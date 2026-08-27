from __future__ import annotations

import json
import tomllib
from pathlib import Path

from factorybench.catalog import build_catalog
from factorybench.release import HARBOR_PYTHON_IMAGE
from factorybench.server import handle_request, tool_definitions
from factorybench.world import FactoryWorld


RELEASE = Path(__file__).resolve().parents[1] / "benchmark" / "factorybench100"


def test_checked_in_release_has_all_distribution_shapes() -> None:
    qualification = json.loads((RELEASE / "reports" / "qualification.json").read_text())
    website = json.loads((RELEASE / "website-data.json").read_text())
    hf_rows = [line for line in (RELEASE / "huggingface" / "data" / "tasks.jsonl").read_text().splitlines() if line]
    harbor_tasks = list((RELEASE / "harbor" / "tasks").glob("*/task.toml"))
    harbor_manifest = tomllib.loads((RELEASE / "harbor" / "dataset.toml").read_text())
    assert qualification["qualification_passed"] is True
    assert qualification["mutation_omissions"]["detected"] == qualification["mutation_omissions"]["total"]
    assert website["benchmark"]["taskCount"] == 100
    assert website["scoring"]["categories"] == [
        {
            "description": "100 × deterministic workflow checks passed / checks available, averaged over tasks.",
            "key": "factory_score",
            "label": "FactoryScore",
            "weight": 100,
        }
    ]
    assert len(hf_rows) == 100
    assert len(harbor_tasks) == 100
    assert len(harbor_manifest["tasks"]) == 100
    assert all(reference["digest"].startswith("sha256:") for reference in harbor_manifest["tasks"])
    assert {row["rank"] for row in website["leaderboard"]} == {"REF", "CTL"}
    assert json.loads((RELEASE / "reports" / "build.json").read_text())["harbor_python_image"] == HARBOR_PYTHON_IMAGE
    assert "Creative Commons Attribution 4.0" in (RELEASE / "LICENSE-DATA").read_text()
    assert (RELEASE / "huggingface" / "LICENSE").read_bytes() == (RELEASE / "LICENSE-DATA").read_bytes()
    assert (RELEASE / "huggingface" / "LICENSE-DATA").read_bytes() == (RELEASE / "LICENSE-DATA").read_bytes()
    assert (RELEASE / "harbor" / "LICENSE-DATA").read_bytes() == (RELEASE / "LICENSE-DATA").read_bytes()

    for row in map(json.loads, hf_rows):
        assert all((RELEASE / "huggingface" / path).is_file() for path in row["context_files"])

    for sample in website["samples"].values():
        for asset in sample["assets"]:
            path = RELEASE / asset["path"]
            assert path.is_file()
            assert asset["bytes"] == path.stat().st_size
            assert asset["url"].endswith(asset["path"])


def test_harbor_tasks_protect_authoritative_state() -> None:
    task_dir = RELEASE / "harbor" / "tasks" / "factorybench-021"
    environment_files = {path.name for path in (task_dir / "environment").iterdir()}
    definition = tomllib.loads((task_dir / "task.toml").read_text())
    dockerfile = (task_dir / "environment" / "Dockerfile").read_text()
    service_dockerfile = (task_dir / "environment" / "Dockerfile.service").read_text()
    compose = (task_dir / "environment" / "docker-compose.yaml").read_text()
    environment_task = json.loads((task_dir / "environment" / "task.json").read_text())
    verifier = (task_dir / "tests" / "verify.py").read_text()

    assert "seed.db" not in environment_files
    assert definition["agent"]["user"] == "agent"
    assert definition["verifier"]["user"] == "root"
    assert f"FROM {HARBOR_PYTHON_IMAGE}" in dockerfile
    assert "runtime.py" not in dockerfile
    assert "task.json" not in dockerfile
    assert f"FROM {HARBOR_PYTHON_IMAGE}" in service_dockerfile
    assert "COPY runtime.py schema.sql service.py task.json" in service_dockerfile
    assert "0700 /var/lib/factorybench" in service_dockerfile
    assert "http://erp:8765/call" in compose
    assert "factorybench-evidence:/var/lib/factorybench-evidence:ro" in compose
    assert "FACTORYBENCH_EVIDENCE_PATH: /var/lib/factorybench-evidence/evidence.json" in compose
    assert "internal: true" in compose
    assert environment_task["answer_schema"]["additionalProperties"] is False
    assert "http://erp:8765/snapshot" not in compose
    assert "urlopen" not in verifier
    assert "/var/lib/factorybench-evidence/evidence.json" in verifier
    assert "baseline_snapshot" in verifier


def test_tool_contracts_are_json_schema_objects() -> None:
    tools = tool_definitions()
    assert len(tools) >= 30
    assert {tool["name"] for tool in tools} >= {"get_bom", "create_work_order", "submit_answer"}
    assert all(tool["inputSchema"]["type"] == "object" for tool in tools)
    task_tools = tool_definitions(build_catalog()[0])
    submit = next(tool for tool in task_tools if tool["name"] == "submit_answer")
    assert submit["inputSchema"]["additionalProperties"] is False
    assert submit["inputSchema"]["required"] == sorted(build_catalog()[0]["expected"]["answer"])


def test_mcp_initialize_and_tool_list(tmp_path: Path) -> None:
    task = build_catalog()[0]
    with FactoryWorld.fresh(task, tmp_path / "world.db") as world:
        initialized = handle_request(world, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        listed = handle_request(world, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert initialized["result"]["serverInfo"]["name"] == "factorybench"
    assert len(listed["result"]["tools"]) == len(tool_definitions())
    submit = next(tool for tool in listed["result"]["tools"] if tool["name"] == "submit_answer")
    assert submit["inputSchema"] == task["answer_schema"]
