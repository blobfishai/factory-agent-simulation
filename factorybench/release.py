"""Build the public FactoryBench-100 release tree and website payload."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import shutil
import statistics
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

from .catalog import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    FAMILIES,
    WORLD_ID,
    build_catalog,
    catalog_fingerprint,
    catalog_quality_report,
    task_fingerprint,
)
from .evaluation import NEGATIVE_POLICIES, policy_steps, qualify, run_episode
from .harbor_receipts import harbor_task_digest
from .harbor_results import _assert_public_value_safe, _validate_runtime_overlay
from .scenarios import FAMILY_DESCRIPTIONS, FAMILY_LABELS
from .server import tool_definitions
from .world import READ_TOOLS

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "benchmark" / "factorybench100"
MODEL_RUNS_ROOT = REPO_ROOT / "model_runs"
SOURCE_URL = "https://github.com/blobfishai/factory-agent-simulation"
HF_URL = "https://huggingface.co/datasets/SamuelChien821/factorybench-100"
HARBOR_URL = "https://hub.harborframework.com/datasets/blobfishai/factorybench-100/latest"
PAGE_URL = "https://blobfish.ai/benchmarks/factorybench-100"
HARBOR_PYTHON_IMAGE = "python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17"
MCP_CONFIG_PATH = "environment/mcp.json"
LEADERBOARD_POLICIES = (
    "oracle",
    "shortcut",
    "state_only",
    "wrong_evidence",
    "wrong_decision",
)
HARBOR_MCP_SERVERS = (
    "factorybench",
    "gmail",
    "google_drive",
    "google_sheets",
    "oracle_fusion",
    "slack",
)

def _write_text(path: Path, value: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    _write_text(path, "".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_pdf(path: Path, text: str) -> None:
    """Write a small valid PDF containing the task-specific extracted text."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [line[:92] for line in text.splitlines() if line.strip()][:42]
    commands = ["BT", "/F1 10 Tf", "54 750 Td", "12 TL"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("T*")
        commands.append(f"({escaped}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(bytes(output))


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _stable_zip_info(filename: str) -> zipfile.ZipInfo:
    """Return cross-run metadata for deterministic XLSX members."""

    info = zipfile.ZipInfo(filename=filename, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    return info


def _write_xlsx(path: Path, rows: list[list[Any]]) -> None:
    """Write a dependency-free, standards-shaped one-sheet XLSX workbook."""

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            reference = f"{_column_name(column_number)}{row_number}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{html.escape(str(value))}</t></is></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            _stable_zip_info("[Content_Types].xml"),
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        )
        archive.writestr(
            _stable_zip_info("_rels/.rels"),
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        )
        archive.writestr(
            _stable_zip_info("xl/workbook.xml"),
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Evidence" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            _stable_zip_info("xl/_rels/workbook.xml.rels"),
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        )
        archive.writestr(_stable_zip_info("xl/worksheets/sheet1.xml"), sheet)


def _write_asset(path: Path, asset: dict[str, Any]) -> None:
    if asset["media_type"] == "application/pdf":
        _write_pdf(path, asset["content"])
    elif asset["media_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        _write_xlsx(path, asset["rows"])
    else:
        _write_text(path, asset["content"])


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_model_runs() -> list[dict[str, Any]]:
    if not MODEL_RUNS_ROOT.exists():
        return []
    current_tasks = build_catalog()
    current_task_fingerprints = {
        task["task_id"]: task_fingerprint(task) for task in current_tasks
    }
    current_task_ids = set(current_task_fingerprints)
    current_catalog_fingerprint = catalog_fingerprint(current_tasks)
    released_task_digests = {
        task_id: harbor_task_digest(
            REPO_ROOT / "benchmark" / "factorybench100" / "harbor" / "tasks" / task_id
        )[0]
        for task_id in current_task_ids
    }

    def artifact_path(relative: Any, *, expected: str) -> Path:
        if not isinstance(relative, str) or relative != expected:
            raise ValueError(f"model-run artifact path must be {expected}")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"model-run artifact escapes its release root: {relative}")
        resolved = (MODEL_RUNS_ROOT / path).resolve()
        if not resolved.is_relative_to(MODEL_RUNS_ROOT.resolve()) or not resolved.is_file():
            raise ValueError(f"missing model-run artifact: {resolved}")
        return resolved

    runs = []
    for path in sorted(MODEL_RUNS_ROOT.glob("*.json")):
        run = _read_json(path)
        if run.get("schema_version") != "factorybench.model-run.v1":
            raise ValueError(f"unsupported model-run schema: {path}")
        if run.get("benchmark_version") != BENCHMARK_VERSION:
            continue
        if run.get("catalog_sha256") != current_catalog_fingerprint:
            continue
        run_slug = run.get("run_slug")
        model = run.get("model")
        if (
            run.get("benchmark") != BENCHMARK_NAME
            or not isinstance(run_slug, str)
            or run_slug != path.stem
            or not isinstance(run.get("job_id"), str)
            or not run["job_id"]
            or not isinstance(run.get("selection"), str)
            or not run["selection"].strip()
            or not isinstance(model, dict)
            or not all(
                isinstance(model.get(key), str) and model[key]
                for key in ("name", "provider", "agent", "agent_version", "reasoning_effort")
            )
        ):
            raise ValueError(f"invalid model-run identity: {path}")
        trials = run.get("trials")
        aggregate = run.get("aggregate")
        if (
            not isinstance(trials, list)
            or not isinstance(aggregate, dict)
            or len(trials) != len(current_task_ids)
            or aggregate.get("tasks") != len(current_task_ids)
        ):
            raise ValueError(f"model-run trial count mismatch: {path}")
        trial_ids = [
            trial.get("task_id") if isinstance(trial, dict) else None
            for trial in trials
        ]
        if len(set(trial_ids)) != len(trial_ids) or set(trial_ids) != current_task_ids:
            raise ValueError(f"model-run does not cover the complete catalog: {path}")
        if any(
            trial.get("task_id") not in current_task_fingerprints
            or trial.get("benchmark_task_sha256")
            != current_task_fingerprints[trial.get("task_id")]
            or trial.get("harbor_task_digest")
            != released_task_digests[trial.get("task_id")]
            for trial in trials
        ):
            continue
        runtime_overlay = run.get("runtime_overlay")
        if not isinstance(runtime_overlay, dict):
            raise ValueError(f"current model run lacks its sealed runtime overlay: {path}")
        runtime_mount = runtime_overlay.get("runtime_mount")
        runtime_targets = (
            runtime_mount.get("targets") if isinstance(runtime_mount, dict) else None
        )
        if not isinstance(runtime_targets, list) or not all(
            isinstance(target, str) for target in runtime_targets
        ):
            raise ValueError(f"invalid model-run runtime overlay targets: {path}")
        _validate_runtime_overlay(
            runtime_overlay,
            task_count=len(current_task_ids),
            mounted_targets=tuple(sorted(runtime_targets)),
            agent_version=model["agent_version"],
            verify_source=False,
        )
        public_manifest = {
            key: value for key, value in run.items() if key != "runtime_overlay"
        }
        _assert_public_value_safe(public_manifest, location=f"model run {path.name}")
        overlay_for_safety = json.loads(json.dumps(runtime_overlay))
        overlay_for_safety["runtime_mount"]["targets"] = [
            "<sealed-runtime-target>" for _ in runtime_targets
        ]
        _assert_public_value_safe(
            overlay_for_safety,
            location=f"runtime overlay {path.name}",
        )
        for trial in trials:
            task_id = trial["task_id"]
            artifact = artifact_path(
                trial.get("artifact"),
                expected=f"{run_slug}/trials/{task_id}.json",
            )
            artifact_record = _read_json(artifact)
            _assert_public_value_safe(
                artifact_record,
                location=f"model trial {task_id}",
            )
            artifact_summary = {
                key: value
                for key, value in artifact_record.items()
                if key not in {"verdict", "trace"}
            }
            if artifact_summary != {
                key: value for key, value in trial.items() if key != "artifact"
            }:
                raise ValueError(f"model-run summary disagrees with its artifact: {artifact}")
            verdict = artifact_record.get("verdict")
            trace = artifact_record.get("trace")
            if (
                not isinstance(verdict, dict)
                or verdict.get("task_id") != task_id
                or not isinstance(verdict.get("strict_pass"), bool)
                or not isinstance(trial.get("strict_pass"), bool)
                or verdict.get("strict_pass") is not trial.get("strict_pass")
                or not isinstance(verdict.get("factory_score"), (int, float))
                or isinstance(verdict.get("factory_score"), bool)
                or not math.isclose(
                    float(verdict["factory_score"]),
                    float(trial.get("score")),
                    rel_tol=0,
                    abs_tol=1e-8,
                )
                or not isinstance(trace, list)
                or not all(
                    isinstance(entry, dict)
                    and isinstance(entry.get("tool"), str)
                    and isinstance(entry.get("arguments"), dict)
                    and isinstance(entry.get("success"), bool)
                    and "result" in entry
                    for entry in trace
                )
                or len(trace) != trial.get("tool_calls")
                or sum(
                    isinstance(entry, dict) and entry.get("success") is True
                    for entry in trace
                )
                != trial.get("successful_tool_calls")
                or sum(
                    isinstance(entry, dict) and entry.get("success") is False
                    for entry in trace
                )
                != trial.get("rejected_tool_calls")
                or not isinstance(artifact_record.get("final_response"), str)
                or not artifact_record["final_response"].strip()
                or artifact_record.get("final_response_sha256")
                != _canonical_json_sha256(artifact_record["final_response"])
                or artifact_record.get("public_trace_sha256")
                != _canonical_json_sha256(trace)
            ):
                raise ValueError(f"model-run verifier artifact is internally inconsistent: {artifact}")
        overlay_artifact = artifact_path(
            runtime_overlay.get("artifact"),
            expected=f"{run_slug}/runtime-overlay.json",
        )
        if _read_json(overlay_artifact) != runtime_overlay:
            raise ValueError(f"model-run runtime overlay receipt changed: {path}")

        scores = [trial.get("score") for trial in trials]
        calls = [trial.get("tool_calls") for trial in trials]
        if (
            not all(
                isinstance(score, (int, float))
                and not isinstance(score, bool)
                and math.isfinite(float(score))
                and 0 <= float(score) <= 100
                for score in scores
            )
            or not any(float(score) > 0 for score in scores)
            or not all(
                isinstance(call, int) and not isinstance(call, bool) and call >= 0
                for call in calls
            )
            or aggregate.get("mean_factory_score")
            != round(statistics.mean(float(score) for score in scores), 2)
            or aggregate.get("strict_passes")
            != sum(trial.get("strict_pass") is True for trial in trials)
            or aggregate.get("strict_pass_rate")
            != round(
                sum(trial.get("strict_pass") is True for trial in trials)
                / len(trials)
                * 100,
                2,
            )
            or aggregate.get("average_tool_calls")
            != round(statistics.mean(calls), 2)
        ):
            raise ValueError(f"model-run aggregate disagrees with its trials: {path}")
        runs.append(run)
    return runs


def _copy_model_run_artifacts(runs: list[dict[str, Any]], destination: Path) -> None:
    """Mirror only manifests and trials pinned to the current benchmark release."""

    for run in runs:
        manifest = MODEL_RUNS_ROOT / f"{run['run_slug']}.json"
        if not manifest.is_file():
            raise ValueError(f"missing model-run manifest: {manifest}")
        target = destination / manifest.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest, target)
        for trial in run["trials"]:
            source = MODEL_RUNS_ROOT / str(trial["artifact"])
            target = destination / str(trial["artifact"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        runtime_overlay = run.get("runtime_overlay")
        if runtime_overlay is not None:
            source = MODEL_RUNS_ROOT / str(runtime_overlay["artifact"])
            target = destination / str(runtime_overlay["artifact"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _harbor_model_run_bundle(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Flatten the exact public run tree into one Harbor dataset-level file."""

    bundled_runs: list[dict[str, Any]] = []
    for run in runs:
        run_slug = str(run["run_slug"])
        artifacts = []
        for trial in run["trials"]:
            relative = str(trial["artifact"])
            artifacts.append(
                {
                    "path": f"model-runs/{relative}",
                    "record": _read_json(MODEL_RUNS_ROOT / relative),
                }
            )
        runtime_overlay = run.get("runtime_overlay")
        runtime_artifact = None
        if runtime_overlay is not None:
            relative = str(runtime_overlay["artifact"])
            runtime_artifact = {
                "path": f"model-runs/{relative}",
                "record": _read_json(MODEL_RUNS_ROOT / relative),
            }
        bundled_runs.append(
            {
                "manifest_path": f"model-runs/{run_slug}.json",
                "manifest": run,
                "trial_artifacts": artifacts,
                "runtime_overlay_artifact": runtime_artifact,
            }
        )
    bundle = {
        "schema_version": "factorybench.harbor-model-runs.v1",
        "benchmark": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "runs": bundled_runs,
    }
    _assert_public_value_safe(bundle, location="Harbor model-run bundle")
    return bundle


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _harbor_task_digest(task_dir: Path) -> str:
    """Match Harbor 0.21's content digest for the generated task shape."""
    return harbor_task_digest(task_dir)[0]


def _harbor_dataset_manifest(
    tasks_root: Path,
    dataset_files: tuple[Path, ...] = (),
) -> str:
    lines = [
        "# Generated FactoryBench-100 Harbor dataset",
        "[dataset]",
        'name = "blobfishai/factorybench-100"',
        f'version = "{BENCHMARK_VERSION}"',
        'description = "100 executable manufacturing ERP workflow tasks with deterministic FactoryScore grading"',
        'keywords = [ "manufacturing", "erp", "agents", "stateful", "deterministic",]',
        "[[dataset.authors]]",
        'name = "Blobfish AI"',
        "",
    ]
    for task_dir in sorted(path for path in tasks_root.iterdir() if path.is_dir()):
        task_config = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
        lines.extend(
            [
                "",
                "[[tasks]]",
                f'name = "{task_config["task"]["name"]}"',
                f'digest = "{_harbor_task_digest(task_dir)}"',
            ]
        )
    for dataset_file in sorted(dataset_files, key=lambda path: path.name):
        if dataset_file.parent != tasks_root.parent or "/" in dataset_file.name:
            raise ValueError("Harbor dataset files must be top-level release files")
        lines.extend(
            [
                "",
                "[[files]]",
                f'path = "{dataset_file.name}"',
                f'digest = "sha256:{_sha256(dataset_file)}"',
            ]
        )
    return "\n".join(lines) + "\n"


def _rubric_criteria(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": milestone["id"],
            "category": milestone["category"],
            "description": milestone["description"],
            "weight": float(milestone["weight"]),
        }
        for milestone in task["rubric_milestones"]
    ]


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    rubric = _rubric_criteria(task)
    return {
        "task_id": task["task_id"],
        "task_name": task["title"],
        "world_id": WORLD_ID,
        "prompt": task["instruction"],
        "role": task["role"],
        "family": task["family"],
        "level": task["level"],
        "as_of": task["as_of"],
        "context_files": [
            f"assets/{task['task_id']}/{asset['path']}"
            for asset in task["assets"]
        ],
        "reference_tools": [step["tool"] for step in task["oracle_steps"]],
        "call_order_policy": "The reference trajectory is illustrative, not graded. Material identity, authority, constraint, and ERP discoveries must precede the dependent mutation; their order and valid query shapes are otherwise open.",
        "required_reads": task["required_reads"],
        "required_read_calls": task["required_read_calls"],
        "reference_read_calls": task["reference_read_calls"],
        "post_write_verifications": task.get("post_write_verifications", []),
        "answer_schema": task["answer_schema"],
        "allowed_write_tables": task["allowed_write_tables"],
        "rubric": [criterion["description"] for criterion in rubric],
        "rubric_criteria": rubric,
        "metric": task["evaluation"],
        "metadata": {
            "benchmark": BENCHMARK_NAME,
            "benchmark_version": BENCHMARK_VERSION,
            "organization": "Northstar Controls Manufacturing",
            "primary_plant": "SEA",
            "source_shape": "synthetic Oracle Fusion 26a operation-mapped enterprise world",
            "systems": task["world"]["systems"],
            "evidence_files": len(task["assets"]),
            "synthetic": True,
        },
    }


def _stage_for_tool(tool: str) -> str:
    if tool == "factorybench.context.get":
        return "discover"
    if tool.startswith(("gmail.", "google_drive.", "google_sheets.", "slack.")) and tool in READ_TOOLS:
        return "evidence"
    if tool in READ_TOOLS:
        return "inspect"
    if tool == "factorybench.submit_answer":
        return "submit"
    if tool.startswith(("gmail.", "google_drive.", "google_sheets.", "slack.")):
        return "communicate"
    return "transact"


def _website_data(
    tasks: list[dict[str, Any]],
    qualification: dict[str, Any],
    representative_episodes: dict[str, dict[str, Any]],
    release_root: Path,
    model_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    tools = tool_definitions()
    reference_calls = sorted(len(task["oracle_steps"]) for task in tasks)
    result_by_policy = {result["policy"]: result for result in qualification["results"]}
    names = {
        "oracle": "Reference oracle",
        "shortcut": "Shortcut control",
        "state_only": "State-only control",
        "wrong_evidence": "Wrong-evidence control",
        "wrong_decision": "Wrong-decision control",
    }
    notes = {
        "oracle": "Measured solvability ceiling from replaying the checked-in reference workflow; not a model submission.",
        "shortcut": "Measured control that submits a plausible answer and one late write without doing the investigation.",
        "state_only": "Measured control that reaches the reference provider state but omits the employee handoff.",
        "wrong_evidence": "Measured control that substitutes a valid but stale or irrelevant source for one required current record.",
        "wrong_decision": "Measured control that reaches the reference provider state but chooses a rejected operating alternative.",
    }
    leaderboard = []
    ranked_runs = sorted(
        model_runs,
        key=lambda run: (-run["aggregate"]["mean_factory_score"], run["model"]["name"]),
    )
    for rank, run in enumerate(ranked_runs, start=1):
        aggregate = run["aggregate"]
        model = run["model"]
        harness = run["harness"]
        leaderboard.append(
            {
                "rank": rank,
                "name": model["name"],
                "harness": (
                    f"{harness['name']} {harness['version']} · {model['agent']} "
                    f"{model['agent_version']} · {model['reasoning_effort']} reasoning"
                ),
                "kind": "model",
                "tasks": aggregate["tasks"],
                "score": aggregate["mean_factory_score"],
                "strictPassRate": aggregate["strict_pass_rate"],
                "categoryScores": {"factory_score": aggregate["mean_factory_score"]},
                "averageCalls": aggregate["average_tool_calls"],
                "averageCost": aggregate["average_cost_usd"],
                "note": run["selection"],
                "runUrl": run.get("run_url")
                or f"{SOURCE_URL}/blob/main/model_runs/{run['run_slug']}.json",
            }
        )
    for rank, policy in enumerate(LEADERBOARD_POLICIES, start=1):
        result = result_by_policy[policy]
        call_counts = [len(policy_steps(task, policy)) for task in tasks]
        leaderboard.append(
            {
                "rank": "REF" if policy == "oracle" else "CTL",
                "name": names[policy],
                "harness": "factorybench.evaluation deterministic replay",
                "kind": "reference",
                "tasks": len(tasks),
                "score": result["mean_score"],
                "strictPassRate": round(result["strict_passes"] / len(tasks) * 100, 2),
                "categoryScores": {"factory_score": result["mean_score"]},
                "averageCalls": round(statistics.mean(call_counts), 2),
                "averageCost": 0,
                "note": notes[policy],
            }
        )

    summaries: list[dict[str, Any]] = []
    samples: dict[str, Any] = {}
    for ordinal, task in enumerate(tasks, start=1):
        task_id = task["task_id"]
        summaries.append(
            {
                "id": task_id,
                "ordinal": ordinal,
                "title": task["title"],
                "category": task["family"],
                "organization": "Northstar Controls Manufacturing",
                "asOf": task["as_of"],
                "summary": task["instruction"],
                "documents": len(task["assets"]),
                "referenceToolCalls": len(task["oracle_steps"]),
                "sample": True,
                "datasetUrl": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/tasks/{task_id}.json",
            }
        )
        samples[task_id] = {
            "taskId": task_id,
            "prompt": task["instruction"],
            "gradedCriteria": [criterion["description"] for criterion in _rubric_criteria(task)],
            "criterionWeights": _rubric_criteria(task),
            "decisionBranch": task["workflow"]["decision_branch"],
            "options": task["decision_model"]["options"],
            "assets": [
                {
                    "path": (Path("assets") / task_id / asset["path"]).as_posix(),
                    "url": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/{(Path('assets') / task_id / asset['path']).as_posix()}",
                    "name": asset["path"],
                    "format": {
                        "application/pdf": "PDF",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
                        "application/json": "JSON",
                        "text/csv": "CSV",
                        "text/markdown": "Markdown",
                        "message/rfc822": "Email",
                    }.get(asset["media_type"], asset["media_type"]),
                    "bytes": (release_root / "assets" / task_id / asset["path"]).stat().st_size,
                    "preview": asset["preview"],
                    "role": asset["kind"],
                    "note": f"Synthetic task evidence surfaced through {asset['source']}.",
                    "source": asset["source"],
                    "mediaType": asset["media_type"],
                }
                for asset in task["assets"]
            ],
            "scoringWeights": [
                {
                    "key": "factory_score",
                    "label": "FactoryScore",
                    "weight": 100,
                    "description": "Mean percentage of deterministic end-to-end workflow checks passed.",
                }
            ],
        }

    trajectories = []
    for run in ranked_runs:
        featured_task_id = run["featured_task_id"]
        trial_summary = next(
            trial for trial in run["trials"] if trial["task_id"] == featured_task_id
        )
        trial = _read_json(MODEL_RUNS_ROOT / trial_summary["artifact"])
        task = next(item for item in tasks if item["task_id"] == featured_task_id)
        events: list[dict[str, Any]] = [
            {
                "index": 0,
                "kind": "message",
                "role": "employee-request",
                "stage": "discover",
                "text": task["instruction"],
            }
        ]
        for call_number, entry in enumerate(trial["trace"], start=1):
            result = json.dumps(entry["result"], sort_keys=True)
            events.append(
                {
                    "index": len(events),
                    "kind": "tool",
                    "stage": _stage_for_tool(entry["tool"]),
                    "call": call_number,
                    "tool": entry["tool"],
                    "arguments": entry["arguments"],
                    "outcome": "ok" if entry["success"] else "error",
                    "result": result[:360] + ("…" if len(result) > 360 else ""),
                }
            )
        events.append(
            {
                "index": len(events),
                "kind": "message",
                "role": "agent-response",
                "stage": "communicate",
                "text": trial["final_response"],
            }
        )
        events.append(
            {
                "index": len(events),
                "kind": "message",
                "role": "verifier-receipt",
                "stage": "submit",
                "text": (
                    f"Verifier: FactoryScore {trial['score']:.2f}; "
                    f"strict pass {'yes' if trial['strict_pass'] else 'no'}."
                ),
            }
        )
        artifact_url = f"{SOURCE_URL}/blob/main/model_runs/{trial_summary['artifact']}"
        model = run["model"]
        harness = run["harness"]
        trajectories.append(
            {
                "taskId": featured_task_id,
                "model": model["name"],
                "harness": (
                    f"{harness['name']} {harness['version']} · {model['agent']} "
                    f"{model['agent_version']} · {model['reasoning_effort']} reasoning"
                ),
                "kind": "model",
                "passed": trial["strict_pass"],
                "score": trial["score"],
                "categoryScores": {"factory_score": trial["score"]},
                "toolCalls": trial["tool_calls"],
                "costUsd": trial["cost_usd"],
                "tokens": trial["tokens"],
                "transcriptUrl": artifact_url,
                "verifierUrl": artifact_url,
                "stages": [
                    {"key": "discover", "label": "Discover"},
                    {"key": "evidence", "label": "Evidence"},
                    {"key": "inspect", "label": "Inspect"},
                    {"key": "transact", "label": "Transact"},
                    {"key": "communicate", "label": "Communicate"},
                    {"key": "submit", "label": "Submit"},
                ],
                "events": events,
            }
        )
    for family in FAMILIES:
        episode = representative_episodes[family]
        task = next(item for item in tasks if item["task_id"] == episode["task_id"])
        events: list[dict[str, Any]] = [
            {
                "index": 0,
                "kind": "message",
                "role": "employee-request",
                "stage": "discover",
                "text": task["instruction"],
            }
        ]
        for call_number, entry in enumerate(episode["trace"], start=1):
            result = json.dumps(entry["result"], sort_keys=True)
            events.append(
                {
                    "index": len(events),
                    "kind": "tool",
                    "stage": _stage_for_tool(entry["tool"]),
                    "call": call_number,
                    "tool": entry["tool"],
                    "arguments": entry["arguments"],
                    "outcome": "ok" if entry["success"] else "error",
                    "result": result[:360] + ("…" if len(result) > 360 else ""),
                }
            )
        events.append(
            {
                "index": len(events),
                "kind": "message",
                "role": "verifier-receipt",
                "stage": "submit",
                "text": f"Verifier: {episode['passed_checks']}/{episode['total_checks']} checks passed; FactoryScore {episode['score']:.2f}.",
            }
        )
        task_id = episode["task_id"]
        trajectories.append(
            {
                "taskId": task_id,
                "model": "Reference oracle",
                "harness": "factorybench.evaluation deterministic replay",
                "kind": "reference",
                "passed": episode["strict_pass"],
                "score": episode["score"],
                "categoryScores": {"factory_score": episode["score"]},
                "toolCalls": len(episode["trace"]),
                "costUsd": 0,
                "transcriptUrl": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/trajectories/oracle/{task_id}.json",
                "verifierUrl": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/verifiers/{task_id}.json",
                "stages": [
                    {"key": "discover", "label": "Discover"},
                    {"key": "evidence", "label": "Evidence"},
                    {"key": "inspect", "label": "Inspect"},
                    {"key": "transact", "label": "Transact"},
                    {"key": "communicate", "label": "Communicate"},
                    {"key": "submit", "label": "Submit"},
                ],
                "events": events,
            }
        )

    return {
        "schemaVersion": "blobfish.benchmark-page.v1",
        "benchmark": {
            "name": BENCHMARK_NAME,
            "version": BENCHMARK_VERSION,
            "tagline": "100 employee-grade manufacturing decisions with hidden investigation graphs and executable ERP outcomes.",
            "question": "Can an agent turn a high-level operating question into the right investigation, calculation, option analysis, and audited Oracle decision?",
            "taskCount": len(tasks),
            "categoryNoun": "decision domain",
            "categories": [{"key": family, "label": FAMILY_LABELS[family], "count": sum(task["family"] == family for task in tasks)} for family in FAMILIES],
            "world": {"tools": len(tools), "tables": 7, "documents": sum(len(task["assets"]) for task in tasks)},
            "referenceCalls": {"min": min(reference_calls), "median": statistics.median(reference_calls), "max": max(reference_calls)},
            "deterministicVerifier": True,
            "mcp": {
                "package": "factory-agent-simulation",
                "version": BENCHMARK_VERSION,
                "protocolVersion": "2025-03-26",
                "serverName": "factorybench",
                "command": f"uvx --from git+{SOURCE_URL}@v{BENCHMARK_VERSION} factorybench-mcp --task factorybench-001 --db .factorybench/factorybench-001.db --fresh",
                "configUrl": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/{MCP_CONFIG_PATH}",
                "demoTaskId": "factorybench-001",
                "sandboxUrl": "/api/v1/benchmarks/factorybench-100/sandbox/mcp",
                "sandboxSessionUrl": "/api/v1/benchmarks/factorybench-100/sandbox/sessions",
            },
            "contractPins": [
                {"name": "World", "value": WORLD_ID},
                {"name": "ERP contract", "value": "Oracle Fusion Cloud 26a documented REST operations"},
                {"name": "Collaboration contracts", "value": "Gmail v1 · Drive v3 · Sheets v4 · Slack Web API"},
                {"name": "Database", "value": "SQLite isolated multi-system snapshot"},
                {"name": "Harbor base image", "value": HARBOR_PYTHON_IMAGE},
                {"name": "Network in reward path", "value": "none"},
            ],
            "links": {"harbor": HARBOR_URL, "huggingFace": HF_URL, "source": SOURCE_URL, "blobfishPage": PAGE_URL},
        },
        "scoring": {
            "categories": [
                {
                    "key": "factory_score",
                    "label": "FactoryScore",
                    "weight": 100,
                    "description": "100 × passed task-specific deterministic criterion weight / available criterion weight, averaged over tasks.",
                }
            ],
            "strictPassTracked": True,
        },
        "leaderboard": leaderboard,
        "tasks": summaries,
        "samples": samples,
        "tools": [
            {
                **tool,
                "server": tool["_meta"]["factorybench"]["server"],
            }
            for tool in tools
        ],
        "trajectories": trajectories,
        "methodology": [
            {
                "title": "One metric, inspectable evidence",
                "body": "FactoryScore is the mean percentage of task-specific deterministic criterion weight passed. Discovery and final insights carry weight, calculations and the primary ERP decision carry more, and supporting collaboration writes and containment remain observable. Strict completion is supporting evidence, not a second metric.",
            },
            {
                "title": "The request does not reveal the recipe",
                "body": "Each prompt is a short employee request: decide the date, quantity, disposition, or commercial response and explain the constraint and alternatives. It contains no task ID, source list, filenames, answer schema, API names, or ordered steps. The agent must discover the case records and decide which evidence matters.",
            },
            {
                "title": "Facts are scattered, not preassembled",
                "body": "Each task mounts 28 retrievable, task-specific sources across Oracle resources, email, Drive, spreadsheets, Slack, vendor PDFs, specifications, inventory eligibility, finite-capacity slots, revisions, and approval limits. Current, superseded, other-case, and other-plant records must be correlated by immutable identity. No read returns an approved payload, operation name, or assembled answer. The clean-room company and all records are synthetic.",
            },
            {
                "title": "Qualification before publication",
                "body": f"The release executes {qualification['executions']} canonical trials: 100 reference workflows, 100 exact replays, and {100 * len(NEGATIVE_POLICIES):,} adversarial runs across {len(NEGATIVE_POLICIES)} controls. It also removes every reference mutation one at a time as a supplemental verifier test. Qualification passed: {qualification['oracle']['passes']}/100 oracle strict passes, {qualification['determinism']['exact_episode_matches']}/100 exact replay matches, and {sum(row['correct_rejections'] for row in qualification['negative_controls'].values())}/{100 * len(NEGATIVE_POLICIES):,} negative-control rejections.",
            },
            {
                "title": "Public inspirations and design boundary",
                "body": "Enterprise-Bench informed noisy multi-system task framing; ERP-Bench informed long-horizon manufacturing coverage; Mercor APEX informed the public task, asset, environment, and trajectory presentation. FactoryBench tasks, records, tools, and verifiers are independently authored and executable under this repository's licenses.",
            },
        ],
        "architectureComparison": {
            "title": "The same evaluation spine, assembled for manufacturing ERP",
            "intro": "Archipelago and FactoryBench share the central idea that an agent should act through tools in an isolated world and be graded from observable outcomes. FactoryBench adds endpoint-mapped enterprise APIs, heterogeneous evidence, task-level control checks, exact answer fields, and full public oracle replays.",
            "leftLabel": "Mercor Archipelago",
            "rightLabel": "Blobfish FactoryBench-100",
            "rows": [
                {"layer": "Environment", "left": "Containerized task environments with snapshot lifecycle", "right": "Per-task SQLite snapshots for Oracle, Gmail, Drive, Sheets, and Slack state"},
                {"layer": "Tool surface", "left": "MCP gateway and environment servers", "right": "One tool per documented upstream API operation, with method/path/source pins"},
                {"layer": "Agent run", "left": "Agent runner records tool interaction", "right": "Harness records every evidence read, ERP mutation, collaboration write, rejection, and submission"},
                {"layer": "Grading", "left": "Before/after snapshot graders", "right": "Task-specific discoveries + calculations + alternatives + exact state + answer insights"},
                {"layer": "Distribution", "left": "Open-source framework and role benchmarks", "right": "GitHub world, Hugging Face rows, Harbor tasks, and website explorer"},
            ],
            "linkLabel": "Inspect Archipelago",
            "linkUrl": "https://github.com/Mercor-Intelligence/archipelago",
        },
    }



def _harbor_task(root: Path, task: dict[str, Any]) -> None:
    harbor_task_name = f"blobfishai/{task['task_id']}"
    if harbor_task_name == "blobfishai/factorybench-100":
        harbor_task_name = "blobfishai/factorybench-task-100"
    task_dir = root / "tasks" / task["task_id"]
    environment = task_dir / "environment"
    tests = task_dir / "tests"
    solution = task_dir / "solution"
    environment.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    solution.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "factorybench" / "world.py", environment / "runtime.py")
    shutil.copy2(REPO_ROOT / "factorybench" / "contracts.py", environment / "contracts.py")
    shutil.copy2(REPO_ROOT / "factorybench" / "schema.sql", environment / "schema.sql")
    shutil.copy2(REPO_ROOT / "factorybench" / "harbor_service.py", environment / "service.py")
    shutil.copy2(REPO_ROOT / "factorybench" / "harbor_tool.py", environment / "tool")
    (environment / "service.py").chmod(0o755)
    (environment / "tool").chmod(0o755)
    _write_json(
        environment / "task.json",
        {
            "task_id": task["task_id"],
            "benchmark_version": BENCHMARK_VERSION,
            "title": task["title"],
            "instruction": task["instruction"],
            "family": task["family"],
            "role": task["role"],
            "level": task["level"],
            "as_of": task["as_of"],
            "world": task["world"],
            "workflow": task["workflow"],
            "seed_tables": task["seed_tables"],
            "required_reads": task["required_reads"],
            "required_read_calls": task["required_read_calls"],
            "reference_read_calls": task["reference_read_calls"],
            "required_investigations": task["required_investigations"],
            "rubric_milestones": task["rubric_milestones"],
            "post_write_verifications": task.get("post_write_verifications", []),
            "answer_schema": task["answer_schema"],
            "allowed_write_tables": task["allowed_write_tables"],
            "expected": task["expected"],
        },
    )
    _write_json(environment / "tools.json", tool_definitions(task))
    _write_text(
        environment / "Dockerfile",
        f"""FROM {HARBOR_PYTHON_IMAGE}
RUN groupadd --gid 10001 agent \\
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash agent \\
    && install -d -o agent -g agent -m 0755 /workspace \\
    && install -d -o root -g root -m 0755 /opt/factorybench
COPY tools.json /opt/factorybench/
COPY tool /usr/local/bin/tool
RUN chmod 0755 /usr/local/bin/tool \\
    && chmod 0444 /opt/factorybench/tools.json
WORKDIR /workspace
ENV FACTORYBENCH_ROOT=/opt/factorybench \\
    PYTHONUNBUFFERED=1
CMD ["sh", "-c", "sleep infinity"]
""",
    )
    _write_text(
        environment / "Dockerfile.service",
        f"""FROM {HARBOR_PYTHON_IMAGE}
RUN install -d -o root -g root -m 0700 /var/lib/factorybench \\
    && install -d -o root -g root -m 0755 /opt/factorybench
COPY runtime.py contracts.py schema.sql service.py task.json /opt/factorybench/
RUN chmod 0755 /opt/factorybench/service.py \\
    && chmod 0444 /opt/factorybench/runtime.py /opt/factorybench/contracts.py /opt/factorybench/schema.sql /opt/factorybench/task.json
ENV FACTORYBENCH_ROOT=/opt/factorybench \\
    FACTORYBENCH_BIND_HOST=0.0.0.0 \\
    PYTHONUNBUFFERED=1
CMD ["python3", "/opt/factorybench/service.py"]
""",
    )
    _write_text(
        environment / "docker-compose.yaml",
        """services:
  main:
    depends_on:
      world:
        condition: service_healthy
    environment:
      FACTORYBENCH_MCP_BASE: http://world:8765/mcp
    networks: [agent-egress, factorybench]
    volumes:
      - factorybench-evidence:/var/lib/factorybench-evidence:ro
  world:
    build:
      context: .
      dockerfile: Dockerfile.service
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=1)"]
      interval: 1s
      timeout: 2s
      retries: 30
    environment:
      FACTORYBENCH_EVIDENCE_PATH: /var/lib/factorybench-evidence/evidence.json
    networks: [factorybench]
    volumes:
      - factorybench-evidence:/var/lib/factorybench-evidence
networks:
  agent-egress: {}
  factorybench:
    internal: true
volumes:
  factorybench-evidence:
""",
    )
    _write_text(
        task_dir / "instruction.md",
        task["instruction"] + "\n",
    )
    description = json.dumps(task["instruction"])
    mcp_servers = "\n".join(
        f'''[[environment.mcp_servers]]
name = "{server}"
transport = "streamable-http"
url = "http://world:8765/mcp/{server}"
'''
        for server in HARBOR_MCP_SERVERS
    )
    _write_text(
        task_dir / "task.toml",
        f'''schema_version = "1.4"

[task]
name = "{harbor_task_name}"
version = "{BENCHMARK_VERSION}"
description = {description}
authors = [{{ name = "Blobfish AI" }}]
keywords = ["manufacturing", "erp", "oracle-fusion", "multi-system", "stateful", "deterministic"]

[agent]
user = "agent"
timeout_sec = 900.0

[verifier]
user = "root"
timeout_sec = 120.0

[environment]
build_timeout_sec = 600.0
cpus = 1
memory_mb = 1024
storage_mb = 2048
gpus = 0

{mcp_servers}
[metadata]
benchmark = "FactoryBench-100"
world_id = "{WORLD_ID}"
task_id = "{task['task_id']}"
category = "{task['family']}"
difficulty = "{task['level']}"
metric = "FactoryScore"
synthetic = true
''',
    )
    _write_json(
        tests / "task.json",
        {
            "task_id": task["task_id"],
            "required_reads": task["required_reads"],
            "required_read_calls": task["required_read_calls"],
            "reference_read_calls": task["reference_read_calls"],
            "required_investigations": task["required_investigations"],
            "rubric_milestones": task["rubric_milestones"],
            "post_write_verifications": task.get("post_write_verifications", []),
            "answer_schema": task["answer_schema"],
            "allowed_write_tables": task["allowed_write_tables"],
            "write_tools": sorted({step["tool"] for step in task["oracle_steps"] if step["tool"] not in READ_TOOLS}),
            "expected": task["expected"],
        },
    )
    shutil.copy2(REPO_ROOT / "factorybench" / "harbor_verify.py", tests / "verify.py")
    (tests / "verify.py").chmod(0o755)
    _write_text(
        tests / "test.sh",
        """#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/verify.py"
""",
        executable=True,
    )
    plan = [{"tool": step["tool"], "arguments": step["arguments"]} for step in task["oracle_steps"]]
    _write_json(solution / "plan.json", plan)
    _write_text(
        solution / "solve.py",
        """#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

plan = json.loads(Path(__file__).with_name("plan.json").read_text())
for step in plan:
    subprocess.run(["tool", "call", step["tool"], json.dumps(step["arguments"])], check=True)
""",
        executable=True,
    )
    _write_text(solution / "solve.sh", "#!/bin/bash\nset -euo pipefail\npython3 \"$(dirname \"$0\")/solve.py\"\n", executable=True)


def _model_run_markdown(
    model_runs: list[dict[str, Any]],
    *,
    artifact_pattern: str = "model-runs/{run_slug}.json",
) -> str:
    if not model_runs:
        return "No version-pinned model run is published for this release."
    rows = "\n".join(
        (
            f"| [{run['model']['name']}]({artifact_pattern.format(run_slug=run['run_slug'])}) | "
            f"{run['harness']['name']} {run['harness']['version']} / {run['model']['agent']} "
            f"{run['model']['agent_version']} / {run['model']['reasoning_effort']} | "
            f"{run['aggregate']['tasks']}/100 | {run['aggregate']['mean_factory_score']:.2f} | "
            f"{run['aggregate']['strict_passes']}/{run['aggregate']['tasks']} | {run['selection']} |"
        )
        for run in model_runs
    )
    return (
        "| Model | Harness | Coverage | FactoryScore | Strict passes | Selection |\n"
        "|---|---|---:|---:|---:|---|\n"
        f"{rows}"
    )


def _dataset_card(
    tasks: list[dict[str, Any]],
    qualification: dict[str, Any],
    model_runs: list[dict[str, Any]],
    *,
    model_run_artifact_pattern: str = "model-runs/{run_slug}.json",
) -> str:
    model_run_table = _model_run_markdown(
        model_runs,
        artifact_pattern=model_run_artifact_pattern,
    )
    return f"""---
license: cc-by-4.0
task_categories:
- question-answering
- reinforcement-learning
language:
- en
tags:
- manufacturing
- erp
- agents
- mcp
- deterministic-evaluation
pretty_name: FactoryBench-100
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: test
    path: data/tasks.jsonl
---

# FactoryBench-100

FactoryBench-100 is a 100-task benchmark for employee-grade manufacturing and
ERP decisions. Each public prompt is a short, high-level employee request; it
does not name the systems, files, API calls, answer schema, or execution order.
The isolated SQLite world exposes documented Oracle Fusion Cloud 26a REST
operations alongside Gmail v1, Drive v3, Sheets v4, and Slack Web API operations
over synthetic state.

Harbor runs the authoritative SQLite state and trace in a private root-owned
sidecar. The agent container receives only the task instruction, typed tool CLI,
and tool schemas; it does not receive the database, runtime, verifier, or gold
state.

The data is entirely synthetic. No Oracle software, proprietary UI, customer
record, or copied task is included.

## Metric

The single metric is **FactoryScore**:

`100 × passed deterministic criterion weight / available criterion weight`,
averaged over all evaluated tasks.

Every rubric is task-specific. Criteria cover prerequisite discoveries in any
valid order, netting and date calculations, conditional branches, comparison of
three realistic options, post-write provider readback, the exact ERP and collaboration state transitions,
key answer insights, write containment, and rejected mutations. Harmless failed
exploratory reads do not erase an otherwise correct outcome. Strict pass is
reported only as supporting evidence.

## Qualification

- Canonical executions: {qualification['executions']} (100 oracle + 100 exact replay + {100 * len(NEGATIVE_POLICIES):,} adversarial controls)
- Reference oracle: {qualification['oracle']['mean_score']:.2f} FactoryScore, {qualification['oracle']['passes']}/{len(tasks)} strict passes
- Exact deterministic replay: {qualification['determinism']['exact_episode_matches']}/{qualification['determinism']['replays']} matched
- Negative controls: {sum(row['correct_rejections'] for row in qualification['negative_controls'].values())}/{sum(row['executions'] for row in qualification['negative_controls'].values())} correctly rejected across {len(NEGATIVE_POLICIES)} failure modes
- Single-mutation omission checks: {qualification['mutation_omissions']['detected']}/{qualification['mutation_omissions']['total']} detected

These rows are measured controls, not claims about frontier models.

## Pinned model runs

{model_run_table}

Only exact-release 100/100-task runs are eligible. Full manifests, final model
responses, deterministic verifier verdicts, and task-level traces are mirrored
under `model-runs/`.

## Fields

Each JSONL row includes the natural-language prompt, role, workflow family,
28 heterogeneous context files, reference tools, prerequisite investigation
groups, allowed write tables, weighted human-readable rubric, and metric
contract. Context files are the only agent-visible artifacts. Exact starting
state and verifier contracts are published separately under `evaluation/` for
audit and are not mounted into the agent's asset room. Executable worlds, oracle
traces, and Harbor tasks live in the source repository.

## Links

- Website: {PAGE_URL}
- Source and executable world: {SOURCE_URL}
- Harbor: {HARBOR_URL}

## Influences

The release takes design inspiration from
[Enterprise-Bench](https://hub.harborframework.com/datasets/Enterprise-Bench/l1-l2-bench/latest),
[ERP-Bench](https://hub.harborframework.com/datasets/agentic-labs/erp-bench/latest),
[Mercor APEX](https://www.mercor.com/apex/apex-accounting-leaderboard/), and
[Archipelago](https://github.com/Mercor-Intelligence/archipelago). All task
records and implementations in FactoryBench are independently authored.
"""


def _release_readme(
    qualification: dict[str, Any],
    model_runs: list[dict[str, Any]],
) -> str:
    rows = "\n".join(
        f"| {result['policy'].replace('_', ' ').title()} | {result['mean_score']:.2f} | {result['strict_passes']}/100 |"
        for result in qualification["results"]
    )
    model_run_table = _model_run_markdown(model_runs)
    return f"""# FactoryBench-100 release

FactoryBench-100 contains 100 distinct executable employee decisions across 20
manufacturing and ERP domains. Every task includes a high-level human request,
28 synthetic evidence artifacts, a multi-system starting state, endpoint-pinned
tool contracts, a hidden investigation and calculation graph, three realistic
options, task-specific weighted criteria, an oracle replay, a Harbor 1.4 task,
and a Hugging Face row.

Each Harbor task isolates the authoritative ERP state and trace in a private
root-owned sidecar. The agent container contains no database, runtime, verifier,
or gold state.

## Measured qualification

| Control | FactoryScore | Strict passes |
|---|---:|---:|
{rows}

The oracle is a solvability reference, not a model result. The {len(NEGATIVE_POLICIES)} negative
controls cover no-op and shortcut behavior, missing handoff or evidence,
write-before-read, missing readback, unauthorized mutation, incorrect values,
incorrect operating choice, substitution of stale or irrelevant evidence, a correct
write made to the wrong existing destination, and keyword-only collaboration output.
All {sum(row['correct_rejections'] for row in qualification['negative_controls'].values())} adversarial executions are rejected.

Release qualification also removes every reference mutation individually. All
{qualification['mutation_omissions']['detected']} of {qualification['mutation_omissions']['total']} omissions reduce the score and fail strict completion.

## Pinned model runs

{model_run_table}

Only exact-release 100/100-task runs are eligible for the model leaderboard.

## Layout

- `tasks/`: full public task specifications
- `assets/`: the 28 agent-visible policy, email, Slack, PDF, Excel, CSV, JSON, log, and specification sources per task
- `state/`: exact evaluator starting state, kept outside the agent-visible asset room
- `environment/`: schema and MCP-style tool contracts
- `trajectories/oracle/`: real replayed tool traces and state diffs
- `model-runs/`: pinned model manifests and task-level traces
- `verifiers/contracts/`: exact sealed verifier contracts; `verifiers/*.json` contains measured oracle criterion results
- `reports/`: build and qualification evidence
- `huggingface/`: upload-ready dataset mirror
- `harbor/`: 100 portable Harbor task packages
- `website-data.json`: validated input for the Blobfish benchmark explorer

The world is clean-room and maps each Oracle tool to a documented Fusion Cloud
26a REST operation. The implementation and records are independently authored;
the repository does not distribute Oracle code, proprietary UI, or customer data.
"""


def build_release(
    output: Path = DEFAULT_OUTPUT,
    *,
    _staged: bool = False,
) -> dict[str, Any]:
    if not _staged:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f".{output.name}-build-",
            dir=output.parent,
        ) as temporary:
            temporary_root = Path(temporary)
            staged_output = temporary_root / output.name
            build_report = build_release(staged_output, _staged=True)
            previous_output = temporary_root / "previous-release"
            had_previous = output.exists()
            if had_previous:
                output.replace(previous_output)
            try:
                staged_output.replace(output)
            except BaseException:
                if had_previous and previous_output.exists():
                    previous_output.replace(output)
                raise
            return build_report

    tasks = build_catalog()
    qualification = qualify(tasks)
    model_runs = _load_model_runs()
    if not qualification["qualification_passed"]:
        raise RuntimeError("qualification failed; release was not emitted")
    if output.exists():
        raise ValueError(f"staged release output already exists: {output}")
    output.mkdir(parents=True)
    tools = tool_definitions()
    grouped_tools = [
        {
            "server": server,
            "tools": [tool for tool in tools if tool["_meta"]["factorybench"]["server"] == server],
        }
        for server in sorted({tool["_meta"]["factorybench"]["server"] for tool in tools})
    ]

    _write_text(output / "README.md", _release_readme(qualification, model_runs))
    _write_json(output / "reports" / "qualification.json", qualification)
    _write_json(output / "reports" / "catalog-fidelity.json", catalog_quality_report(tasks))
    _write_json(output / "environment" / "tool-contracts.json", {"servers": grouped_tools})
    _write_json(
        output / MCP_CONFIG_PATH,
        {
            "mcpServers": {
                "factorybench": {
                    "command": "uvx",
                    "args": [
                        "--from",
                        f"git+{SOURCE_URL}@v{BENCHMARK_VERSION}",
                        "factorybench-mcp",
                        "--task",
                        "factorybench-001",
                        "--db",
                        ".factorybench/factorybench-001.db",
                        "--fresh",
                    ],
                }
            }
        },
    )
    shutil.copy2(REPO_ROOT / "factorybench" / "schema.sql", output / "environment" / "schema.sql")

    public_rows: list[dict[str, Any]] = []
    representative_episodes: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="factorybench-release-") as temporary:
        scratch = Path(temporary)
        for task in tasks:
            task_id = task["task_id"]
            _write_json(output / "tasks" / f"{task_id}.json", task)
            public = _public_task(task)
            public_rows.append(public)
            for asset in task["assets"]:
                _write_asset(output / "assets" / task_id / asset["path"], asset)
            _write_json(
                output / "state" / task_id / "starting-state.json",
                task["seed_tables"],
            )
            _write_json(
                output / "verifiers" / "contracts" / f"{task_id}.json",
                task["expected"],
            )
            episode = run_episode(task, "oracle", scratch / f"{task_id}.db")
            _write_json(output / "trajectories" / "oracle" / f"{task_id}.json", episode)
            _write_json(output / "verifiers" / f"{task_id}.json", {key: value for key, value in episode.items() if key not in {"trace", "state_diff"}})
            if task["family"] not in representative_episodes:
                representative_episodes[task["family"]] = episode
            _harbor_task(output / "harbor", task)

    demo_harbor_task = output / "harbor" / "tasks" / "factorybench-001"
    sandbox_bundle = output / "sandbox" / "factorybench-001"
    sandbox_bundle.mkdir(parents=True)
    for name in ("runtime.py", "contracts.py", "schema.sql", "task.json", "tools.json"):
        shutil.copy2(demo_harbor_task / "environment" / name, sandbox_bundle / name)
    shutil.copy2(REPO_ROOT / "factorybench" / "sandbox_bridge.py", sandbox_bundle / "bridge.py")
    _write_text(
        sandbox_bundle / "README.md",
        """# FactoryBench live sandbox bundle

This bundle powers the public benchmark-page MCP demo. Each browser session
receives a private SQLite database and trace. `bridge.py` executes only the
checked-in FactoryWorld tools in `runtime.py`; it does not accept source code,
shell commands, package installation, or arbitrary paths.
""",
    )

    _write_jsonl(output / "tasks" / "tasks.jsonl", public_rows)
    _write_text(output / "huggingface" / "README.md", _dataset_card(tasks, qualification, model_runs))
    _write_jsonl(output / "huggingface" / "data" / "tasks.jsonl", public_rows)
    _write_json(output / "huggingface" / "contracts" / "tool-contracts.json", {"servers": grouped_tools})
    shutil.copy2(output / MCP_CONFIG_PATH, output / "huggingface" / "contracts" / "mcp.json")
    shutil.copytree(output / "assets", output / "huggingface" / "assets")
    shutil.copytree(output / "state", output / "huggingface" / "evaluation" / "state")
    shutil.copytree(
        output / "verifiers" / "contracts",
        output / "huggingface" / "evaluation" / "verifier-contracts",
    )
    shutil.copytree(
        output / "trajectories" / "oracle",
        output / "huggingface" / "evaluation" / "oracle-trajectories",
    )
    _copy_model_run_artifacts(model_runs, output / "model-runs")
    _copy_model_run_artifacts(model_runs, output / "huggingface" / "model-runs")
    _write_text(output / "huggingface" / ".gitattributes", "*.jsonl filter=lfs diff=lfs merge=lfs -text\n")

    _copy_model_run_artifacts(model_runs, output / "harbor" / "model-runs")
    harbor_dataset_files: tuple[Path, ...] = ()
    if model_runs:
        harbor_model_runs = output / "harbor" / "model-runs.json"
        _write_json(harbor_model_runs, _harbor_model_run_bundle(model_runs))
        harbor_dataset_files = (harbor_model_runs,)
    _write_text(
        output / "harbor" / "dataset.toml",
        _harbor_dataset_manifest(
            output / "harbor" / "tasks",
            harbor_dataset_files,
        ),
    )
    _write_text(
        output / "harbor" / "README.md",
        _dataset_card(
            tasks,
            qualification,
            model_runs,
            model_run_artifact_pattern="model-runs.json",
        ),
    )

    shutil.copy2(REPO_ROOT / "LICENSE", output / "LICENSE")
    shutil.copy2(REPO_ROOT / "NOTICE", output / "NOTICE")
    shutil.copy2(REPO_ROOT / "LICENSE-DATA", output / "LICENSE-DATA")
    shutil.copy2(REPO_ROOT / "LICENSE-DATA", output / "huggingface" / "LICENSE")
    shutil.copy2(REPO_ROOT / "LICENSE-DATA", output / "huggingface" / "LICENSE-DATA")
    shutil.copy2(REPO_ROOT / "LICENSE", output / "harbor" / "LICENSE")
    shutil.copy2(REPO_ROOT / "NOTICE", output / "harbor" / "NOTICE")
    shutil.copy2(REPO_ROOT / "LICENSE-DATA", output / "harbor" / "LICENSE-DATA")

    website = _website_data(tasks, qualification, representative_episodes, output, model_runs)
    _write_json(output / "website-data.json", website)

    artifact_files = sorted(path for path in output.rglob("*") if path.is_file())
    fidelity = catalog_quality_report(tasks)
    build_report = {
        "benchmark": BENCHMARK_NAME,
        "version": BENCHMARK_VERSION,
        "task_count": len(tasks),
        "family_count": len(FAMILIES),
        "tool_count": len(tools),
        "metric": "FactoryScore",
        "model_run_count": len(model_runs),
        "source_asset_count": sum(len(task["assets"]) for task in tasks),
        "unique_tool_sequences": fidelity["unique_sequences"],
        "catalog_fidelity_passed": fidelity["passed"],
        "harbor_python_image": HARBOR_PYTHON_IMAGE,
        "qualification_passed": True,
        "artifact_file_count_before_report": len(artifact_files),
        "artifact_bytes_before_report": sum(path.stat().st_size for path in artifact_files),
        "root_sha256": hashlib.sha256(
            "".join(f"{path.relative_to(output).as_posix()}:{_sha256(path)}\n" for path in artifact_files).encode()
        ).hexdigest(),
    }
    _write_json(output / "reports" / "build.json", build_report)
    return build_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FactoryBench-100 release artifacts")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build_release(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
