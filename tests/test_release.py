from __future__ import annotations

import hashlib
import json
import tomllib
import zipfile
from pathlib import Path

from factorybench.catalog import WORLD_ID, build_catalog
from factorybench.release import HARBOR_PYTHON_IMAGE, _write_xlsx
from factorybench.server import handle_request, tool_definitions
from factorybench.world import FactoryWorld


RELEASE = Path(__file__).resolve().parents[1] / "benchmark" / "factorybench100"


def test_checked_in_release_has_all_distribution_shapes() -> None:
    qualification = json.loads((RELEASE / "reports" / "qualification.json").read_text())
    fidelity = json.loads((RELEASE / "reports" / "catalog-fidelity.json").read_text())
    website = json.loads((RELEASE / "website-data.json").read_text())
    hf_rows = [line for line in (RELEASE / "huggingface" / "data" / "tasks.jsonl").read_text().splitlines() if line]
    harbor_tasks = list((RELEASE / "harbor" / "tasks").glob("*/task.toml"))
    harbor_manifest = tomllib.loads((RELEASE / "harbor" / "dataset.toml").read_text())
    assert qualification["qualification_passed"] is True
    assert qualification["mutation_omissions"] == {
        "total": 300,
        "detected": 300,
        "all_detected": True,
        "failures": [],
    }
    assert fidelity["passed"] is True
    assert fidelity["unique_sequences"] == 100
    assert fidelity["closest_pair"]["similarity"] <= 0.80
    assert website["benchmark"]["taskCount"] == 100
    assert len(website["benchmark"]["categories"]) == 20
    assert website["benchmark"]["world"]["documents"] == 1200
    assert len(hf_rows) == 100
    assert len(harbor_tasks) == 100
    assert len(harbor_manifest["tasks"]) == 100
    assert all(reference["digest"].startswith("sha256:") for reference in harbor_manifest["tasks"])
    assert any(tool["name"] == "oracle_fusion.invoices.validate" for tool in website["tools"])
    assert not {"approve_invoice", "hold_invoice"} & {tool["name"] for tool in website["tools"]}

    model_rows = [row for row in website["leaderboard"] if row["kind"] == "model"]
    assert model_rows
    assert all(row["tasks"] == 100 for row in model_rows)
    semantic_rows = []
    harbor_task_root = RELEASE / "harbor" / "tasks"
    for path in sorted(harbor_task_root.rglob("*")):
        if not path.is_file() or (
            path.name == "Dockerfile" and path.parent.name == "environment"
        ):
            continue
        relative = path.relative_to(harbor_task_root).as_posix()
        semantic_rows.append(f"{relative}\0{hashlib.sha256(path.read_bytes()).hexdigest()}")
    semantic_tree_sha256 = hashlib.sha256("\n".join(semantic_rows).encode()).hexdigest()
    for row in model_rows:
        for mirror in ("model-runs", "huggingface/model-runs", "harbor/model-runs"):
            manifest_path = RELEASE / mirror / Path(row["runUrl"]).name
            assert manifest_path.is_file()
            manifest = json.loads(manifest_path.read_text())
            overlay = manifest["runtime_overlay"]
            assert overlay["semantic_files_byte_identical"] is True
            assert overlay["tasks_compared"] == 100
            assert overlay["semantic_file_count"] == len(semantic_rows)
            assert overlay["semantic_tree_sha256"] == semantic_tree_sha256
            assert (RELEASE / mirror / overlay["artifact"]).is_file()

    for row in map(json.loads, hf_rows):
        assert len(row["context_files"]) >= 13
        assert all((RELEASE / "huggingface" / path).is_file() for path in row["context_files"])

    for sample in website["samples"].values():
        assert len(sample["assets"]) == 14
        for asset in sample["assets"]:
            path = RELEASE / asset["path"]
            assert path.is_file()
            assert asset["bytes"] == path.stat().st_size
            assert asset["url"].endswith(asset["path"])


def test_released_pdf_and_excel_assets_are_real_files() -> None:
    asset_root = RELEASE / "assets" / "factorybench-001"
    assert (asset_root / "supplier-confirmation.pdf").read_bytes().startswith(b"%PDF-1.4")
    with zipfile.ZipFile(asset_root / "planning-inputs.xlsx") as workbook:
        assert "xl/workbook.xml" in workbook.namelist()
        assert "xl/worksheets/sheet1.xml" in workbook.namelist()


def test_xlsx_writer_is_byte_deterministic(tmp_path: Path) -> None:
    rows = [["part", "quantity"], ["NS-COMP-001", 42]]
    first = tmp_path / "first.xlsx"
    second = tmp_path / "second.xlsx"

    _write_xlsx(first, rows)
    _write_xlsx(second, rows)

    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as workbook:
        assert {member.date_time for member in workbook.infolist()} == {
            (1980, 1, 1, 0, 0, 0)
        }


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
    assert "contracts.py" in environment_files
    assert definition["agent"]["user"] == "agent"
    assert definition["verifier"]["user"] == "root"
    assert f"FROM {HARBOR_PYTHON_IMAGE}" in dockerfile
    assert "runtime.py" not in dockerfile
    assert "task.json" not in dockerfile
    assert f"FROM {HARBOR_PYTHON_IMAGE}" in service_dockerfile
    assert "COPY runtime.py contracts.py schema.sql service.py task.json" in service_dockerfile
    assert "0700 /var/lib/factorybench" in service_dockerfile
    assert "http://erp:8765/call" in compose
    assert "factorybench-evidence:/var/lib/factorybench-evidence:ro" in compose
    assert environment_task["world"]["id"] == WORLD_ID
    assert len(environment_task["seed_tables"]["evidence_files"]) == 12
    assert environment_task["answer_schema"]["additionalProperties"] is False
    assert "urlopen" not in verifier
    assert "/var/lib/factorybench-evidence/evidence.json" in verifier


def test_tool_contracts_are_endpoint_pinned_json_schema_objects() -> None:
    tools = tool_definitions()
    assert len(tools) >= 80
    names = {tool["name"] for tool in tools}
    assert {
        "factorybench.context.get",
        "factorybench.submit_answer",
        "oracle_fusion.invoices.validate",
        "gmail.messages.get",
        "google_drive.files.get",
        "google_sheets.spreadsheets.values.update",
        "slack.chat_postMessage",
    } <= names
    assert all(tool["inputSchema"]["type"] == "object" for tool in tools)
    assert all("upstream" in tool["_meta"]["factorybench"] for tool in tools)
    task_tools = tool_definitions(build_catalog()[0])
    submit = next(tool for tool in task_tools if tool["name"] == "factorybench.submit_answer")
    assert submit["inputSchema"] == build_catalog()[0]["answer_schema"]


def test_mcp_initialize_and_tool_list(tmp_path: Path) -> None:
    task = build_catalog()[0]
    with FactoryWorld.fresh(task, tmp_path / "world.db") as world:
        initialized = handle_request(world, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        listed = handle_request(world, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert initialized["result"]["serverInfo"] == {"name": "factorybench", "version": "3.0.0"}
    assert len(listed["result"]["tools"]) == len(tool_definitions())
    submit = next(tool for tool in listed["result"]["tools"] if tool["name"] == "factorybench.submit_answer")
    assert submit["inputSchema"] == task["answer_schema"]


def test_environment_context_exposes_evidence_and_mounted_systems(tmp_path: Path) -> None:
    task = build_catalog()[0]
    with FactoryWorld.fresh(task, tmp_path / "world.db") as world:
        context = world.call_tool("factorybench.context.get", {})
    assert context["task"] == {
        "task_id": task["task_id"],
        "family": task["family"],
        "role": task["role"],
        "as_of": task["as_of"],
    }
    assert context["organization"]["world_id"] == WORLD_ID
    assert context["state"] == {
        "scope": "isolated task snapshot",
        "persistence": "episode-local SQLite",
        "network": "closed",
    }
    assert len(context["evidence_index"]) == 12
    assert set(task["world"]["systems"]) == {server["name"] for server in context["tool_servers"]}
    assert context["reference_records"]["case_reference"] == "CASE-001"
    assert context["reference_records"]["google_sheets"]["outcome_write_range"] == "Control!H3"
