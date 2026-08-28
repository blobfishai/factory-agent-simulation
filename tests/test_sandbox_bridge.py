from __future__ import annotations

import json
from pathlib import Path

from factorybench.catalog import build_catalog
from factorybench.sandbox_bridge import _run


def _bundle(tmp_path: Path, task: dict) -> Path:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "task.json").write_text(json.dumps(task), encoding="utf-8")
    return bundle


def test_sandbox_bridge_persists_a_real_isolated_episode(tmp_path: Path) -> None:
    task = build_catalog()[0]
    bundle = _bundle(tmp_path, task)
    session = tmp_path / "session"

    reset = _run(bundle, session, {"action": "reset"})
    assert reset["ok"] is True
    assert reset["trace"] == []
    assert reset["state_diff"] == {}
    assert reset["verification"]["strict_pass"] is False

    for index, step in enumerate(task["oracle_steps"], start=1):
        result = _run(
            bundle,
            session,
            {
                "action": "call",
                "tool": step["tool"],
                "arguments": step["arguments"],
            },
        )
        assert result["ok"] is True
        assert result["is_error"] is False
        assert result["state_revision"] == index

    evidence = _run(bundle, session, {"action": "inspect"})
    assert evidence["state_revision"] == len(task["oracle_steps"])
    assert evidence["verification"]["score"] == 100.0
    assert evidence["verification"]["strict_pass"] is True
    assert set(evidence["state_diff"]) >= {
        "answers",
        "audit_log",
        "resource_state",
    }


def test_sandbox_bridge_returns_tool_errors_inside_the_episode(tmp_path: Path) -> None:
    task = build_catalog()[0]
    bundle = _bundle(tmp_path, task)
    session = tmp_path / "session"
    _run(bundle, session, {"action": "reset"})

    write = next(step for step in task["oracle_steps"] if not step.get("control"))
    result = _run(
        bundle,
        session,
        {"action": "call", "tool": write["tool"], "arguments": write["arguments"]},
    )
    assert result["ok"] is True
    assert result["is_error"] is True
    assert "read-before-write control failed" in result["result"]["error"]

    evidence = _run(bundle, session, {"action": "inspect"})
    assert evidence["verification"]["strict_pass"] is False
    assert evidence["verification"]["checks"][-1]["id"] == "error_free"
    assert evidence["verification"]["checks"][-1]["passed"] is False
