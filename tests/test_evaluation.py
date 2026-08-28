from __future__ import annotations

from copy import deepcopy
import tempfile
from pathlib import Path

import pytest

from factorybench.catalog import FAMILIES, build_catalog
from factorybench.evaluation import evaluate_policy, qualify, run_episode
from factorybench.world import FactoryWorld, READ_TOOLS, WRITE_TOOLS


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
    first_write = next(step for step in task["oracle_steps"] if step["tool"] in WRITE_TOOLS)
    with FactoryWorld.fresh(task, tmp_path / "world.db") as world:
        assert world.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        result = world.call_tool(first_write["tool"], first_write["arguments"])
        assert "read-before-write control failed" in result["error"]
        assert world.connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0


def test_preflight_requires_each_successful_task_bound_read_tool(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    control_steps = [step for step in task["oracle_steps"] if step["tool"] in READ_TOOLS]
    omitted = control_steps[1]
    first_write = next(step for step in task["oracle_steps"] if step["tool"] in WRITE_TOOLS)
    with FactoryWorld.fresh(task, tmp_path / "missing-evidence.db") as world:
        for step in control_steps:
            if step is omitted:
                continue
            assert "error" not in world.call_tool(step["tool"], step["arguments"])
        result = world.call_tool(first_write["tool"], first_write["arguments"])
    assert omitted["tool"] in result["error"]


def test_collection_reads_accept_realistic_alternate_queries(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    control_steps = [step for step in task["oracle_steps"] if step["tool"] in READ_TOOLS]
    first_write = next(step for step in task["oracle_steps"] if step["tool"] in WRITE_TOOLS)
    with FactoryWorld.fresh(task, tmp_path / "alternate-query.db") as world:
        for step in control_steps:
            arguments = step["arguments"]
            if step["tool"] == "gmail.messages.list":
                arguments = {
                    "userId": "me",
                    "q": "after:2026/01/01 before:2026/02/01",
                    "maxResults": 100,
                }
            result = world.call_tool(step["tool"], arguments)
            assert "error" not in result
        assert "error" not in world.call_tool(first_write["tool"], first_write["arguments"])


def test_item_reads_keep_immutable_identifier_semantics(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    with FactoryWorld.fresh(task, tmp_path / "wrong-id.db") as world:
        result = world.call_tool(
            "gmail.messages.get",
            {"userId": "me", "id": "msg-does-not-exist", "format": "full"},
        )
    assert "record not found" in result["error"]


def test_listed_drive_assets_are_retrievable_and_sheet_ranges_are_flexible(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    with FactoryWorld.fresh(task, tmp_path / "asset-discovery.db") as world:
        context = world.call_tool("factorybench.context.get", {})
        assert context["reference_records"]["google_sheets"]["outcome_write_range"] == "Control!H3"
        listed = world.call_tool(
            "google_drive.files.list",
            {"q": "trashed = false", "pageSize": 100},
        )
        assert len(listed["files"]) == 12
        for file in listed["files"]:
            downloaded = world.call_tool(
                "google_drive.files.download",
                {"fileId": file["id"]},
            )
            assert downloaded["id"] == file["id"]
            assert downloaded["content"]
        values = world.call_tool(
            "google_sheets.spreadsheets.values.get",
            {
                "spreadsheetId": "sheet-001",
                "range": "Control!A1:H2",
                "valueRenderOption": "UNFORMATTED_VALUE",
            },
        )
        assert values["values"][1][0] == "CASE-001"


def test_oracle_writes_require_the_approved_documented_payload(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    control_steps = [step for step in task["oracle_steps"] if step["tool"] in READ_TOOLS]
    primary_write = next(
        step for step in task["oracle_steps"] if step["tool"] == task["workflow"]["primary_write"]
    )
    altered = deepcopy(primary_write["arguments"])
    altered["requestBody"]["PlannedCompletionDate"] = "2099-01-01"
    with FactoryWorld.fresh(task, tmp_path / "wrong-payload.db") as world:
        for step in control_steps:
            assert "error" not in world.call_tool(step["tool"], step["arguments"])
        result = world.call_tool(primary_write["tool"], altered)
    assert "does not match the approved value" in result["error"]


def test_input_contract_rejects_legacy_invoice_id_shape(tasks, tmp_path: Path) -> None:
    task = next(task for task in tasks if any(step["tool"] == "oracle_fusion.invoices.validate" for step in task["oracle_steps"]))
    with FactoryWorld.fresh(task, tmp_path / "invoice-contract.db") as world:
        result = world.call_tool("oracle_fusion.invoices.validate", {"invoice_id": "INV-1"})
    assert "unexpected properties" in result["error"] or "missing required" in result["error"]


def test_numeric_answers_use_decimal_normalization(tasks, tmp_path: Path) -> None:
    task = deepcopy(next(task for task in tasks if any(isinstance(value, float) for value in task["expected"]["answer"].values())))
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
        "total": 300,
        "detected": 300,
        "all_detected": True,
        "failures": [],
    }


def test_subset_qualification_bounds_the_determinism_sample(tasks) -> None:
    report = qualify(tasks[:1])
    assert report["qualification_passed"] is True
    assert report["determinism_sample_size"] == 1
