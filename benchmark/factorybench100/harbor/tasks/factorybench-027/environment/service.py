#!/usr/bin/env python3
"""Root-owned Streamable HTTP MCP service for generated Harbor environments."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

try:
    from .contracts import public_tool_definitions
    from .world import FactoryWorld, seed_database
except ImportError:  # Copied beside runtime.py in a Harbor image.
    from contracts import public_tool_definitions
    from runtime import FactoryWorld, seed_database

MAX_REQUEST_BYTES = 1_000_000
PROTOCOL_VERSION = "2025-06-18"


def grouped_tool_definitions(task: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return the task-scoped contract split across its six provider servers."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for tool in public_tool_definitions(task["answer_schema"]):
        server = str(tool["_meta"]["factorybench"]["server"])
        grouped.setdefault(server, []).append(tool)
    return grouped


def _tool_result(result: dict[str, Any]) -> dict[str, Any]:
    response: dict[str, Any] = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False, sort_keys=True),
            }
        ],
        "isError": "error" in result,
    }
    if "error" not in result:
        response["structuredContent"] = result
    return response


def mcp_response(
    world: FactoryWorld,
    tools_by_server: dict[str, list[dict[str, Any]]],
    server_name: str,
    request: dict[str, Any],
) -> dict[str, Any] | None:
    """Handle one MCP request against the authoritative task world."""

    request_id = request.get("id")
    method = request.get("method")
    if request_id is None and isinstance(method, str) and method.startswith("notifications/"):
        return None
    if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32600, "message": "Invalid Request"},
        }
    if server_name not in tools_by_server:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"unknown server {server_name!r}"},
        }
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": f"factorybench-{server_name}",
                    "version": str(world.task.get("benchmark_version", "3.3.5")),
                },
                "instructions": (
                    "Operate only on this isolated synthetic FactoryBench task. "
                    "Every write is persisted to task-local SQLite and graded for scope."
                ),
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools_by_server[server_name]},
        }
    if method == "tools/call":
        params = request.get("params")
        if not isinstance(params, dict):
            params = {}
        name = str(params.get("name", ""))
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        allowed = {tool["name"] for tool in tools_by_server[server_name]}
        if name not in allowed:
            result = {"error": f"tool {name!r} is not exposed by {server_name}"}
        else:
            try:
                result = world.call_tool(name, arguments)
            except Exception as exc:  # Keep malformed calls from killing authoritative state.
                world.connection.rollback()
                result = {"error": f"internal tool error: {type(exc).__name__}"}
                world.trace.append(
                    {
                        "index": len(world.trace),
                        "tool": name or "unknown",
                        "arguments": arguments,
                        "success": False,
                        "result": result,
                    }
                )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": _tool_result(result),
        }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


class FactoryService(HTTPServer):
    world: FactoryWorld
    evidence_path: Path
    baseline: dict[str, list[dict[str, Any]]]
    tools_by_server: dict[str, list[dict[str, Any]]]

    def persist_evidence(self) -> None:
        temporary = self.evidence_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "baseline": self.baseline,
                    "snapshot": self.world.snapshot(),
                    "trace": self.world.trace,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(self.evidence_path)


class RequestHandler(BaseHTTPRequestHandler):
    server: FactoryService
    server_version = "FactoryBenchMCP/3.3"

    def log_message(self, *_: Any) -> None:
        return

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("MCP-Protocol-Version", PROTOCOL_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _accepted(self) -> None:
        self.send_response(HTTPStatus.ACCEPTED)
        self.send_header("Content-Length", "0")
        self.send_header("MCP-Protocol-Version", PROTOCOL_VERSION)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path == "/health":
            self._send(
                HTTPStatus.OK,
                {"status": "ok", "task_id": self.server.world.task["task_id"]},
            )
        else:
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if not self.path.startswith("/mcp/"):
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        server_name = self.path.removeprefix("/mcp/")
        if (
            server_name not in self.server.tools_by_server
            or self.path != f"/mcp/{server_name}"
        ):
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_REQUEST_BYTES:
            self._send(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "invalid request size"},
                },
            )
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._send(
                HTTPStatus.BAD_REQUEST,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                },
            )
            return
        if isinstance(payload, list):
            responses = [
                response
                for item in payload
                if isinstance(item, dict)
                and (
                    response := mcp_response(
                        self.server.world,
                        self.server.tools_by_server,
                        server_name,
                        item,
                    )
                )
                is not None
            ]
            self.server.persist_evidence()
            self._send(HTTPStatus.OK, responses)
            return
        if not isinstance(payload, dict):
            self._send(
                HTTPStatus.BAD_REQUEST,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Invalid Request"},
                },
            )
            return
        response = mcp_response(
            self.server.world,
            self.server.tools_by_server,
            server_name,
            payload,
        )
        self.server.persist_evidence()
        if response is None:
            self._accepted()
            return
        self._send(HTTPStatus.OK, response)


def main() -> None:
    root = Path(os.environ.get("FACTORYBENCH_ROOT", "/opt/factorybench"))
    state_dir = Path(os.environ.get("FACTORYBENCH_STATE_DIR", "/var/lib/factorybench"))
    evidence_path = Path(
        os.environ.get(
            "FACTORYBENCH_EVIDENCE_PATH",
            "/var/lib/factorybench-evidence/evidence.json",
        )
    )
    os.umask(0o077)
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_dir.chmod(0o700)
    evidence_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    evidence_path.parent.chmod(0o700)
    task = json.loads((root / "task.json").read_text(encoding="utf-8"))
    database_path = seed_database(task, state_dir / "world.db")
    database_path.chmod(0o600)
    with FactoryWorld(task, database_path) as world:
        bind_host = os.environ.get("FACTORYBENCH_BIND_HOST", "127.0.0.1")
        port = int(os.environ.get("FACTORYBENCH_PORT", "8765"))
        server = FactoryService((bind_host, port), RequestHandler)
        server.world = world
        server.evidence_path = evidence_path
        server.baseline = world.snapshot()
        server.tools_by_server = grouped_tool_definitions(task)
        server.persist_evidence()
        try:
            server.serve_forever()
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
