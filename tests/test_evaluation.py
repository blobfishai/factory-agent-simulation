from __future__ import annotations

from copy import deepcopy
import tempfile
from pathlib import Path

import pytest

from factorybench.catalog import FAMILIES, build_catalog
from factorybench.evaluation import evaluate_policy, qualify, run_episode
from factorybench.world import FactoryWorld


@pytest.fixture(scope="module")
def tasks():
    return build_catalog()


def test_reference_episode_strictly_passes_each_family(tasks) -> None:
    representatives = [next(task for task in tasks if task["family"] == family) for family in FAMILIES]
    with tempfile.TemporaryDirectory() as temporary:
        for task in representatives:
            episode = run_episode(task, "oracle", Path(temporary) / f"{task['task_id']}.db")
            assert episode["score"] == 100.0
            assert episode["strict_pass"] is True
            assert all(entry["success"] for entry in episode["trace"])


def test_environment_rejects_write_before_required_reads(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    first_write = next(step for step in task["oracle_steps"] if not step.get("control"))
    with FactoryWorld.fresh(task, tmp_path / "world.db") as world:
        assert world.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        result = world.call_tool(first_write["tool"], first_write["arguments"])
        assert "read-before-write control failed" in result["error"]
        assert world.connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0


def test_preflight_reads_are_bound_to_task_arguments(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    control_steps = [step for step in task["oracle_steps"] if step.get("control")]
    first_write = next(step for step in task["oracle_steps"] if not step.get("control"))
    with FactoryWorld.fresh(task, tmp_path / "wrong-preflight.db") as world:
        wrong_policy = world.call_tool("search_documents", {"category": "supplier_selection"})
        assert "error" not in wrong_policy
        for step in control_steps:
            if step["tool"] == "search_documents":
                continue
            assert "error" not in world.call_tool(step["tool"], step["arguments"])
        result = world.call_tool(first_write["tool"], first_write["arguments"])
    assert "search_documents" in result["error"]
    assert "order_release" in result["error"]


def test_supplier_promised_date_must_meet_quote_and_need_by(tasks, tmp_path: Path) -> None:
    task = next(task for task in tasks if task["family"] == "supplier_selection")
    with FactoryWorld.fresh(task, tmp_path / "late-po.db") as world:
        for step in task["oracle_steps"]:
            if step["tool"] == "create_purchase_order":
                arguments = {**step["arguments"], "promised_date": "2099-12-31"}
                result = world.call_tool(step["tool"], arguments)
                break
            assert "error" not in world.call_tool(step["tool"], step["arguments"])
    assert "promised date" in result["error"]


def test_numeric_answers_use_decimal_normalization(tasks, tmp_path: Path) -> None:
    task = deepcopy(next(task for task in tasks if task["family"] == "supplier_selection"))
    task["oracle_steps"][-1]["arguments"]["total_amount"] = "1539.20"
    episode = run_episode(task, "oracle", tmp_path / "decimal-answer.db")
    assert episode["score"] == 100.0
    assert episode["strict_pass"] is True


def test_negative_controls_are_diagnostic(tasks) -> None:
    representatives = [next(task for task in tasks if task["family"] == family) for family in FAMILIES]
    oracle = evaluate_policy("oracle", representatives)
    incomplete = evaluate_policy("incomplete_workflow", representatives)
    read_only = evaluate_policy("read_only", representatives)
    no_control = evaluate_policy("no_control", representatives)
    assert oracle["mean_score"] == 100.0
    assert oracle["mean_score"] > incomplete["mean_score"] > read_only["mean_score"] > no_control["mean_score"]


def test_full_release_qualification_passes(tasks) -> None:
    report = qualify(tasks)
    assert report["qualification_passed"] is True
    assert report["oracle_all_strict"] is True
    assert report["deterministic_replay"] is True
    assert report["negative_controls_below_oracle"] is True
    assert report["mutation_omissions"] == {
        "total": 240,
        "detected": 240,
        "all_detected": True,
        "failures": [],
    }


def test_subset_qualification_bounds_the_determinism_sample(tasks) -> None:
    report = qualify(tasks[:1])
    assert report["qualification_passed"] is True
    assert report["determinism_sample_size"] == 1
