from __future__ import annotations

import hashlib
from collections import Counter

from factorybench.catalog import FAMILIES, build_catalog, catalog_quality_report, task_tool_sequence
from factorybench.server import tool_definitions
from factorybench.world import READ_TOOLS


def test_catalog_has_twenty_balanced_workflow_families() -> None:
    tasks = build_catalog()
    assert len(tasks) == 100
    assert len({task["task_id"] for task in tasks}) == 100
    assert Counter(task["family"] for task in tasks) == Counter({family: 5 for family in FAMILIES})


def test_every_task_has_a_distinct_tool_call_sequence() -> None:
    tasks = build_catalog()
    report = catalog_quality_report(tasks)
    assert report["passed"] is True
    assert report["unique_titles"] == 100
    assert report["unique_sequences"] == 100
    assert report["duplicate_sequences"] == []
    assert report["closest_pair"]["similarity"] <= 0.82
    assert report["asset_role_count"] == 12
    assert report["asset_roles_with_unique_task_content"] == 12
    assert set(report["asset_role_unique_content_counts"].values()) == {100}
    assert len({task_tool_sequence(task) for task in tasks}) == 100


def test_every_task_is_executable_cross_system_and_richly_seeded() -> None:
    tool_names = {tool["name"] for tool in tool_definitions()}
    for task in build_catalog():
        assert task["instruction"]
        assert task["seed_tables"]
        assert len(task["assets"]) >= 12
        assert len(task["world"]["systems"]) >= 5
        assert {"oracle_fusion", "factorybench"} <= set(task["world"]["systems"])
        assert task["expected"]["assertions"]
        assert task["expected"]["answer"]
        assert task["required_reads"]
        assert len(task["required_read_calls"]) == len(task["required_reads"])
        assert all(call["match"] == "successful_tool_call" for call in task["required_read_calls"])
        required_oracle_reads = {
            call["tool"]
            for call in task["required_read_calls"]
            if call["tool"].startswith("oracle_fusion.")
        }
        assert required_oracle_reads <= {
            task["workflow"]["support_read"],
            task["workflow"]["primary_read"],
        }
        seeded_read_tools = {
            row["tool_name"]
            for row in task["seed_tables"]["api_fixtures"]
            if row["read_only"]
        }
        assert READ_TOOLS - {"factorybench.context.get"} <= seeded_read_tools
        assert task["answer_schema"]["additionalProperties"] is False
        assert set(task["answer_schema"]["required"]) == set(task["expected"]["answer"])
        assert task["oracle_steps"][0]["tool"] == "factorybench.context.get"
        assert task["oracle_steps"][-1]["tool"] == "factorybench.submit_answer"
        assert task["oracle_steps"][-1]["arguments"] == task["expected"]["answer"]
        assert {step["tool"] for step in task["oracle_steps"]} <= tool_names
        assert task["evaluation"]["metric"] == "FactoryScore"


def test_oracle_tools_are_documented_operations_not_business_verb_shortcuts() -> None:
    forbidden = {
        "approve_invoice",
        "hold_invoice",
        "create_work_order",
        "reroute_operation",
        "reschedule_work_order",
        "search_documents",
    }
    definitions = tool_definitions()
    names = {tool["name"] for tool in definitions}
    assert not names & forbidden
    oracle = [tool for tool in definitions if tool["name"].startswith("oracle_fusion.")]
    assert oracle
    for tool in oracle:
        upstream = tool["_meta"]["factorybench"]["upstream"]
        assert upstream["method"] in {"GET", "POST", "PATCH", "DELETE"}
        assert upstream["path"].startswith("/fscmRestApi/resources/11.13.18.05/")
        assert upstream["source"].startswith("https://docs.oracle.com/")
    validation = next(tool for tool in oracle if tool["name"] == "oracle_fusion.invoices.validate")
    assert validation["_meta"]["factorybench"]["upstream"] == {
        "method": "POST",
        "path": "/fscmRestApi/resources/11.13.18.05/invoices/action/validateInvoice",
        "source": "https://docs.oracle.com/en/cloud/saas/financials/26a/farfa/op-invoices-action-validateinvoice-post.html",
    }
    assert validation["inputSchema"]["properties"]["requestBody"]["required"] == [
        "ProcessAction",
        "BusinessUnit",
        "Supplier",
        "InvoiceNumber",
    ]


def test_evidence_hashes_match_extracted_task_content() -> None:
    required_media = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "message/rfc822",
        "text/csv",
        "application/json",
        "text/markdown",
    }
    for task in build_catalog():
        assert required_media <= {asset["media_type"] for asset in task["assets"]}
        rows = {row["asset_id"]: row for row in task["seed_tables"]["evidence_files"]}
        for asset in task["assets"]:
            row = rows[asset["asset_id"]]
            assert row["sha256"] == hashlib.sha256(asset["content"].encode()).hexdigest()


def test_every_asset_role_has_task_specific_content() -> None:
    hashes_by_path: dict[str, set[str]] = {}
    for task in build_catalog():
        for asset in task["assets"]:
            hashes_by_path.setdefault(asset["path"], set()).add(
                hashlib.sha256(asset["content"].encode()).hexdigest()
            )

    assert len(hashes_by_path) == 12
    assert all(len(hashes) == 100 for hashes in hashes_by_path.values())
