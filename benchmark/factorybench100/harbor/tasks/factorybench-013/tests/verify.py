#!/usr/bin/env python3
"""Hidden verifier entrypoint for generated Harbor task packages."""

from __future__ import annotations

import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _canonical_argument(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _canonical_argument(item)) for key, item in value.items()))
    if isinstance(value, list):
        normalized = [_canonical_argument(item) for item in value]
        return tuple(sorted(normalized, key=repr))
    return value


def _missing_required_read_calls(
    task: dict[str, Any],
    trace: list[dict[str, Any]],
    before_index: int,
) -> list[dict[str, Any]]:
    successful = [
        entry for entry in trace if entry.get("success") and entry["index"] < before_index
    ]
    missing = []
    for requirement in task["required_read_calls"]:
        if not any(
            entry["tool"] == requirement["tool"]
            and (
                requirement.get("match") == "successful_tool_call"
                or _canonical_argument(entry.get("arguments", {}))
                == _canonical_argument(requirement["arguments"])
            )
            for entry in successful
        ):
            missing.append(requirement)
    return missing


def _normalize_answer_fields(task: dict[str, Any], fields: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    properties = task["answer_schema"]["properties"]
    for field, field_schema in properties.items():
        value = fields[field]
        answer_type = field_schema["type"]
        if answer_type == "string":
            normalized[field] = str(value)
            continue
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"invalid expected numeric answer field: {field}") from exc
        if answer_type == "integer":
            normalized[field] = str(int(decimal_value))
        else:
            quantum = Decimal(str(field_schema.get("multipleOf", 0.01)))
            places = max(0, -quantum.as_tuple().exponent)
            normalized[field] = f"{decimal_value.quantize(quantum):.{places}f}"
    return normalized


def _fetch_evidence() -> dict[str, Any]:
    evidence_path = Path(
        os.environ.get(
            "FACTORYBENCH_EVIDENCE_PATH",
            "/var/lib/factorybench-evidence/evidence.json",
        )
    )
    return json.loads(evidence_path.read_text(encoding="utf-8"))


def _matching_rows(
    snapshot: dict[str, list[dict[str, Any]]],
    assertion: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        row
        for row in snapshot.get(assertion["table"], [])
        if all(row.get(key) == value for key, value in assertion["where"].items())
    ]


def _write_verdict(verdict: dict[str, Any]) -> None:
    logdir = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))
    logdir.mkdir(parents=True, exist_ok=True)
    score = verdict["factory_score"] / 100
    (logdir / "verdict.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (logdir / "reward.json").write_text(json.dumps({"reward": score}) + "\n", encoding="utf-8")
    (logdir / "reward.txt").write_text(f"{score:.8f}\n", encoding="utf-8")


def _write_trace(task_id: str, trace: list[dict[str, Any]]) -> None:
    """Publish only interactions the agent already observed, never hidden state."""

    logdir = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))
    logdir.mkdir(parents=True, exist_ok=True)
    (logdir / "trace.json").write_text(
        json.dumps({"task_id": task_id, "trace": trace}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    task = json.loads((HERE / "task.json").read_text(encoding="utf-8"))
    evidence = _fetch_evidence()
    trace = evidence["trace"]
    current_snapshot = evidence["snapshot"]
    baseline_snapshot = evidence["baseline"]
    checks: list[dict[str, Any]] = []

    successful = [entry for entry in trace if entry.get("success")]
    write_tools = set(task["write_tools"])
    first_write = min(
        (entry["index"] for entry in successful if entry["tool"] in write_tools),
        default=len(trace) + 1,
    )
    missing = _missing_required_read_calls(task, trace, first_write)
    checks.append(
        {
            "id": "read_before_write",
            "passed": not missing,
            "evidence": {"missing": missing},
        }
    )

    for assertion in task["expected"]["assertions"]:
        rows = _matching_rows(current_snapshot, assertion)
        passed = len(rows) == assertion.get("count", 1)
        mismatches: dict[str, Any] = {}
        if "values" in assertion and len(rows) == 1:
            for key, expected in assertion["values"].items():
                actual = rows[0].get(key)
                matched = (
                    abs(float(actual) - expected) <= 1e-6
                    if isinstance(expected, float) and isinstance(actual, (int, float))
                    else actual == expected
                )
                if not matched:
                    mismatches[key] = {"expected": expected, "actual": actual}
            passed = passed and not mismatches
        checks.append(
            {
                "id": assertion["id"],
                "passed": passed,
                "evidence": {"rows": len(rows), "mismatches": mismatches},
            }
        )

    submitted = {
        row["field"]: row["value"]
        for row in current_snapshot.get("answers", [])
        if row["task_id"] == task["task_id"]
    }
    expected_answer = _normalize_answer_fields(task, task["expected"]["answer"])
    checks.append(
        {
            "id": "exact_answer",
            "passed": submitted == expected_answer,
            "evidence": {"expected": expected_answer, "submitted": submitted},
        }
    )

    changed_tables = sorted(
        table
        for table in set(current_snapshot) | set(baseline_snapshot)
        if current_snapshot.get(table, []) != baseline_snapshot.get(table, [])
    )
    disallowed = sorted(set(changed_tables) - set(task["allowed_write_tables"]))
    checks.append(
        {
            "id": "write_scope",
            "passed": not disallowed,
            "evidence": {"changed": changed_tables, "disallowed": disallowed},
        }
    )

    errors = [entry for entry in trace if not entry.get("success")]
    checks.append(
        {
            "id": "error_free",
            "passed": not errors,
            "evidence": {"errors": errors},
        }
    )
    passed = sum(1 for check in checks if check["passed"])
    score = passed / len(checks)
    verdict = {
        "task_id": task["task_id"],
        "metric": "FactoryScore",
        "factory_score": round(score * 100, 2),
        "strict_pass": passed == len(checks),
        "checks": checks,
    }
    _write_trace(task["task_id"], trace)
    _write_verdict(verdict)
    print(json.dumps(verdict, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
