"""Minimal MCP-compatible JSON-RPC server for a FactoryBench task world."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .catalog import BENCHMARK_VERSION, get_task
from .contracts import public_tool_definitions
from .world import (
    FactoryWorld,
    READ_TOOLS,
    WRITE_TOOLS,
    seed_database,
)


def tool_definitions(task: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return public_tool_definitions(task["answer_schema"] if task is not None else None)


def _response(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    response = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response


def handle_request(world: FactoryWorld, request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "experimental": {},
                    "logging": {},
                    "prompts": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "tools": {"listChanged": False},
                },
                "serverInfo": {"name": "factorybench", "version": BENCHMARK_VERSION},
            },
        )
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": tool_definitions(world.task)})
    if method == "tools/call":
        params = request.get("params", {})
        name = params.get("name", "")
        result = world.call_tool(name, params.get("arguments", {}))
        return _response(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
                "isError": "error" in result,
            },
        )
    task_uri = f"factorybench://tasks/{world.task['task_id']}"
    if method == "resources/list":
        return _response(
            request_id,
            {
                "resources": [
                    {
                        "name": f"{world.task['task_id']}-instruction",
                        "title": "Task instruction",
                        "uri": f"{task_uri}/instruction",
                        "mimeType": "text/plain",
                    },
                    {
                        "name": f"{world.task['task_id']}-tool-contract",
                        "title": "Task-scoped MCP tool contract",
                        "uri": f"{task_uri}/tool-contract",
                        "mimeType": "application/json",
                    },
                ]
            },
        )
    if method == "resources/read":
        uri = request.get("params", {}).get("uri")
        if uri == f"{task_uri}/instruction":
            contents = [{"uri": uri, "mimeType": "text/plain", "text": world.task["instruction"]}]
        elif uri == f"{task_uri}/tool-contract":
            contents = [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps({"tools": tool_definitions(world.task)}, sort_keys=True),
                }
            ]
        else:
            return _response(request_id, error={"code": -32002, "message": "resource not found"})
        return _response(request_id, {"contents": contents})
    if method == "prompts/list":
        return _response(
            request_id,
            {
                "prompts": [
                    {
                        "name": "run-factory-workflow",
                        "title": "Run the FactoryBench ERP workflow",
                        "description": "Complete the current task against its isolated ERP state.",
                        "arguments": [],
                    }
                ]
            },
        )
    if method == "prompts/get":
        name = request.get("params", {}).get("name")
        if name != "run-factory-workflow":
            return _response(request_id, error={"code": -32602, "message": "prompt not found"})
        return _response(
            request_id,
            {
                "description": "Complete the current isolated FactoryBench task.",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"{world.task['instruction']} Investigate the isolated world in any valid order. "
                                "When the business work is complete, record the structured decision with factorybench.submit_answer."
                            ),
                        },
                    }
                ],
            },
        )
    return _response(request_id, error={"code": -32601, "message": f"method not found: {method}"})


def _load_task(value: str) -> dict[str, Any]:
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return get_task(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one FactoryBench task world")
    parser.add_argument("--task", required=True, help="Task ID or task JSON path")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--call", choices=sorted(READ_TOOLS | WRITE_TOOLS))
    parser.add_argument("--arguments", default="{}")
    args = parser.parse_args()
    task = _load_task(args.task)
    if args.fresh or not args.db.exists():
        seed_database(task, args.db)
    with FactoryWorld(task, args.db) as world:
        if args.call:
            result = world.call_tool(args.call, json.loads(args.arguments))
            print(json.dumps(result, indent=2, sort_keys=True))
            raise SystemExit(1 if "error" in result else 0)
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                response = handle_request(world, request)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                response = _response(None, error={"code": -32600, "message": str(exc)})
            if response is not None:
                print(json.dumps(response, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
