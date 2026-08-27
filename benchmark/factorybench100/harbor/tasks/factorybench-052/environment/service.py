#!/usr/bin/env python3
"""Root-owned HTTP tool service used by generated Harbor environments."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

try:
    from .world import FactoryWorld, seed_database
except ImportError:  # Copied beside runtime.py in a Harbor image.
    from runtime import FactoryWorld, seed_database

MAX_REQUEST_BYTES = 1_000_000


class FactoryService(HTTPServer):
    world: FactoryWorld
    evidence_path: Path
    baseline: dict[str, list[dict[str, Any]]]

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

    def log_message(self, *_: Any) -> None:
        return

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path != "/call":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_REQUEST_BYTES:
            self._send(413, {"error": "invalid request size"})
            return
        payload: Any = None
        try:
            payload = json.loads(self.rfile.read(length))
            tool = payload["tool"]
            arguments = payload.get("arguments", {})
            if not isinstance(tool, str) or not isinstance(arguments, dict):
                raise TypeError("tool must be a string and arguments must be an object")
            result = self.server.world.call_tool(tool, arguments)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            result = {"error": str(exc)}
        except Exception as exc:  # Keep malformed calls from killing authoritative state.
            self.server.world.connection.rollback()
            result = {"error": f"internal tool error: {type(exc).__name__}"}
            self.server.world.trace.append(
                {
                    "index": len(self.server.world.trace),
                    "tool": payload.get("tool", "unknown") if isinstance(payload, dict) else "unknown",
                    "arguments": payload.get("arguments", {}) if isinstance(payload, dict) else {},
                    "success": False,
                    "result": result,
                }
            )
        self.server.persist_evidence()
        self._send(200, result)


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
        server = FactoryService((bind_host, 8765), RequestHandler)
        server.world = world
        server.evidence_path = evidence_path
        server.baseline = world.snapshot()
        server.persist_evidence()
        try:
            server.serve_forever()
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
