"""Deterministic FactoryScore evaluation and qualification baselines."""

from __future__ import annotations

import argparse
import json
import random
import tempfile
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

POLICIES = ("oracle", "incomplete_workflow", "read_only", "no_control")


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

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    passed_weight = sum(check["weight"] for check in checks if check["passed"])
    total_weight = sum(check["weight"] for check in checks)
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


def policy_steps(task: dict[str, Any], policy: str) -> list[dict[str, Any]]:
    steps = task["oracle_steps"]
    if policy == "oracle":
        return steps
    if policy == "read_only":
        return [step for step in steps if step["tool"] in READ_TOOLS]
    if policy == "no_control":
        return [step for step in steps if not step.get("control")]
    if policy == "incomplete_workflow":
        mutable = [index for index, step in enumerate(steps) if step["tool"] in WRITE_TOOLS - {"factorybench.submit_answer"}]
        if not mutable:
            return steps[:-1]
        omitted = mutable[-1]
        return [step for index, step in enumerate(steps) if index != omitted]
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
    with tempfile.TemporaryDirectory(prefix="factorybench-determinism-") as first_dir, tempfile.TemporaryDirectory(prefix="factorybench-determinism-") as second_dir:
        sample = random.Random(100).sample(selected, min(10, len(selected)))
        first = [run_episode(task, "oracle", Path(first_dir) / f"{task['task_id']}.db") for task in sample]
        second = [run_episode(task, "oracle", Path(second_dir) / f"{task['task_id']}.db") for task in sample]
    deterministic = all(
        left["score"] == right["score"]
        and left["strict_pass"] == right["strict_pass"]
        and left["state_diff"] == right["state_diff"]
        for left, right in zip(first, second, strict=True)
    )
    negatives_below_oracle = all(result["mean_score"] < oracle["mean_score"] for result in results if result["policy"] != "oracle")
    return {
        "benchmark": "FactoryBench-100",
        "metric": "FactoryScore",
        "task_count": len(selected),
        "qualification_passed": oracle["strict_passes"] == len(selected)
        and oracle["mean_score"] == 100.0
        and deterministic
        and negatives_below_oracle
        and mutation_omissions["all_detected"],
        "oracle_all_strict": oracle["strict_passes"] == len(selected),
        "determinism_sample_size": len(first),
        "deterministic_replay": deterministic,
        "negative_controls_below_oracle": negatives_below_oracle,
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
