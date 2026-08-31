#!/usr/bin/env python3
"""Terminal-friendly client for the protected Harbor MCP service."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _call_service(
    definition: dict[str, Any], arguments: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    base = os.environ.get("FACTORYBENCH_MCP_BASE", "http://127.0.0.1:8765/mcp")
    server = definition["_meta"]["factorybench"]["server"]
    url = f"{base.rstrip('/')}/{server}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": definition["name"], "arguments": arguments},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(20):
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                rpc = json.loads(response.read())
                if "error" in rpc:
                    return {"error": str(rpc["error"])}, True
                result = rpc.get("result") or {}
                content = result.get("content") or []
                text = content[0].get("text", "{}") if content else "{}"
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = {"result": text}
                if not isinstance(parsed, dict):
                    parsed = {"result": parsed}
                return parsed, bool(result.get("isError"))
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < 19:
                time.sleep(0.05)
    raise RuntimeError(f"factorybench service unavailable: {last_error}")


def main() -> None:
    root = Path(os.environ.get("FACTORYBENCH_ROOT", "/opt/factorybench"))
    tools = json.loads((root / "tools.json").read_text(encoding="utf-8"))
    if len(sys.argv) < 2 or sys.argv[1] not in {"list", "schema", "call"}:
        raise SystemExit("usage: tool list | tool schema NAME | tool call NAME JSON")
    command = sys.argv[1]
    if command == "list":
        for item in tools:
            print(f"{item['name']}\t{item.get('description', '')}")
        return
    if len(sys.argv) < 3:
        raise SystemExit(f"tool {command} requires a tool name")
    name = sys.argv[2]
    definition = next((item for item in tools if item["name"] == name), None)
    if definition is None:
        raise SystemExit(f"unknown tool: {name}")
    if command == "schema":
        print(json.dumps(definition["inputSchema"], indent=2))
        return
    try:
        arguments = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"arguments must be valid JSON: {exc}") from exc
    if not isinstance(arguments, dict):
        raise SystemExit("arguments must be a JSON object")
    result, is_error = _call_service(definition, arguments)
    print(json.dumps(result, indent=2, sort_keys=True))
    if is_error or "error" in result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
