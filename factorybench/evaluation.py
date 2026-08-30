"""Deterministic FactoryScore evaluation and qualification baselines."""

from __future__ import annotations

import argparse
import base64
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .catalog import build_catalog
from .world import (
    FactoryWorld,
    READ_TOOLS,
    WRITE_TOOLS,
    missing_post_write_verifications,
    missing_required_investigations,
    missing_required_read_calls,
    normalize_answer_fields,
    payload_assertion_mismatches,
)

NEGATIVE_POLICIES = (
    "noop",
    "shortcut",
    "state_only",
    "incomplete_read",
    "write_before_read",
    "missing_readback",
    "unauthorized_write",
    "wrong_value",
    "wrong_decision",
    "wrong_evidence",
    "wrong_target",
    "keyword_stuffing",
)
POLICIES = ("oracle", *NEGATIVE_POLICIES)


def _query_rows(world: FactoryWorld, assertion: dict[str, Any]) -> list[dict[str, Any]]:
    where = assertion["where"]
    clauses = " AND ".join(f"{column} IS ?" if value is None else f"{column} = ?" for column, value in where.items())
    query = f"SELECT * FROM {assertion['table']}"
    params: list[Any] = []
    if clauses:
        query += f" WHERE {clauses}"
        params = list(where.values())
    return [dict(row) for row in world.connection.execute(query, params).fetchall()]


def _values_match(actual: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    mismatches: dict[str, Any] = {}
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        if isinstance(expected_value, float) and isinstance(actual_value, (int, float)):
            matched = abs(float(actual_value) - expected_value) <= 1e-6
        else:
            matched = actual_value == expected_value
        if not matched:
            mismatches[field] = {"expected": expected_value, "actual": actual_value}
    return not mismatches, mismatches


def _aggregate_semantic_checks(
    task: dict[str, Any],
    atomic_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Roll deterministic evidence checks into stable, human-readable milestones."""

    milestones = task.get("rubric_milestones", [])
    if not milestones:
        return [
            {
                **check,
                "earned_weight": float(check["weight"]) if check["passed"] else 0.0,
            }
            for check in atomic_checks
        ]

    by_id: dict[str, dict[str, Any]] = {}
    for check in atomic_checks:
        check_id = str(check["id"])
        if check_id in by_id:
            raise ValueError(f"duplicate atomic check id: {check_id}")
        by_id[check_id] = check

    assigned: set[str] = set()
    aggregated: list[dict[str, Any]] = []
    for milestone in milestones:
        criterion_ids = [str(value) for value in milestone["criterion_ids"]]
        if not criterion_ids:
            raise ValueError(f"semantic milestone {milestone['id']} has no evidence criteria")
        duplicates = sorted({value for value in criterion_ids if criterion_ids.count(value) > 1})
        if duplicates:
            raise ValueError(
                f"semantic milestone {milestone['id']} repeats criteria: {duplicates}"
            )
        reused = sorted(set(criterion_ids) & assigned)
        if reused:
            raise ValueError(f"atomic checks assigned to multiple milestones: {reused}")
        missing = sorted(set(criterion_ids) - set(by_id))
        if missing:
            raise ValueError(
                f"semantic milestone {milestone['id']} references missing checks: {missing}"
            )
        assigned.update(criterion_ids)
        subchecks = [by_id[criterion_id] for criterion_id in criterion_ids]
        atomic_weight = sum(float(check["weight"]) for check in subchecks)
        expected_atomic_weight = float(milestone.get("atomic_weight", atomic_weight))
        if abs(atomic_weight - expected_atomic_weight) > 1e-6:
            raise ValueError(
                f"semantic milestone {milestone['id']} atomic weight changed: "
                f"expected {expected_atomic_weight}, observed {atomic_weight}"
            )
        passed_atomic_weight = sum(
            float(check["weight"]) for check in subchecks if check["passed"]
        )
        milestone_weight = float(milestone["weight"])
        earned_weight = milestone_weight * passed_atomic_weight / atomic_weight
        aggregated.append(
            {
                "id": milestone["id"],
                "category": milestone["category"],
                "description": milestone["description"],
                "weight": milestone_weight,
                "earned_weight": round(earned_weight, 6),
                "passed": all(check["passed"] for check in subchecks),
                "evidence": {
                    "passed_criteria": sum(check["passed"] for check in subchecks),
                    "total_criteria": len(subchecks),
                    "subchecks": subchecks,
                },
            }
        )

    unassigned = sorted(set(by_id) - assigned)
    if unassigned:
        raise ValueError(f"atomic checks omitted from semantic rubric: {unassigned}")
    return aggregated


def verify_episode(task: dict[str, Any], world: FactoryWorld) -> dict[str, Any]:
    """Compute the single benchmark metric from executable checks."""

    checks: list[dict[str, Any]] = []
    successful = [entry for entry in world.trace if entry["success"]]
    first_write_index = min(
        (entry["index"] for entry in successful if entry["tool"] in WRITE_TOOLS),
        default=len(world.trace) + 1,
    )
    for investigation in task.get("required_investigations", []):
        missing = missing_required_investigations(
            {"required_investigations": [investigation]},
            world.trace,
            before_index=first_write_index,
        )
        checks.append(
            {
                "id": investigation["id"],
                "description": investigation["description"],
                "weight": float(investigation.get("weight", 1.0)),
                "passed": not missing,
                "evidence": {
                    "satisfied_by": [
                        {
                            "index": entry["index"],
                            "tool": entry["tool"],
                        }
                        for entry in successful
                        if entry["index"] < first_write_index
                        and any(entry["tool"] == call["tool"] for call in investigation["any_of"])
                    ],
                    "missing": missing,
                },
            }
        )
    if not task.get("required_investigations"):
        missing_reads = missing_required_read_calls(
            task,
            world.trace,
            before_index=first_write_index,
        )
        checks.append(
            {
                "id": "read_before_write",
                "description": "Required cross-system evidence reads completed before the first write.",
                "weight": 1.0,
                "passed": not missing_reads,
                "evidence": {"missing": missing_reads},
            }
        )

    for verification in task.get("post_write_verifications", []):
        missing_readbacks = missing_post_write_verifications(
            {"post_write_verifications": [verification]},
            world.trace,
        )
        checks.append(
            {
                "id": verification["id"],
                "description": verification["description"],
                "weight": float(verification.get("weight", 1.0)),
                "passed": not missing_readbacks,
                "evidence": {
                    "missing": missing_readbacks,
                    "satisfied_by": [
                        {"index": entry["index"], "tool": entry["tool"]}
                        for entry in successful
                        if any(
                            entry["tool"] == requirement["tool"]
                            for requirement in verification.get("any_of", [])
                        )
                    ],
                },
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
                values_passed, mismatches = _values_match(rows[0], assertion["values"])
                passed = passed and values_passed
                evidence["mismatches"] = mismatches
        if len(rows) == 1:
            payload_mismatches = payload_assertion_mismatches(rows[0], assertion)
            passed = passed and not payload_mismatches
            evidence.update(payload_mismatches)
        checks.append(
            {
                "id": assertion["id"],
                "description": assertion["description"],
                "weight": float(assertion.get("weight", 1.0)),
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
    answer_criteria = [
        *task["expected"].get("answer_checks", []),
        *task["expected"].get("calculations", []),
    ]
    if answer_criteria:
        for criterion in answer_criteria:
            field = criterion["field"]
            actual = submitted.get(field)
            expected = expected_answer[field]
            checks.append(
                {
                    "id": criterion["id"],
                    "description": criterion["description"],
                    "weight": float(criterion.get("weight", 1.0)),
                    "passed": actual == expected,
                    "evidence": {"field": field, "expected": expected, "submitted": actual},
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
            "description": f"Kept every successful write inside {task['task_id']}'s declared Oracle, collaboration, answer, and audit state.",
            "weight": 1.0,
            "passed": not disallowed,
            "evidence": {"written_tables": sorted(written_tables), "disallowed": disallowed},
        }
    )

    mutation_errors = [
        {"index": entry["index"], "tool": entry["tool"], "error": entry["result"].get("error")}
        for entry in world.trace
        if not entry["success"] and entry["tool"] in WRITE_TOOLS - {"factorybench.submit_answer"}
    ]
    checks.append(
        {
            "id": "no_rejected_mutation",
            "description": "Completed without a rejected state-changing call; failed exploratory reads do not erase a correct business outcome.",
            "weight": 1.0,
            "passed": not mutation_errors,
            "evidence": {"errors": mutation_errors},
        }
    )

    atomic_checks = checks
    checks = _aggregate_semantic_checks(task, atomic_checks)
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    passed_weight = sum(float(check["earned_weight"]) for check in checks)
    total_weight = sum(float(check["weight"]) for check in checks)
    score = round(passed_weight / total_weight * 100, 2)
    return {
        "task_id": task["task_id"],
        "metric": "FactoryScore",
        "score": score,
        "passed_checks": passed,
        "total_checks": total,
        "passed_weight": round(passed_weight, 2),
        "total_weight": round(total_weight, 2),
        "strict_pass": passed == total,
        "passed_atomic_checks": sum(check["passed"] for check in atomic_checks),
        "total_atomic_checks": len(atomic_checks),
        "checks": checks,
    }


def _state_diff(before: dict[str, list[dict[str, Any]]], after: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for table in sorted(set(before) | set(after)):
        before_rows = before.get(table, [])
        after_rows = after.get(table, [])
        if before_rows != after_rows:
            changed[table] = {
                "before_count": len(before_rows),
                "after_count": len(after_rows),
                "before": before_rows,
                "after": after_rows,
            }
    return changed


def _drive_file_id(task: dict[str, Any], index: int) -> str:
    ordinal = int(task["task_id"].rsplit("-", 1)[1])
    path = task["assets"][index - 1]["path"]
    if path == "business-request-and-control.md":
        return f"drive-{ordinal:03d}"
    if path == "drive-approval-record.json":
        return f"drive-approval-{ordinal:03d}"
    return f"drive-{ordinal:03d}-{index:02d}"


def _wrong_answer(task: dict[str, Any], *, decision: bool) -> dict[str, Any]:
    answer = deepcopy(task["expected"]["answer"])
    if decision:
        answer["recommended_option"] = next(
            option["id"]
            for option in task["decision_model"]["options"]
            if not option["recommended"]
        )
        return answer

    for field, schema in task["answer_schema"]["properties"].items():
        if field == "recommended_option":
            continue
        if schema["type"] in {"integer", "number"}:
            answer[field] = answer[field] + 1
            return answer
    field = next(
        field
        for field, schema in task["answer_schema"]["properties"].items()
        if field != "recommended_option" and "enum" not in schema
    )
    answer[field] = f"{answer[field]}-unsupported"
    return answer


def _unauthorized_write_step(task: dict[str, Any]) -> dict[str, Any]:
    step = deepcopy(
        next(
            item
            for item in task["oracle_steps"]
            if item["phase"] == "primary_mutation"
        )
    )
    arguments = step["arguments"]
    for key, value in arguments.items():
        if key == "requestBody":
            continue
        if isinstance(value, str):
            arguments[key] = f"{value}-OUT-OF-SCOPE"
            break
        if isinstance(value, int) and not isinstance(value, bool):
            arguments[key] = value + 1_000_000
            break
    else:
        arguments.setdefault("requestBody", {})["FactoryBenchUnauthorized"] = True
    step["phase"] = "negative_control"
    step["control"] = False
    return step


def _wrong_evidence_step(
    task: dict[str, Any],
    source: dict[str, Any],
    used_file_ids: set[str],
) -> dict[str, Any]:
    replacement = deepcopy(source)
    role_priority = (
        "engineering_bom_superseded",
        "control_audit_log",
        "planning_chat",
        "procurement_email",
        "revision_index",
    )
    indexed_assets = list(enumerate(task["assets"], start=1))
    candidates = [
        (index, asset)
        for role in role_priority
        for index, asset in indexed_assets
        if asset["kind"] == role and _drive_file_id(task, index) not in used_file_ids
    ]
    if not candidates:
        candidates = [
            (index, asset)
            for index, asset in indexed_assets
            if _drive_file_id(task, index) not in used_file_ids
        ]
    if not candidates:
        raise ValueError(f"{task['task_id']} has no decoy evidence file")
    replacement["arguments"]["fileId"] = _drive_file_id(task, candidates[0][0])
    replacement["phase"] = "negative_control"
    replacement["control"] = True
    return replacement


def policy_steps(task: dict[str, Any], policy: str) -> list[dict[str, Any]]:
    steps = deepcopy(task["oracle_steps"])
    required_read_signatures = {
        (
            call["tool"],
            json.dumps(call["arguments"], sort_keys=True, separators=(",", ":")),
        )
        for call in task["required_read_calls"]
    }
    if policy == "oracle":
        return steps
    if policy == "noop":
        return []
    if policy == "shortcut":
        return steps[-2:]
    if policy == "state_only":
        return [
            step
            for step in steps
            if step["tool"] != "factorybench.submit_answer"
        ]
    if policy == "incomplete_read":
        omitted = next(
            index
            for index in range(len(steps) - 1, -1, -1)
            if (
                steps[index]["tool"],
                json.dumps(
                    steps[index]["arguments"], sort_keys=True, separators=(",", ":")
                ),
            )
            in required_read_signatures
        )
        return [step for index, step in enumerate(steps) if index != omitted]
    if policy == "write_before_read":
        primary_index = next(
            index
            for index, step in enumerate(steps)
            if step["phase"] == "primary_mutation"
        )
        primary = steps.pop(primary_index)
        context_index = next(
            index
            for index, step in enumerate(steps)
            if step["tool"] == "factorybench.context.get"
        )
        steps.insert(context_index + 1, primary)
        return steps
    if policy == "missing_readback":
        return [
            step
            for step in steps
            if step["phase"] != "post_write_verification"
        ]
    if policy == "unauthorized_write":
        answer_index = next(
            index
            for index, step in enumerate(steps)
            if step["tool"] == "factorybench.submit_answer"
        )
        steps.insert(answer_index, _unauthorized_write_step(task))
        return steps
    if policy == "wrong_value":
        answer_step = next(
            step
            for step in steps
            if step["tool"] == "factorybench.submit_answer"
        )
        answer_step["arguments"] = _wrong_answer(task, decision=False)
        return steps
    if policy == "wrong_decision":
        answer_step = next(
            step
            for step in steps
            if step["tool"] == "factorybench.submit_answer"
        )
        answer_step["arguments"] = _wrong_answer(task, decision=True)
        return steps
    if policy == "wrong_evidence":
        drive_file_counts: dict[str, int] = {}
        for step in steps:
            if step.get("control") and "fileId" in step["arguments"]:
                file_id = str(step["arguments"]["fileId"])
                drive_file_counts[file_id] = drive_file_counts.get(file_id, 0) + 1
        drive_indexes = [
            index
            for index, step in enumerate(steps)
            if step.get("control")
            and step["tool"]
            in {
                "google_drive.files.get",
                "google_drive.files.download",
                "google_drive.files.export",
            }
            and "fileId" in step["arguments"]
            and drive_file_counts[str(step["arguments"]["fileId"])] == 1
            and (
                step["tool"],
                json.dumps(step["arguments"], sort_keys=True, separators=(",", ":")),
            )
            in required_read_signatures
        ]
        if not drive_indexes:
            raise ValueError(f"{task['task_id']} has no required Drive evidence")
        used_file_ids = {
            str(step["arguments"]["fileId"])
            for step in steps
            if "fileId" in step["arguments"]
        }
        omitted = drive_indexes[-1]
        steps[omitted] = _wrong_evidence_step(
            task,
            steps[omitted],
            used_file_ids,
        )
        return steps
    if policy in {"wrong_target", "keyword_stuffing"}:
        natural_tools = {
            "gmail.drafts.create",
            "gmail.messages.send",
            "google_drive.comments.create",
            "slack.chat_postMessage",
        }
        content_tools = natural_tools | {
            "google_sheets.spreadsheets.values.append",
            "google_sheets.spreadsheets.values.update",
        }
        candidates = [
            step
            for step in steps
            if step.get("phase") == "collaboration_mutation"
            and step["tool"] in content_tools
        ]
        target = next(
            (step for step in candidates if step["tool"] in natural_tools),
            candidates[0],
        )
        target_index = next(
            index for index, step in enumerate(steps) if step is target
        )
        readback = next(
            step
            for step in steps[target_index + 1 :]
            if step.get("phase") == "post_write_verification"
        )
        arguments = target["arguments"]
        ordinal = int(task["task_id"].rsplit("-", 1)[1])
        case = task["decision_model"]["case_reference"]
        option = task["decision_model"]["selected_option"]
        completion = task["decision_model"]["selected_completion"]

        if policy == "wrong_target":
            if target["tool"] in {"gmail.drafts.create", "gmail.messages.send"}:
                envelope = arguments.get("message", arguments)
                raw = envelope["raw"]
                decoded = base64.urlsafe_b64decode(
                    raw + "=" * (-len(raw) % 4)
                ).decode("utf-8")
                current_to = next(
                    line for line in decoded.splitlines() if line.startswith("To: ")
                )
                adjacent_mailbox = next(
                    address
                    for address in (
                        "operations.lead@northstar.example",
                        "finance.controls@northstar.example",
                    )
                    if f"To: {address}" != current_to
                )
                decoded = decoded.replace(
                    current_to,
                    f"To: {adjacent_mailbox}",
                    1,
                )
                envelope["raw"] = base64.urlsafe_b64encode(decoded.encode()).decode().rstrip("=")
            elif target["tool"] == "google_drive.comments.create":
                arguments["fileId"] = f"drive-approval-{ordinal:03d}"
                readback["arguments"]["fileId"] = arguments["fileId"]
            elif target["tool"] == "slack.chat_postMessage":
                arguments.pop("thread_ts", None)
                readback["arguments"]["ts"] = f"1768{ordinal:06d}.000900"
            else:
                sheet, cell = str(arguments["range"]).split("!", 1)
                arguments["range"] = (
                    "Control!A1" if sheet == "Audit" else f"{sheet}!A1"
                )
                readback["arguments"]["range"] = arguments["range"]
            return steps

        anchors = f"{case} {option} {completion}"
        if target["tool"] in {"gmail.drafts.create", "gmail.messages.send"}:
            envelope = arguments.get("message", arguments)
            raw = envelope["raw"]
            decoded = base64.urlsafe_b64decode(
                raw + "=" * (-len(raw) % 4)
            ).decode("utf-8")
            headers = decoded.split("\r\n\r\n", 1)[0]
            envelope["raw"] = base64.urlsafe_b64encode(
                f"{headers}\r\n\r\n{anchors}".encode()
            ).decode().rstrip("=")
        elif target["tool"] == "google_drive.comments.create":
            arguments["requestBody"]["content"] = anchors
        elif target["tool"] == "slack.chat_postMessage":
            arguments["text"] = anchors
        else:
            arguments["requestBody"]["values"] = [[anchors]]
        return steps
    raise ValueError(f"unknown policy: {policy}")


def run_episode(task: dict[str, Any], policy: str, database_path: str | Path) -> dict[str, Any]:
    with FactoryWorld.fresh(task, database_path) as world:
        before = world.snapshot()
        for step in policy_steps(task, policy):
            world.call_tool(step["tool"], step["arguments"])
        verification = verify_episode(task, world)
        after = world.snapshot()
        return {
            **verification,
            "policy": policy,
            "trace": world.trace,
            "state_diff": _state_diff(before, after),
        }


def evaluate_policy(
    policy: str,
    tasks: Iterable[dict[str, Any]] | None = None,
    *,
    workdir: str | Path | None = None,
    include_episodes: bool = False,
) -> dict[str, Any]:
    selected = list(tasks if tasks is not None else build_catalog())
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if workdir is None:
        temporary = tempfile.TemporaryDirectory(prefix="factorybench-")
        root = Path(temporary.name)
    else:
        root = Path(workdir)
        root.mkdir(parents=True, exist_ok=True)
    try:
        episodes = [run_episode(task, policy, root / f"{task['task_id']}.db") for task in selected]
    finally:
        if temporary is not None:
            temporary.cleanup()
    mean_score = round(sum(episode["score"] for episode in episodes) / len(episodes), 2)
    strict_passes = sum(1 for episode in episodes if episode["strict_pass"])
    family_scores: dict[str, float] = {}
    for family in sorted({task["family"] for task in selected}):
        task_ids = {task["task_id"] for task in selected if task["family"] == family}
        values = [episode["score"] for episode in episodes if episode["task_id"] in task_ids]
        family_scores[family] = round(sum(values) / len(values), 2)
    result: dict[str, Any] = {
        "policy": policy,
        "metric": "FactoryScore",
        "mean_score": mean_score,
        "strict_passes": strict_passes,
        "task_count": len(selected),
        "family_scores": family_scores,
    }
    if include_episodes:
        result["episodes"] = episodes
    return result


def evaluate_mutation_omissions(tasks: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Prove that every reference mutation is necessary for strict completion."""

    selected = list(tasks if tasks is not None else build_catalog())
    failures: list[dict[str, Any]] = []
    total = 0
    with tempfile.TemporaryDirectory(prefix="factorybench-mutation-omissions-") as temporary:
        root = Path(temporary)
        for task in selected:
            mutable_steps = [
                index
                for index, step in enumerate(task["oracle_steps"])
                if step["tool"] in WRITE_TOOLS - {"factorybench.submit_answer"}
            ]
            for omitted_index in mutable_steps:
                total += 1
                with FactoryWorld.fresh(
                    task,
                    root / f"{task['task_id']}-{omitted_index}.db",
                ) as world:
                    for index, step in enumerate(task["oracle_steps"]):
                        if index != omitted_index:
                            world.call_tool(step["tool"], step["arguments"])
                    verification = verify_episode(task, world)
                if verification["strict_pass"] or verification["score"] == 100.0:
                    failures.append(
                        {
                            "task_id": task["task_id"],
                            "omitted_step": omitted_index,
                            "omitted_tool": task["oracle_steps"][omitted_index]["tool"],
                            "score": verification["score"],
                            "strict_pass": verification["strict_pass"],
                        }
                    )
    return {
        "total": total,
        "detected": total - len(failures),
        "all_detected": not failures,
        "failures": failures,
    }


def qualify(tasks: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    selected = list(tasks if tasks is not None else build_catalog())
    results = [evaluate_policy(policy, selected) for policy in POLICIES]
    oracle = next(result for result in results if result["policy"] == "oracle")
    mutation_omissions = evaluate_mutation_omissions(selected)
    with tempfile.TemporaryDirectory(prefix="factorybench-oracle-") as first_dir, tempfile.TemporaryDirectory(prefix="factorybench-replay-") as second_dir:
        first = [
            run_episode(task, "oracle", Path(first_dir) / f"{task['task_id']}.db")
            for task in selected
        ]
        second = [
            run_episode(task, "oracle", Path(second_dir) / f"{task['task_id']}.db")
            for task in selected
        ]
    exact_matches = sum(left == right for left, right in zip(first, second, strict=True))
    deterministic = exact_matches == len(selected)
    result_by_policy = {result["policy"]: result for result in results}
    negative_controls = {
        policy: {
            "executions": len(selected),
            "false_accepts": result_by_policy[policy]["strict_passes"],
            "correct_rejections": len(selected)
            - result_by_policy[policy]["strict_passes"],
            "mean_score": result_by_policy[policy]["mean_score"],
        }
        for policy in NEGATIVE_POLICIES
    }
    negatives_below_oracle = all(
        result_by_policy[policy]["mean_score"] < oracle["mean_score"]
        for policy in NEGATIVE_POLICIES
    )
    no_false_accepts = not any(
        result["false_accepts"] for result in negative_controls.values()
    )
    qualification_passed = (
        oracle["strict_passes"] == len(selected)
        and oracle["mean_score"] == 100.0
        and deterministic
        and no_false_accepts
        and negatives_below_oracle
        and mutation_omissions["all_detected"]
    )
    return {
        "schema_version": "factorybench.qualification.v3",
        "benchmark": "FactoryBench-100",
        "version": selected[0]["benchmark_version"] if selected else None,
        "metric": "FactoryScore",
        "task_count": len(selected),
        "executions": len(selected) * (2 + len(NEGATIVE_POLICIES)),
        "qualification_passed": qualification_passed,
        "release_passed": qualification_passed,
        "oracle_all_strict": oracle["strict_passes"] == len(selected),
        "oracle": {
            "executions": len(selected),
            "passes": oracle["strict_passes"],
            "failures": len(selected) - oracle["strict_passes"],
            "mean_score": oracle["mean_score"],
        },
        "determinism_sample_size": len(first),
        "deterministic_replay": deterministic,
        "determinism": {
            "replays": len(selected),
            "exact_episode_matches": exact_matches,
            "mismatches": len(selected) - exact_matches,
        },
        "negative_controls_below_oracle": negatives_below_oracle,
        "negative_controls": negative_controls,
        "mutation_omissions": mutation_omissions,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate FactoryBench-100 policies")
    parser.add_argument("--policy", choices=POLICIES)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    tasks = build_catalog()
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be at least 1")
        tasks = tasks[: args.limit]
    result = evaluate_policy(args.policy, tasks, include_episodes=False) if args.policy else qualify(tasks)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
