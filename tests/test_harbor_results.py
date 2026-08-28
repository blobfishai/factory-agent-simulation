from __future__ import annotations

import json
from pathlib import Path

import factorybench.release as release_module
from factorybench.catalog import build_catalog, catalog_fingerprint, task_fingerprint
from factorybench.harbor_results import import_harbor_job


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_harbor_import_pins_each_trial_and_the_complete_catalog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    task = build_catalog()[0]
    job = tmp_path / "job"
    trial = job / "trial-001"
    _write_json(
        job / "result.json",
        {
            "id": "job-001",
            "started_at": "2026-01-12T08:00:00Z",
            "finished_at": "2026-01-12T08:05:00Z",
            "stats": {"n_errored_trials": 0},
        },
    )
    _write_json(
        trial / "result.json",
        {
            "started_at": "2026-01-12T08:00:00Z",
            "finished_at": "2026-01-12T08:05:00Z",
            "task_checksum": "harbor-task-sha",
            "exception_info": None,
        },
    )
    _write_json(
        trial / "verifier" / "verdict.json",
        {
            "task_id": task["task_id"],
            "strict_pass": True,
            "factory_score": 100.0,
            "passed_weight": 1.0,
            "total_weight": 1.0,
        },
    )
    _write_json(trial / "verifier" / "trace.json", {"trace": [{"success": True}]})
    _write_json(
        trial / "agent" / "trajectory.json",
        {
            "agent": {"model_name": "test-model", "version": "1.0.0"},
            "final_metrics": {},
        },
    )

    output = tmp_path / "model-runs"
    manifest = import_harbor_job(
        job,
        output,
        run_slug="contract-pinned-run",
        selection="one contract-pinning test task",
        reasoning_effort="max",
        harbor_version="test",
    )

    assert manifest["catalog_sha256"] == catalog_fingerprint(build_catalog())
    assert manifest["trials"][0]["benchmark_task_sha256"] == task_fingerprint(task)
    trial_artifact = json.loads(
        (output / manifest["trials"][0]["artifact"]).read_text(encoding="utf-8")
    )
    assert trial_artifact["benchmark_task_sha256"] == task_fingerprint(task)

    monkeypatch.setattr(release_module, "MODEL_RUNS_ROOT", output)
    assert release_module._load_model_runs() == [manifest]

    manifest["trials"][0]["benchmark_task_sha256"] = "stale-contract"
    _write_json(output / "contract-pinned-run.json", manifest)
    assert release_module._load_model_runs() == []
