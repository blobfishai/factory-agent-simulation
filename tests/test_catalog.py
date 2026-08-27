from __future__ import annotations

import hashlib
from collections import Counter

from factorybench.catalog import FAMILIES, build_catalog
from factorybench.server import tool_definitions


def test_catalog_has_ten_balanced_workflow_families() -> None:
    tasks = build_catalog()
    assert len(tasks) == 100
    assert len({task["task_id"] for task in tasks}) == 100
    assert Counter(task["family"] for task in tasks) == Counter({family: 10 for family in FAMILIES})


def test_every_task_is_executable_and_scoped() -> None:
    tool_names = {tool["name"] for tool in tool_definitions()}
    for task in build_catalog():
        assert task["instruction"]
        assert task["seed_tables"]
        assert task["expected"]["assertions"]
        assert task["expected"]["answer"]
        assert task["required_reads"]
        assert len(task["required_read_calls"]) == len(task["required_reads"])
        assert task["allowed_write_tables"]
        assert task["answer_schema"]["additionalProperties"] is False
        assert set(task["answer_schema"]["required"]) == set(task["expected"]["answer"])
        assert task["oracle_steps"][-1]["tool"] == "submit_answer"
        assert task["oracle_steps"][-1]["arguments"] == task["expected"]["answer"]
        assert {step["tool"] for step in task["oracle_steps"]} <= tool_names
        assert task["evaluation"]["metric"] == "FactoryScore"


def test_task_data_is_explicitly_synthetic() -> None:
    for task in build_catalog():
        assert task["world"]["name"] == "Northstar Controls Oracle-shaped ERP"
        assert "Oracle-shaped" in task["world"]["name"]
        assert task["world"]["database"] == "SQLite"


def test_policy_document_hashes_match_the_canonical_markdown() -> None:
    for task in build_catalog():
        for document in task["seed_tables"]["documents"]:
            content = f"# {document['title']}\n\n{document['body']}\n".encode()
            assert document["sha256"] == hashlib.sha256(content).hexdigest()
