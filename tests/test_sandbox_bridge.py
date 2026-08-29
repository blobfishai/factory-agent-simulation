from __future__ import annotations

import json
from pathlib import Path

from factorybench.catalog import build_catalog
from factorybench.evaluation import verify_episode
from factorybench.sandbox_bridge import _run
from factorybench.world import FactoryWorld


def _atomic_check(verdict: dict, check_id: str) -> dict:
    return next(
        subcheck
        for milestone in verdict["checks"]
        for subcheck in milestone.get("evidence", {}).get("subchecks", [milestone])
        if subcheck["id"] == check_id
    )


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


def test_sandbox_bridge_scores_missing_investigation_without_blocking_business_api(tmp_path: Path) -> None:
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
    assert result["is_error"] is False

    evidence = _run(bundle, session, {"action": "inspect"})
    assert evidence["verification"]["strict_pass"] is False
    investigations = [
        check
        for check in evidence["verification"]["checks"]
        if check["id"].startswith("investigation_")
    ]
    assert investigations
    assert not any(check["passed"] for check in investigations)
    assert evidence["verification"]["checks"][-1]["id"] == "no_rejected_mutation"
    assert evidence["verification"]["checks"][-1]["passed"] is True


def test_provider_reads_reflect_actual_collaboration_writes(tmp_path: Path) -> None:
    task = build_catalog()[0]
    with FactoryWorld.fresh(task, tmp_path / "world.db") as world:
        sheet_write = next(
            step
            for step in task["oracle_steps"]
            if step["tool"] == "google_sheets.spreadsheets.values.update"
        )
        written_values = [[
            "CASE-001 | standard plan | 2026-01-20 | protected WC-2 calendar"
        ]]
        sheet_arguments = {
            **sheet_write["arguments"],
            "requestBody": {
                **sheet_write["arguments"]["requestBody"],
                "values": written_values,
            },
        }
        update = world.call_tool(sheet_write["tool"], sheet_arguments)
        assert update["updatedData"]["values"] == written_values
        readback = world.call_tool(
            "google_sheets.spreadsheets.values.get",
            {
                "spreadsheetId": sheet_arguments["spreadsheetId"],
                "range": sheet_arguments["range"],
                "valueRenderOption": "UNFORMATTED_VALUE",
            },
        )
        assert readback["values"] == written_values

        draft_write = next(
            step
            for step in task["oracle_steps"]
            if step["tool"] == "gmail.drafts.create"
        )
        created = world.call_tool(draft_write["tool"], draft_write["arguments"])
        draft = world.call_tool(
            "gmail.drafts.get",
            {"userId": "me", "id": created["id"], "format": "raw"},
        )
        message = world.call_tool(
            "gmail.messages.get",
            {"userId": "me", "id": created["message"]["id"], "format": "raw"},
        )
        drafts = world.call_tool(
            "gmail.messages.list",
            {"userId": "me", "q": "in:drafts \"CASE-001\"", "maxResults": 20},
        )
        assert draft["message"]["raw"] == draft_write["arguments"]["message"]["raw"]
        assert message["raw"] == draft_write["arguments"]["message"]["raw"]
        assert drafts == {
            "messages": [{"id": "draft-msg-001", "threadId": "thread-001"}],
            "resultSizeEstimate": 1,
        }


def test_every_listed_gmail_message_is_retrievable_with_its_real_thread_shape(
    tmp_path: Path,
) -> None:
    task = build_catalog()[0]
    with FactoryWorld.fresh(task, tmp_path / "gmail-thread.db") as world:
        listed = world.call_tool(
            "gmail.messages.list",
            {"userId": "me", "q": '"CASE-001"', "maxResults": 20},
        )
        messages = [
            world.call_tool(
                "gmail.messages.get",
                {"userId": "me", "id": item["id"], "format": "full"},
            )
            for item in listed["messages"]
        ]
        thread = world.call_tool(
            "gmail.threads.get",
            {"userId": "me", "id": "thread-001", "format": "full"},
        )
        attachment = world.call_tool(
            "gmail.messages.attachments.get",
            {"userId": "me", "messageId": "msg-001-1", "id": "att-001"},
        )

    assert [message["id"] for message in messages] == [
        "msg-001",
        "msg-001-1",
        "msg-001-2",
        "msg-001-3",
    ]
    assert [message["id"] for message in thread["messages"]] == [
        message["id"] for message in messages
    ]
    assert len({message["payload"]["body"]["data"] for message in messages}) == 4
    assert messages[1]["payload"]["parts"][0]["body"]["attachmentId"] == "att-001"
    assert attachment["size"] > 0
    assert attachment["data"]


def test_collaboration_api_accepts_natural_text_but_rubric_requires_decision_evidence(
    tmp_path: Path,
) -> None:
    task = build_catalog()[0]
    write = next(
        step
        for step in task["oracle_steps"]
        if step["tool"] == "google_sheets.spreadsheets.values.update"
    )
    assertion = next(
        assertion
        for assertion in task["expected"]["assertions"]
        if assertion.get("payload_contains", {}).get("tool") == write["tool"]
    )
    wrong = {
        **write["arguments"],
        "requestBody": {
            **write["arguments"]["requestBody"],
            "values": [["Updated — see me later"]],
        },
    }
    with FactoryWorld.fresh(task, tmp_path / "collaboration-content.db") as world:
        accepted = world.call_tool(write["tool"], wrong)
        assert "error" not in accepted
        wrong_verdict = verify_episode(task, world)
        wrong_check = _atomic_check(wrong_verdict, assertion["id"])
        assert wrong_check["passed"] is False
        assert set(wrong_check["evidence"]["missing_payload_text"]) == {
            "2026-01-20",
            "standard_plan",
        }

        corrected = world.call_tool(write["tool"], write["arguments"])
        assert "error" not in corrected
        corrected_verdict = verify_episode(task, world)
        corrected_check = _atomic_check(corrected_verdict, assertion["id"])
        assert corrected_check["passed"] is True


def test_drive_comments_and_slack_posts_are_inspectable_after_creation(tmp_path: Path) -> None:
    tasks = build_catalog()
    drive_task = next(
        task
        for task in tasks
        if any(step["tool"] == "google_drive.comments.create" for step in task["oracle_steps"])
    )
    with FactoryWorld.fresh(drive_task, tmp_path / "drive.db") as world:
        write = next(
            step
            for step in drive_task["oracle_steps"]
            if step["tool"] == "google_drive.comments.create"
        )
        created = world.call_tool(write["tool"], write["arguments"])
        listed = world.call_tool(
            "google_drive.comments.list",
            {"fileId": write["arguments"]["fileId"], "pageSize": 100},
        )
        fetched = world.call_tool(
            "google_drive.comments.get",
            {
                "fileId": write["arguments"]["fileId"],
                "commentId": created["id"],
            },
        )
        assert listed["comments"] == [fetched]
        assert fetched["content"] == write["arguments"]["requestBody"]["content"]

    slack_task = next(
        task
        for task in tasks
        if any(step["tool"] == "slack.chat_postMessage" for step in task["oracle_steps"])
    )
    with FactoryWorld.fresh(slack_task, tmp_path / "slack.db") as world:
        write = next(
            step
            for step in slack_task["oracle_steps"]
            if step["tool"] == "slack.chat_postMessage"
        )
        created = world.call_tool(write["tool"], write["arguments"])
        replies = world.call_tool(
            "slack.conversations_replies",
            {
                "channel": write["arguments"]["channel"],
                "ts": write["arguments"]["thread_ts"],
                "limit": 100,
            },
        )
        assert created["ok"] is True
        assert replies["messages"][-1]["text"] == write["arguments"]["text"]
        file_id = replies["messages"][2]["files"][0]["id"]
        file_info = world.call_tool("slack.files_info", {"file": file_id})
        assert file_info["ok"] is True
        assert file_info["file"]["id"] == file_id


def test_sandbox_bridge_accepts_wrong_business_state_then_grades_the_correction(
    tmp_path: Path,
) -> None:
    task = build_catalog()[0]
    bundle = _bundle(tmp_path, task)
    session = tmp_path / "oracle-session"
    _run(bundle, session, {"action": "reset"})
    write = next(
        step
        for step in task["oracle_steps"]
        if step["tool"] == task["workflow"]["primary_write"]
    )
    incomplete = {
        **write["arguments"],
        "requestBody": {
            key: value
            for key, value in write["arguments"]["requestBody"].items()
            if key != "WorkOrderStatusCode"
        },
    }
    accepted = _run(
        bundle,
        session,
        {"action": "call", "tool": write["tool"], "arguments": incomplete},
    )
    assert accepted["ok"] is True
    assert accepted["is_error"] is False
    wrong = _run(bundle, session, {"action": "inspect"})
    mutation = next(
        check
        for check in wrong["verification"]["checks"]
        if check["id"] == "mutation_01"
    )
    assert mutation["passed"] is False
    assert "payload_mismatches" in mutation["evidence"]
    assert wrong["verification"]["checks"][-1]["passed"] is True

    corrected = _run(
        bundle,
        session,
        {"action": "call", "tool": write["tool"], "arguments": write["arguments"]},
    )
    assert corrected["is_error"] is False
    final = _run(bundle, session, {"action": "inspect"})
    mutation = next(
        check
        for check in final["verification"]["checks"]
        if check["id"] == "mutation_01"
    )
    assert mutation["passed"] is True
    state_rows = final["state_diff"]["resource_state"]["after"]
    primary = next(
        row
        for row in state_rows
        if row["resource_id"] == f"{task['task_id']}-mutation-01"
    )
    assert json.loads(primary["payload_json"])["arguments"] == write["arguments"]
