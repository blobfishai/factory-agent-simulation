#!/usr/bin/env python3
"""Agent-facing CLI for the protected Harbor tool service."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _call_service(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    url = os.environ.get("FACTORYBENCH_SERVICE_URL", "http://127.0.0.1:8765/call")
    request = urllib.request.Request(
        url,
        data=json.dumps({"tool": tool, "arguments": arguments}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(20):
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read())
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
    result = _call_service(name, arguments)
    print(json.dumps(result, indent=2, sort_keys=True))
    if "error" in result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
