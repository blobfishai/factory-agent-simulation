from __future__ import annotations

from copy import deepcopy
import json
import tempfile
from pathlib import Path

import pytest

from factorybench.catalog import FAMILIES, build_catalog
from factorybench.evaluation import evaluate_policy, qualify, run_episode, verify_episode
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


def test_environment_does_not_use_an_observer_only_read_gate(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    first_write = next(step for step in task["oracle_steps"] if step["tool"] in WRITE_TOOLS)
    with FactoryWorld.fresh(task, tmp_path / "world.db") as world:
        assert world.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        result = world.call_tool(first_write["tool"], first_write["arguments"])
        assert "error" not in result
        assert world.connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
        verdict = verify_episode(task, world)
    investigation_checks = [
        check for check in verdict["checks"] if check["id"].startswith("investigation_")
    ]
    assert investigation_checks
    assert not any(check["passed"] for check in investigation_checks)


def test_verifier_scores_each_missing_business_investigation(tasks, tmp_path: Path) -> None:
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
        assert "error" not in result
        verdict = verify_episode(task, world)
    missing = next(check for check in verdict["checks"] if check["id"] == "investigation_02")
    assert missing["passed"] is False
    assert "task-scoped correspondence" in missing["description"]


def test_collection_reads_accept_realistic_alternate_queries(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    control_steps = [step for step in task["oracle_steps"] if step["control"]]
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
        verdict = verify_episode(task, world)
    gmail_discovery = next(
        check for check in verdict["checks"] if check["id"] == "investigation_02"
    )
    assert gmail_discovery["passed"] is True


def test_unrelated_oracle_collection_search_returns_an_empty_provider_page(
    tasks, tmp_path: Path
) -> None:
    task = next(task for task in tasks if task["task_id"] == "factorybench-016")
    assert "oracle_fusion.sales_orders.list" not in task["required_reads"]
    with FactoryWorld.fresh(task, tmp_path / "empty-oracle-collection.db") as world:
        result = world.call_tool(
            "oracle_fusion.sales_orders.list",
            {
                "q": "OrderNumber='NOT-A-MATCH'",
                "limit": 50,
                "onlyData": True,
            },
        )
    assert result == {
        "items": [],
        "count": 0,
        "hasMore": False,
        "limit": 50,
        "offset": 0,
        "links": [],
    }


def test_repeating_one_drive_file_cannot_satisfy_distinct_discoveries(
    tasks, tmp_path: Path
) -> None:
    task = tasks[0]
    first_write = next(step for step in task["oracle_steps"] if step["tool"] in WRITE_TOOLS)
    with FactoryWorld.fresh(task, tmp_path / "repeated-drive-file.db") as world:
        for step in task["oracle_steps"]:
            if not step["control"]:
                continue
            arguments = deepcopy(step["arguments"])
            if step["tool"] in {
                "google_drive.files.get",
                "google_drive.files.download",
                "google_drive.files.export",
            }:
                arguments["fileId"] = "drive-001"
            assert "error" not in world.call_tool(step["tool"], arguments)
        assert "error" not in world.call_tool(first_write["tool"], first_write["arguments"])
        verdict = verify_episode(task, world)

    drive_discoveries = [
        check
        for check in verdict["checks"]
        if check["id"].startswith("investigation_")
        and (
            "Opened the" in check["description"]
            or "approval record" in check["description"]
        )
    ]
    assert len(drive_discoveries) >= 5
    assert sum(not check["passed"] for check in drive_discoveries) >= 4


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
        assert context["reference_records"]["google_sheets"]["decision_range"] == "Control!A1:I50"
        assert context["reference_records"]["google_sheets"]["audit_append_range"] == "Audit!A:G"
        listed = world.call_tool(
            "google_drive.files.list",
            {"q": "trashed = false", "pageSize": 100},
        )
        assert len(listed["files"]) == 12
        metadata = world.call_tool(
            "google_drive.files.get",
            {"fileId": listed["files"][0]["id"], "fields": "id,name,mimeType"},
        )
        assert "content" not in metadata
        media = world.call_tool(
            "google_drive.files.get",
            {"fileId": listed["files"][0]["id"], "alt": "media"},
        )
        assert media["content"]
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
        assert values["range"] == "Control!A1:H2"
        assert len(values["values"]) == 2
        assert all(len(row) <= 8 for row in values["values"])
        assert values["values"][1][0] == "CASE-001"


def test_oracle_accepts_business_wrong_values_and_verifier_detects_them(
    tasks, tmp_path: Path
) -> None:
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
        assert "error" not in result
        readback = next(
            step
            for step in task["oracle_steps"]
            if step["phase"] == "post_write_verification"
        )
        observed = world.call_tool(readback["tool"], readback["arguments"])
        assert observed["PlannedCompletionDate"] == "2099-01-01"
        verdict = verify_episode(task, world)
        state = world.connection.execute(
            "SELECT payload_json FROM resource_state WHERE task_id = ? AND revision = 1",
            (task["task_id"],),
        ).fetchone()

    assert json.loads(state["payload_json"])["arguments"] == altered
    mutation = next(check for check in verdict["checks"] if check["id"] == "mutation_01")
    assert mutation["passed"] is False
    assert (
        mutation["evidence"]["payload_mismatches"]
        ["payload.arguments.requestBody.PlannedCompletionDate"]["actual"]
        == "2099-01-01"
    )
    readback_check = next(
        check
        for check in verdict["checks"]
        if check["id"] == "verify_primary_oracle_state"
    )
    assert readback_check["passed"] is False
    assert next(
        check for check in verdict["checks"] if check["id"] == "no_rejected_mutation"
    )["passed"] is True


def test_oracle_patch_can_be_corrected_after_an_incomplete_transition(
    tasks, tmp_path: Path
) -> None:
    task = tasks[0]
    primary_write = next(
        step for step in task["oracle_steps"] if step["tool"] == task["workflow"]["primary_write"]
    )
    partial = {
        "WorkOrderId": primary_write["arguments"]["WorkOrderId"],
        "requestBody": {
            "PlannedStartDate": primary_write["arguments"]["requestBody"]["PlannedStartDate"],
            "PlannedCompletionDate": primary_write["arguments"]["requestBody"]["PlannedCompletionDate"],
        },
    }
    with FactoryWorld.fresh(task, tmp_path / "partial-patch.db") as world:
        result = world.call_tool(primary_write["tool"], partial)
        assert "error" not in result
        partial_verdict = verify_episode(task, world)
        assert next(
            check
            for check in partial_verdict["checks"]
            if check["id"] == "mutation_01"
        )["passed"] is False
        corrected = world.call_tool(primary_write["tool"], primary_write["arguments"])
        assert "error" not in corrected
        rows = world.connection.execute(
            "SELECT status, effective_at, payload_json FROM resource_state WHERE task_id = ? AND revision = 1",
            (task["task_id"],),
        ).fetchall()
        readback = next(
            step
            for step in task["oracle_steps"]
            if step["phase"] == "post_write_verification"
        )
        assert "error" not in world.call_tool(readback["tool"], readback["arguments"])
        corrected_verdict = verify_episode(task, world)
    assert len(rows) == 1
    assert json.loads(rows[0]["payload_json"])["arguments"] == primary_write["arguments"]
    assert next(
        check
        for check in corrected_verdict["checks"]
        if check["id"] == "mutation_01"
    )["passed"] is True


def test_provider_readback_observes_the_committed_state_and_is_graded(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    primary_write = next(
        step for step in task["oracle_steps"] if step["phase"] == "primary_mutation"
    )
    readback = next(
        step for step in task["oracle_steps"] if step["phase"] == "post_write_verification"
    )
    expected = task["post_write_verifications"][0]["expected_result_contains"]
    with FactoryWorld.fresh(task, tmp_path / "readback.db") as world:
        before = world.call_tool(readback["tool"], readback["arguments"])
        assert before["WorkOrderStatusCode"] == "ORA_RELEASED"
        assert before["PlannedStartDate"] != expected["PlannedStartDate"]
        assert "StatusCode" not in before
        assert "error" not in world.call_tool(primary_write["tool"], primary_write["arguments"])
        after = world.call_tool(readback["tool"], readback["arguments"])
        assert all(after[field] == value for field, value in expected.items())
        assert "StatusCode" not in after
        verdict = verify_episode(task, world)
    check = next(
        check for check in verdict["checks"] if check["id"] == "verify_primary_oracle_state"
    )
    assert check["passed"] is True


def test_create_readback_materializes_a_record_only_after_the_write(tasks, tmp_path: Path) -> None:
    task = next(task for task in tasks if task["task_id"] == "factorybench-031")
    primary_write = next(
        step for step in task["oracle_steps"] if step["phase"] == "primary_mutation"
    )
    readback = next(
        step for step in task["oracle_steps"] if step["phase"] == "post_write_verification"
    )
    verification = task["post_write_verifications"][0]
    identity = verification["target_identity"]

    def target_items(result):
        return [
            item
            for item in result["items"]
            if all(item.get(field) == value for field, value in identity.items())
        ]

    with FactoryWorld.fresh(task, tmp_path / "materialized-create.db") as world:
        before = world.call_tool(readback["tool"], readback["arguments"])
        assert target_items(before) == []
        assert "error" not in world.call_tool(primary_write["tool"], primary_write["arguments"])
        after = world.call_tool(readback["tool"], readback["arguments"])
        assert len(target_items(after)) == 1
        assert all(
            target_items(after)[0][field] == value
            for field, value in verification["expected_result_contains"].items()
        )
        verdict = verify_episode(task, world)
    check = next(
        check for check in verdict["checks"] if check["id"] == "verify_primary_oracle_state"
    )
    assert check["passed"] is True


def test_every_primary_write_changes_a_provider_readback_field(tasks, tmp_path: Path) -> None:
    def target(result, identity):
        if isinstance(result, dict) and isinstance(result.get("items"), list):
            return next(
                (
                    item
                    for item in result["items"]
                    if all(item.get(field) == value for field, value in identity.items())
                ),
                None,
            )
        return result

    for task in tasks:
        write = next(
            step
            for step in task["oracle_steps"]
            if step["phase"] == "primary_mutation"
        )
        readback = next(
            step
            for step in task["oracle_steps"]
            if step["phase"] == "post_write_verification"
        )
        verification = task["post_write_verifications"][0]
        with FactoryWorld.fresh(task, tmp_path / f"{task['task_id']}-transition.db") as world:
            references = world.call_tool("factorybench.context.get", {})[
                "reference_records"
            ]
            for step in task["oracle_steps"]:
                if step["tool"] == "google_sheets.spreadsheets.values.update":
                    assert step["arguments"]["range"] == references["google_sheets"][
                        "outcome_write_range"
                    ]
                elif step["tool"] == "google_sheets.spreadsheets.values.append":
                    assert step["arguments"]["range"] == references["google_sheets"][
                        "audit_append_range"
                    ]
                elif step["tool"] == "google_drive.comments.create":
                    assert step["arguments"]["fileId"] == references["google_drive"][
                        "primary_file_id"
                    ]
            before = target(
                world.call_tool(readback["tool"], readback["arguments"]),
                verification["target_identity"],
            )
            assert "error" not in world.call_tool(write["tool"], write["arguments"])
            after = target(
                world.call_tool(readback["tool"], readback["arguments"]),
                verification["target_identity"],
            )
        assert after is not None
        changed = [
            field
            for field, expected in verification["expected_result_contains"].items()
            if before is None or before.get(field) != expected
        ]
        assert changed, f"{task['task_id']} did not produce a business state transition"


def test_write_acknowledgement_without_provider_readback_is_incomplete(tasks, tmp_path: Path) -> None:
    task = tasks[0]
    with FactoryWorld.fresh(task, tmp_path / "missing-readback.db") as world:
        for step in task["oracle_steps"]:
            if step["phase"] == "post_write_verification":
                continue
            assert "error" not in world.call_tool(step["tool"], step["arguments"])
        verdict = verify_episode(task, world)
    check = next(
        check for check in verdict["checks"] if check["id"] == "verify_primary_oracle_state"
    )
    assert check["passed"] is False


def test_input_contract_rejects_legacy_invoice_id_shape(tasks, tmp_path: Path) -> None:
    task = next(task for task in tasks if any(step["tool"] == "oracle_fusion.invoices.validate" for step in task["oracle_steps"]))
    with FactoryWorld.fresh(task, tmp_path / "invoice-contract.db") as world:
        result = world.call_tool("oracle_fusion.invoices.validate", {"invoice_id": "INV-1"})
    assert "unexpected properties" in result["error"] or "missing required" in result["error"]


@pytest.mark.parametrize(
    ("tool_name", "field", "wrong_value"),
    [
        ("oracle_fusion.work_order_operations.update", "PlannedCompletionDate", "2099-01-01"),
        ("oracle_fusion.invoices.validate", "Supplier", "Unrelated Valid Supplier"),
    ],
)
def test_provider_does_not_reveal_gold_values_for_valid_business_mistakes(
    tasks,
    tmp_path: Path,
    tool_name: str,
    field: str,
    wrong_value: str,
) -> None:
    task = next(
        task
        for task in tasks
        if task["workflow"]["primary_write"] == tool_name
    )
    write = next(
        step for step in task["oracle_steps"] if step["phase"] == "primary_mutation"
    )
    wrong = deepcopy(write["arguments"])
    wrong["requestBody"][field] = wrong_value
    with FactoryWorld.fresh(task, tmp_path / f"{task['task_id']}-wrong-valid.db") as world:
        response = world.call_tool(tool_name, wrong)
        assert "error" not in response
        verdict = verify_episode(task, world)
        mutation = next(
            check for check in verdict["checks"] if check["id"] == "mutation_01"
        )
        assert mutation["passed"] is False
        assert next(
            check
            for check in verdict["checks"]
            if check["id"] == "no_rejected_mutation"
        )["passed"] is True
        assert "error" not in world.call_tool(tool_name, write["arguments"])
        corrected = verify_episode(task, world)
        assert next(
            check
            for check in corrected["checks"]
            if check["id"] == "mutation_01"
        )["passed"] is True


@pytest.mark.parametrize(
    ("task_id", "wrong_fields", "readback_passes"),
    [
        (
            "factorybench-016",
            {
                "WorkCenterCode": "WC-ALT-WRONG",
                "PlannedStartDate": "2099-01-15",
            },
            False,
        ),
        (
            "factorybench-024",
            {
                "DocumentName": "WRONG-BUT-VALID-R4",
                "DocumentNumber": "WRONG-REFERENCE-024",
                "Description": "A schema-valid but unsupported diagnostic reference.",
            },
            True,
        ),
    ],
)
def test_harbor_slim_runtime_preserves_actual_oracle_payloads(
    tasks,
    tmp_path: Path,
    task_id: str,
    wrong_fields: dict[str, str],
    readback_passes: bool,
) -> None:
    """A private Harbor sidecar must not canonicalize a model's wrong write."""

    full_task = next(task for task in tasks if task["task_id"] == task_id)
    write = next(
        step
        for step in full_task["oracle_steps"]
        if step["phase"] == "primary_mutation"
    )
    readback = next(
        step
        for step in full_task["oracle_steps"]
        if step["phase"] == "post_write_verification"
    )
    verification = full_task["post_write_verifications"][0]
    wrong = deepcopy(write["arguments"])
    wrong["requestBody"].update(wrong_fields)

    slim_task = deepcopy(full_task)
    slim_task.pop("oracle_steps")
    with FactoryWorld.fresh(slim_task, tmp_path / f"{task_id}-slim.db") as world:
        acknowledgement = world.call_tool(write["tool"], wrong)
        assert "error" not in acknowledgement
        for field, value in wrong_fields.items():
            if field in acknowledgement:
                assert acknowledgement[field] == value

        result = world.call_tool(readback["tool"], readback["arguments"])
        records = result.get("items", [result])
        target = next(
            record
            for record in records
            if all(
                record.get(key) == value
                for key, value in verification["target_identity"].items()
            )
        )
        for field, value in wrong_fields.items():
            if field in target:
                assert target[field] == value

        verdict = verify_episode(slim_task, world)
        assert next(
            check for check in verdict["checks"] if check["id"] == "mutation_01"
        )["passed"] is False
        assert next(
            check
            for check in verdict["checks"]
            if check["id"] == "verify_primary_oracle_state"
        )["passed"] is readback_passes


def test_natural_task_scoped_provider_prose_is_not_exact_string_graded(
    tasks,
    tmp_path: Path,
) -> None:
    task = deepcopy(
        next(task for task in tasks if task["task_id"] == "factorybench-024")
    )
    write = next(
        step for step in task["oracle_steps"] if step["phase"] == "primary_mutation"
    )
    readback = next(
        step
        for step in task["oracle_steps"]
        if step["phase"] == "post_write_verification"
    )
    natural = deepcopy(write["arguments"])
    natural["requestBody"].update(
        {
            "DocumentName": "CASE-024 vendor diagnostic report, revision R4",
            "DocumentNumber": "VENDOR-DIAG-ASSET-024",
            "Description": (
                "Linked the checksum-matched diagnostic report to NS-000024; "
                "the archived and wrong-asset files remain excluded."
            ),
        }
    )

    with FactoryWorld.fresh(task, tmp_path / "natural-provider-prose.db") as world:
        world.call_tool(write["tool"], natural)
        world.call_tool(readback["tool"], readback["arguments"])
        verdict = verify_episode(task, world)

    assert next(
        check for check in verdict["checks"] if check["id"] == "mutation_01"
    )["passed"] is True
    assert next(
        check
        for check in verdict["checks"]
        if check["id"] == "verify_primary_oracle_state"
    )["passed"] is True


def test_optional_operation_name_does_not_require_an_internal_case_token(
    tasks,
    tmp_path: Path,
) -> None:
    task = deepcopy(
        next(task for task in tasks if task["task_id"] == "factorybench-016")
    )
    write = next(
        step for step in task["oracle_steps"] if step["phase"] == "primary_mutation"
    )
    readback = next(
        step
        for step in task["oracle_steps"]
        if step["phase"] == "post_write_verification"
    )
    natural = deepcopy(write["arguments"])
    natural["requestBody"]["OperationName"] = (
        "Reroute final assembly to the qualified alternate work center"
    )

    with FactoryWorld.fresh(task, tmp_path / "natural-operation-name.db") as world:
        world.call_tool(write["tool"], natural)
        world.call_tool(readback["tool"], readback["arguments"])
        verdict = verify_episode(task, world)

    assert next(
        check for check in verdict["checks"] if check["id"] == "mutation_01"
    )["passed"] is True
    assert next(
        check
        for check in verdict["checks"]
        if check["id"] == "verify_primary_oracle_state"
    )["passed"] is True


def test_unauthorized_extra_provider_fields_fail_mutation_containment(
    tasks,
    tmp_path: Path,
) -> None:
    task = deepcopy(
        next(task for task in tasks if task["task_id"] == "factorybench-001")
    )
    write = next(
        step for step in task["oracle_steps"] if step["phase"] == "primary_mutation"
    )
    readback = next(
        step
        for step in task["oracle_steps"]
        if step["phase"] == "post_write_verification"
    )
    overbroad = deepcopy(write["arguments"])
    overbroad["requestBody"]["WorkOrderQuantity"] = 360

    with FactoryWorld.fresh(task, tmp_path / "overbroad-provider-write.db") as world:
        response = world.call_tool(write["tool"], overbroad)
        assert "error" not in response
        world.call_tool(readback["tool"], readback["arguments"])
        verdict = verify_episode(task, world)

    mutation = next(
        check for check in verdict["checks"] if check["id"] == "mutation_01"
    )
    assert mutation["passed"] is False
    assert mutation["evidence"]["unexpected_payload_paths"] == [
        "requestBody.WorkOrderQuantity"
    ]
    assert next(
        check
        for check in verdict["checks"]
        if check["id"] == "verify_primary_oracle_state"
    )["passed"] is False


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
    assert oracle["mean_score"] > incomplete["mean_score"] > no_control["mean_score"] > read_only["mean_score"]


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
