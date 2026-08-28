#!/usr/bin/env python3
"""Hidden verifier entrypoint for generated Harbor task packages."""

from __future__ import annotations

import base64
import json
import os
import re
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
            _investigation_requirement_matches(entry, requirement)
            for entry in successful
        ):
            missing.append(requirement)
    return missing


def _missing_required_investigations(
    task: dict[str, Any],
    trace: list[dict[str, Any]],
    before_index: int,
) -> list[dict[str, Any]]:
    successful = [
        entry for entry in trace if entry.get("success") and entry["index"] < before_index
    ]
    missing: list[dict[str, Any]] = []
    for investigation in task.get("required_investigations", []):
        if not any(
            _investigation_requirement_matches(entry, requirement)
            for requirement in investigation["any_of"]
            for entry in successful
        ):
            missing.append(investigation)
    return missing


def _result_contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        if isinstance(actual, dict) and all(
            key in actual and _result_contains(actual[key], value)
            for key, value in expected.items()
        ):
            return True
        if isinstance(actual, dict):
            return any(_result_contains(value, expected) for value in actual.values())
        if isinstance(actual, list):
            return any(_result_contains(value, expected) for value in actual)
        return False
    if isinstance(expected, list):
        return isinstance(actual, list) and all(
            any(_result_contains(candidate, item) for candidate in actual)
            for item in expected
        )
    return actual == expected


def _investigation_requirement_matches(
    entry: dict[str, Any],
    requirement: dict[str, Any],
) -> bool:
    if entry["tool"] != requirement["tool"]:
        return False
    match = requirement.get("match")
    if match == "result_contains":
        fragment = requirement.get("expected_result_contains")
        return fragment is not None and _result_contains(entry.get("result"), fragment)
    if match == "successful_tool_call":
        return True
    expected_arguments = requirement.get("arguments")
    return expected_arguments is None or _canonical_argument(
        entry.get("arguments", {})
    ) == _canonical_argument(expected_arguments)


def _missing_post_write_verifications(
    task: dict[str, Any],
    trace: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    successful = [entry for entry in trace if entry.get("success")]
    missing: list[dict[str, Any]] = []
    for verification in task.get("post_write_verifications", []):
        mutation_indexes = [
            entry["index"]
            for entry in successful
            if entry["tool"] == verification["after_tool"]
        ]
        if not mutation_indexes:
            missing.append(verification)
            continue
        mutation_index = min(mutation_indexes)
        matched = any(
            entry["index"] > mutation_index
            and _investigation_requirement_matches(entry, requirement)
            and _result_contains(
                entry.get("result"),
                verification.get("expected_result_contains", {}),
            )
            for requirement in verification.get("any_of", [])
            for entry in successful
        )
        if not matched:
            missing.append(verification)
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


def _nested_subset_mismatches(
    actual: Any,
    expected: Any,
    path: str = "payload",
) -> dict[str, dict[str, Any]]:
    mismatches: dict[str, dict[str, Any]] = {}
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return {path: {"expected": expected, "actual": actual}}
        for key, value in expected.items():
            child_path = f"{path}.{key}"
            if key not in actual:
                mismatches[child_path] = {
                    "expected": value,
                    "actual": None,
                    "reason": "missing key",
                }
            else:
                mismatches.update(
                    _nested_subset_mismatches(actual[key], value, child_path)
                )
        return mismatches
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return {path: {"expected": expected, "actual": actual}}
        if len(actual) != len(expected):
            return {
                path: {
                    "expected_length": len(expected),
                    "actual_length": len(actual),
                }
            }
        for index, value in enumerate(expected):
            mismatches.update(
                _nested_subset_mismatches(actual[index], value, f"{path}[{index}]")
            )
        return mismatches
    if actual != expected:
        mismatches[path] = {"expected": expected, "actual": actual}
    return mismatches


def _decoded_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_decoded_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_decoded_text(item) for item in value)
    if not isinstance(value, str):
        return str(value)
    variants = [value]
    try:
        padded = value + "=" * (-len(value) % 4)
        variants.append(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        pass
    return " ".join(variants)


def _leaf_paths(value: Any, path: str = "") -> set[str]:
    if isinstance(value, dict):
        return {
            leaf
            for key, item in value.items()
            for leaf in _leaf_paths(item, f"{path}.{key}" if path else key)
        }
    if isinstance(value, list):
        return {
            leaf
            for index, item in enumerate(value)
            for leaf in _leaf_paths(item, f"{path}[{index}]")
        }
    return {path}


def _payload_assertion_mismatches(
    row: dict[str, Any],
    assertion: dict[str, Any],
) -> dict[str, Any]:
    if not any(
        key in assertion
        for key in (
            "payload_contains",
            "payload_text_contains",
            "payload_text_any_of",
            "payload_allowed_argument_paths",
        )
    ):
        return {}
    raw_payload = row.get("payload_json")
    try:
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    except json.JSONDecodeError:
        return {"payload_json": {"reason": "invalid JSON", "actual": raw_payload}}
    if not isinstance(payload, dict):
        return {"payload_json": {"reason": "payload is not an object", "actual": payload}}
    evidence: dict[str, Any] = {}
    expected_subset = assertion.get("payload_contains")
    if expected_subset is not None:
        nested = _nested_subset_mismatches(payload, expected_subset)
        if nested:
            evidence["payload_mismatches"] = nested
    expected_text = assertion.get("payload_text_contains", [])
    if expected_text:
        searchable = re.sub(
            r"[^a-z0-9.]+",
            " ",
            _decoded_text(payload.get("arguments", payload)).casefold(),
        )
        missing = [
            str(fragment)
            for fragment in expected_text
            if re.sub(r"[^a-z0-9.]+", " ", str(fragment).casefold()).strip()
            not in searchable
        ]
        if missing:
            evidence["missing_payload_text"] = missing
    expected_groups = assertion.get("payload_text_any_of", [])
    if expected_groups:
        searchable = re.sub(
            r"[^a-z0-9.]+",
            " ",
            _decoded_text(payload.get("arguments", payload)).casefold(),
        )
        missing_groups = [
            [str(fragment) for fragment in group]
            for group in expected_groups
            if not any(
                normalized
                and normalized in searchable
                for fragment in group
                for normalized in (
                    re.sub(
                        r"[^a-z0-9.]+",
                        " ",
                        str(fragment).casefold(),
                    ).strip(),
                )
            )
        ]
        if missing_groups:
            evidence["missing_payload_text_any_of"] = missing_groups
    allowed_paths = assertion.get("payload_allowed_argument_paths")
    if allowed_paths is not None:
        actual_paths = _leaf_paths(payload.get("arguments", {}))
        unexpected_paths = sorted(actual_paths - set(allowed_paths))
        if unexpected_paths:
            evidence["unexpected_payload_paths"] = unexpected_paths
    return evidence


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
    investigations = task.get("required_investigations", [])
    if investigations:
        for investigation in investigations:
            missing = _missing_required_investigations(
                {"required_investigations": [investigation]},
                trace,
                first_write,
            )
            checks.append(
                {
                    "id": investigation["id"],
                    "description": investigation["description"],
                    "weight": float(investigation.get("weight", 1.0)),
                    "passed": not missing,
                    "evidence": {"missing": missing},
                }
            )
    else:
        missing = _missing_required_read_calls(task, trace, first_write)
        checks.append(
            {
                "id": "read_before_write",
                "description": "Required cross-system evidence reads completed before the first write.",
                "weight": 1.0,
                "passed": not missing,
                "evidence": {"missing": missing},
            }
        )

    for verification in task.get("post_write_verifications", []):
        missing = _missing_post_write_verifications(
            {"post_write_verifications": [verification]},
            trace,
        )
        checks.append(
            {
                "id": verification["id"],
                "description": verification["description"],
                "weight": float(verification.get("weight", 1.0)),
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
        if len(rows) == 1:
            payload_mismatches = _payload_assertion_mismatches(rows[0], assertion)
            passed = passed and not payload_mismatches
            mismatches.update(payload_mismatches)
        checks.append(
            {
                "id": assertion["id"],
                "description": assertion["description"],
                "weight": float(assertion.get("weight", 1.0)),
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
    answer_criteria = [
        *task["expected"].get("answer_checks", []),
        *task["expected"].get("calculations", []),
    ]
    if answer_criteria:
        for criterion in answer_criteria:
            field = criterion["field"]
            checks.append(
                {
                    "id": criterion["id"],
                    "description": criterion["description"],
                    "weight": float(criterion.get("weight", 1.0)),
                    "passed": submitted.get(field) == expected_answer[field],
                    "evidence": {
                        "field": field,
                        "expected": expected_answer[field],
                        "submitted": submitted.get(field),
                    },
                }
            )
    else:
        checks.append(
            {
                "id": "exact_answer",
                "description": "Submitted answer fields exactly match the ground truth.",
                "weight": 1.0,
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
            "description": f"Kept every successful write inside {task['task_id']}'s declared state.",
            "weight": 1.0,
            "passed": not disallowed,
            "evidence": {"changed": changed_tables, "disallowed": disallowed},
        }
    )

    errors = [
        entry
        for entry in trace
        if not entry.get("success")
        and entry["tool"] in write_tools - {"factorybench.submit_answer"}
    ]
    checks.append(
        {
            "id": "no_rejected_mutation",
            "description": "Completed without a rejected state-changing call; failed exploratory reads do not erase a correct outcome.",
            "weight": 1.0,
            "passed": not errors,
            "evidence": {"errors": errors},
        }
    )
    passed = sum(1 for check in checks if check["passed"])
    passed_weight = sum(check["weight"] for check in checks if check["passed"])
    total_weight = sum(check["weight"] for check in checks)
    score = passed_weight / total_weight
    verdict = {
        "task_id": task["task_id"],
        "metric": "FactoryScore",
        "factory_score": round(score * 100, 2),
        "passed_weight": round(passed_weight, 2),
        "total_weight": round(total_weight, 2),
        "strict_pass": passed == len(checks),
        "checks": checks,
    }
    _write_trace(task["task_id"], trace)
    _write_verdict(verdict)
    print(json.dumps(verdict, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
