"""Per-session bridge from HTTP MCP requests to the authoritative SQLite world.

The website invokes this module as a short-lived, allowlisted worker.  State is
kept in a private session directory, while the tool implementation remains the
same ``FactoryWorld`` used by Harbor and the stdio MCP server.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
from typing import Any

try:
    from .world import (
        FactoryWorld,
        WRITE_TOOLS,
        missing_required_read_calls,
        normalize_answer_fields,
        seed_database,
    )
except ImportError:  # Standalone release bundle copied beside runtime.py.
    from runtime import (  # type: ignore[no-redef]
        FactoryWorld,
        WRITE_TOOLS,
        missing_required_read_calls,
        normalize_answer_fields,
        seed_database,
    )

MAX_REQUEST_BYTES = 1_000_000
MAX_DIFF_ROWS = 100
MAX_TRACE_CALLS = 128


def _read_request() -> dict[str, Any]:
    raw = os.read(0, MAX_REQUEST_BYTES + 1)
    if not raw:
        raise ValueError("request body is required")
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request body exceeds 1 MB")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _changed_state(
    baseline: dict[str, list[dict[str, Any]]],
    current: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for table in sorted(set(baseline) | set(current)):
        before = baseline.get(table, [])
        after = current.get(table, [])
        if before == after:
            continue
        changed[table] = {
            "before_count": len(before),
            "after_count": len(after),
            "before": before[:MAX_DIFF_ROWS],
            "after": after[:MAX_DIFF_ROWS],
            "truncated": len(before) > MAX_DIFF_ROWS or len(after) > MAX_DIFF_ROWS,
        }
    return changed


def _query_rows(world: FactoryWorld, assertion: dict[str, Any]) -> list[dict[str, Any]]:
    where = assertion["where"]
    clauses = " AND ".join(
        f"{column} IS ?" if value is None else f"{column} = ?"
        for column, value in where.items()
    )
    query = f"SELECT * FROM {assertion['table']}"
    if clauses:
        query += f" WHERE {clauses}"
    return [
        dict(row)
        for row in world.connection.execute(query, list(where.values())).fetchall()
    ]


def _values_match(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    mismatches: dict[str, Any] = {}
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        if isinstance(expected_value, float) and isinstance(actual_value, (int, float)):
            matched = abs(float(actual_value) - expected_value) <= 1e-6
        else:
            matched = actual_value == expected_value
        if not matched:
            mismatches[field] = {"expected": expected_value, "actual": actual_value}
    return mismatches


def _verify(task: dict[str, Any], world: FactoryWorld) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    successful = [entry for entry in world.trace if entry.get("success")]
    first_write_index = min(
        (
            entry["index"]
            for entry in successful
            if entry["tool"] in WRITE_TOOLS
        ),
        default=len(world.trace) + 1,
    )
    missing_reads = missing_required_read_calls(
        task,
        world.trace,
        before_index=first_write_index,
    )
    checks.append(
        {
            "id": "read_before_write",
            "description": "Required policy and ERP reads completed before the first write.",
            "passed": not missing_reads,
            "evidence": {"missing": missing_reads},
        }
    )

    for assertion in task["expected"]["assertions"]:
        rows = _query_rows(world, assertion)
        passed = True
        evidence: dict[str, Any] = {"matching_rows": len(rows)}
        if "count" in assertion:
            passed = len(rows) == assertion["count"]
            evidence["expected_count"] = assertion["count"]
        if "values" in assertion:
            if len(rows) != 1:
                passed = False
                evidence["expected_unique_row"] = True
            else:
                mismatches = _values_match(rows[0], assertion["values"])
                passed = passed and not mismatches
                evidence["mismatches"] = mismatches
        checks.append(
            {
                "id": assertion["id"],
                "description": assertion["description"],
                "passed": passed,
                "evidence": evidence,
            }
        )

    submitted = {
        row["field"]: row["value"]
        for row in world.connection.execute(
            "SELECT field, value FROM answers WHERE task_id = ? ORDER BY field",
            (task["task_id"],),
        ).fetchall()
    }
    expected_answer = normalize_answer_fields(task, task["expected"]["answer"])
    checks.append(
        {
            "id": "exact_answer",
            "description": "Submitted answer fields exactly match the ground truth.",
            "passed": submitted == expected_answer,
            "evidence": {"expected": expected_answer, "submitted": submitted},
        }
    )

    written_tables = {
        row["table_name"]
        for row in world.connection.execute(
            "SELECT DISTINCT table_name FROM audit_log WHERE task_id = ?",
            (task["task_id"],),
        ).fetchall()
    }
    disallowed = sorted(written_tables - set(task["allowed_write_tables"]))
    checks.append(
        {
            "id": "write_scope",
            "description": "All successful writes stay inside the task's allowed tables.",
            "passed": not disallowed,
            "evidence": {
                "written_tables": sorted(written_tables),
                "disallowed": disallowed,
            },
        }
    )

    errors = [
        {
            "index": entry["index"],
            "tool": entry["tool"],
            "error": entry["result"].get("error"),
        }
        for entry in world.trace
        if not entry.get("success")
    ]
    checks.append(
        {
            "id": "error_free",
            "description": "The episode completes without a rejected or malformed tool call.",
            "passed": not errors,
            "evidence": {"errors": errors},
        }
    )
    passed = sum(1 for check in checks if check["passed"])
    return {
        "task_id": task["task_id"],
        "metric": "FactoryScore",
        "score": round(passed / len(checks) * 100, 2),
        "passed_checks": passed,
        "total_checks": len(checks),
        "strict_pass": passed == len(checks),
        "checks": checks,
    }


def _persist(
    evidence_path: Path,
    baseline: dict[str, list[dict[str, Any]]],
    world: FactoryWorld,
) -> dict[str, Any]:
    current = world.snapshot()
    evidence = {
        "baseline": baseline,
        "snapshot": current,
        "trace": world.trace,
    }
    _write_json(evidence_path, evidence)
    return evidence


def _summary(
    task: dict[str, Any],
    world: FactoryWorld,
    baseline: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    current = world.snapshot()
    return {
        "task_id": task["task_id"],
        "state_revision": len(world.trace),
        "trace": world.trace,
        "state_diff": _changed_state(baseline, current),
        "verification": _verify(task, world),
    }


def _run(bundle_root: Path, session_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
    task = json.loads((bundle_root / "task.json").read_text(encoding="utf-8"))
    action = request.get("action")
    if action not in {"reset", "call", "inspect"}:
        raise ValueError("action must be reset, call, or inspect")

    session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    session_dir.chmod(0o700)
    database_path = session_dir / "world.db"
    evidence_path = session_dir / "evidence.json"
    lock_path = session_dir / ".lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        lock_path.chmod(0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if action == "reset" or not database_path.exists() or not evidence_path.exists():
            seed_database(task, database_path)
            database_path.chmod(0o600)
            with FactoryWorld(task, database_path) as world:
                baseline = world.snapshot()
                _persist(evidence_path, baseline, world)
                return {"ok": True, **_summary(task, world, baseline)}

        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        baseline = evidence["baseline"]
        with FactoryWorld(task, database_path) as world:
            world.trace = evidence.get("trace", [])
            if action == "call":
                tool = request.get("tool")
                arguments = request.get("arguments", {})
                if not isinstance(tool, str) or not isinstance(arguments, dict):
                    raise ValueError("tool must be a string and arguments must be an object")
                if len(world.trace) >= MAX_TRACE_CALLS:
                    return {
                        "ok": True,
                        "result": {"error": f"session tool-call limit reached ({MAX_TRACE_CALLS})"},
                        "is_error": True,
                        "state_revision": len(world.trace),
                    }
                result = world.call_tool(tool, arguments)
                _persist(evidence_path, baseline, world)
                return {
                    "ok": True,
                    "result": result,
                    "is_error": "error" in result,
                    "state_revision": len(world.trace),
                }
            return {"ok": True, **_summary(task, world, baseline)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one isolated FactoryBench web session")
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--session-dir", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        response = _run(args.bundle_root.resolve(), args.session_dir.resolve(), _read_request())
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        response = {"ok": False, "error": str(exc)}
    print(json.dumps(response, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
