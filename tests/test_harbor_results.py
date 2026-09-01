from __future__ import annotations

import json
from pathlib import Path

import pytest

import factorybench.release as release_module
import factorybench.harbor_results as harbor_results_module
from factorybench.catalog import build_catalog, catalog_fingerprint, task_fingerprint
from factorybench.harbor_receipts import directory_manifest_digest, legacy_task_checksum
from factorybench.harbor_results import (
    RELEASE_TASKS_ROOT,
    _released_task_digests,
    import_harbor_job,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_harbor_import_pins_each_trial_and_the_complete_catalog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tasks = build_catalog()
    released_task_digests = _released_task_digests()
    task = tasks[0]
    job = tmp_path / "job"
    runtime_root = tmp_path / "sealed-codex-runtime"
    runtime_bin = runtime_root / "versions" / "node" / "v22.23.2" / "bin"
    runtime_bin.mkdir(parents=True)
    (runtime_root / "nvm.sh").write_text("nvm runtime\n", encoding="utf-8")
    (runtime_bin / "node").write_bytes(b"node")
    (runtime_bin / "codex").write_bytes(b"codex")
    runtime_tree, runtime_files, runtime_bytes = directory_manifest_digest(runtime_root)
    runtime_locks = tmp_path / "runtime-locks.json"
    _write_json(
        runtime_locks,
        {
            "schemaVersion": "blobfish.agent-runtime-locks.v1",
            "runtimes": [
                {
                    "id": "test-runtime",
                    "agent": "codex",
                    "agentVersion": "1.0.0",
                    "nodeVersion": "22.23.2",
                    "nvmVersion": "0.40.2",
                    "platform": "test-platform",
                    "mountTarget": "/home/agent/.nvm",
                    "mountTargets": ["/home/agent/.nvm", "/root/.nvm"],
                    "treeSha256": runtime_tree,
                    "files": runtime_files,
                    "bytes": runtime_bytes,
                    "forbiddenPaths": [".git"],
                    "requiredPaths": [
                        "nvm.sh",
                        "versions/node/v22.23.2/bin/node",
                        "versions/node/v22.23.2/bin/codex",
                    ],
                }
            ],
        },
    )
    monkeypatch.setattr(harbor_results_module, "RUNTIME_LOCKS_PATH", runtime_locks)
    mounts = [
        {
            "source": str(runtime_root),
            "target": "/root/.nvm",
            "type": "bind",
            "read_only": True,
        },
        {
            "source": str(runtime_root),
            "target": "/home/agent/.nvm",
            "type": "bind",
            "read_only": True,
        },
    ]
    locked_agent = {
        "name": "codex",
        "model_name": "test-model",
        "kwargs": {
            "version": "1.0.0",
            "reasoning_effort": "max",
            "reasoning_summary": "detailed",
            "web_search": "disabled",
        },
    }
    locked_environment = {"type": "docker", "mounts": mounts}
    locked_trials = [
        {
            "schema_version": 2,
            "agent_setup_timeout_multiplier": 3.0,
            "task": {
                "name": catalog_task["task_id"],
                "version": "3.3.5",
                "type": "local",
                "digest": released_task_digests[catalog_task["task_id"]],
                "source": "tasks",
                "path": str(
                    (RELEASE_TASKS_ROOT / catalog_task["task_id"]).resolve()
                ),
            },
            "agent": locked_agent,
            "environment": locked_environment,
        }
        for catalog_task in tasks
    ]
    _write_json(
        job / "result.json",
        {
            "id": "job-001",
            "n_total_trials": len(tasks),
            "started_at": "2026-01-12T08:00:00Z",
            "finished_at": "2026-01-12T08:05:00Z",
            "stats": {
                "n_completed_trials": len(tasks),
                "n_errored_trials": 0,
                "n_running_trials": 0,
                "n_pending_trials": 0,
                "n_cancelled_trials": 0,
                "n_retries": 0,
            },
        },
    )
    _write_json(
        job / "config.json",
        {
            "job_name": "job",
            "agent_setup_timeout_multiplier": 3.0,
            "n_concurrent_trials": 1,
            "environment": locked_environment,
            "agents": [locked_agent],
        },
    )
    _write_json(
        job / "lock.json",
        {
            "schema_version": 3,
            "harbor": {"version": "test", "is_editable": False},
            "n_concurrent_trials": 1,
            "retry": {"max_retries": 0},
            "trials": locked_trials,
        },
    )
    for index, catalog_task in enumerate(tasks, start=1):
        trial = job / f"trial-{index:03d}"
        release_task = (RELEASE_TASKS_ROOT / catalog_task["task_id"]).resolve()
        published_name = (
            "blobfishai/factorybench-task-100"
            if catalog_task["task_id"] == "factorybench-100"
            else f"blobfishai/{catalog_task['task_id']}"
        )
        _write_json(trial / "lock.json", locked_trials[index - 1])
        _write_json(
            trial / "result.json",
            {
                "config": {
                    "job_id": "job-001",
                    "task": {"path": str(release_task)},
                },
                "task_id": {"path": str(release_task)},
                "task_name": published_name,
                "task_checksum": legacy_task_checksum(release_task),
                "id": f"trial-id-{index:03d}",
                "trial_name": f"trial-{index:03d}",
                "started_at": "2026-01-12T08:00:00Z",
                "finished_at": "2026-01-12T08:05:00Z",
                "exception_info": None,
                "agent_info": {
                    "name": "codex",
                    "version": "1.0.0",
                    "model_info": {"name": "test-model", "provider": "test-provider"},
                },
                "agent_result": {
                    "n_input_tokens": 0,
                    "n_cache_tokens": 0,
                    "n_output_tokens": 0,
                    "cost_usd": 0.0,
                },
                "verifier_result": {"rewards": {"reward": 1.0}},
            },
        )
        _write_json(
            trial / "verifier" / "verdict.json",
            {
                "task_id": catalog_task["task_id"],
                "strict_pass": True,
                "factory_score": 100.0,
                "passed_weight": 1.0,
                "total_weight": 1.0,
            },
        )
        trace = [] if index == len(tasks) else [
            {
                "tool": "factorybench.context.get",
                "arguments": (
                    {"access_token": "must-not-publish"}
                    if index == 1
                    else {}
                ),
                "success": True,
                "result": (
                    {"source": "/Users/private-user/evidence.json"}
                    if index == 1
                    else {}
                ),
            }
        ]
        _write_json(
            trial / "verifier" / "trace.json",
            {
                "task_id": catalog_task["task_id"],
                "trace": trace,
            },
        )
        final_message = f"Completed {catalog_task['task_id']}."
        if index == 1:
            final_message += " Authorization: Bearer top-secret-token-123."
        _write_json(
            trial / "agent" / "trajectory.json",
                {
                    "schema_version": "ATIF-v1.7",
                    "session_id": f"session-{index:03d}",
                    "agent": {
                        "name": "codex",
                        "model_name": "test-model",
                        "version": "1.0.0",
                    },
                    "final_metrics": {
                        "total_prompt_tokens": 0,
                        "total_cached_tokens": 0,
                        "total_completion_tokens": 0,
                        "total_cost_usd": 0.0,
                    },
                    "steps": [
                        {
                            "source": "agent",
                            "message": final_message,
                        }
                    ],
                },
        )

    runtime_overlay = tmp_path / "runtime-overlay.json"
    semantic_tree_sha256, semantic_file_count = (
        harbor_results_module._release_semantic_manifest()
    )
    _write_json(
        runtime_overlay,
        {
            "schema_version": "factorybench.runtime-overlay.v1",
            "benchmark_version": "3.3.5",
            "task_count": 100,
            "tasks_compared": 100,
            "semantic_files_byte_identical": True,
            "semantic_file_count": semantic_file_count,
            "semantic_tree_sha256": semantic_tree_sha256,
            "unchanged_contract": "Every released semantic file is unchanged.",
            "runtime": {
                "codex": "1.0.0",
                "node": "22.23.2",
                "nvm": "0.40.2",
            },
            "runtime_mount": {
                "id": "test-runtime",
                "read_only": True,
                "targets": ["/root/.nvm", "/home/agent/.nvm"],
                "tree_sha256": runtime_tree,
                "files": runtime_files,
                "bytes": runtime_bytes,
            },
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
        runtime_overlay_path=runtime_overlay,
    )

    assert manifest["catalog_sha256"] == catalog_fingerprint(build_catalog())
    assert manifest["aggregate"]["tasks"] == 100
    assert manifest["trials"][0]["benchmark_task_sha256"] == task_fingerprint(task)
    trial_artifact = json.loads(
        (output / manifest["trials"][0]["artifact"]).read_text(encoding="utf-8")
    )
    assert trial_artifact["benchmark_task_sha256"] == task_fingerprint(task)
    rendered_artifact = json.dumps(trial_artifact, sort_keys=True)
    assert "must-not-publish" not in rendered_artifact
    assert "top-secret-token-123" not in rendered_artifact
    assert "/Users/private-user" not in rendered_artifact
    assert "<redacted>" in rendered_artifact
    assert manifest["trials"][-1]["tool_calls"] == 0

    monkeypatch.setattr(release_module, "MODEL_RUNS_ROOT", output)
    assert release_module._load_model_runs() == [manifest]

    safe_artifact = json.loads(
        (output / manifest["trials"][0]["artifact"]).read_text(encoding="utf-8")
    )
    unsafe_artifact = json.loads(json.dumps(safe_artifact))
    unsafe_artifact["trace"][0]["arguments"]["access_token"] = (
        "inserted-after-import"
    )
    _write_json(output / manifest["trials"][0]["artifact"], unsafe_artifact)
    with pytest.raises(ValueError, match="sensitive field was not redacted"):
        release_module._load_model_runs()
    _write_json(output / manifest["trials"][0]["artifact"], safe_artifact)

    manifest["trials"][0]["benchmark_task_sha256"] = "stale-contract"
    _write_json(output / "contract-pinned-run.json", manifest)
    assert release_module._load_model_runs() == []

    with pytest.raises(ValueError, match="already exists and is immutable"):
        import_harbor_job(
            job,
            output,
            run_slug="contract-pinned-run",
            selection="immutable test run",
            reasoning_effort="max",
            harbor_version="test",
        )

    mismatched_reasoning_output = tmp_path / "mismatched-reasoning-run"
    with pytest.raises(ValueError, match="agent metadata"):
        import_harbor_job(
            job,
            mismatched_reasoning_output,
            run_slug="mismatched-reasoning-run",
            selection="mismatched reasoning test run",
            reasoning_effort="low",
            harbor_version="test",
        )
    assert not mismatched_reasoning_output.exists()

    unsafe_overlay = json.loads(runtime_overlay.read_text(encoding="utf-8"))
    unsafe_overlay["runtime_mount"]["source"] = "/Users/example/private-runtime"
    unsafe_overlay_path = tmp_path / "unsafe-runtime-overlay.json"
    _write_json(unsafe_overlay_path, unsafe_overlay)
    unsafe_overlay_output = tmp_path / "unsafe-overlay-run"
    with pytest.raises(ValueError, match="machine-local source path"):
        import_harbor_job(
            job,
            unsafe_overlay_output,
            run_slug="unsafe-overlay-run",
            selection="unsafe overlay test run",
            reasoning_effort="max",
            harbor_version="test",
            runtime_overlay_path=unsafe_overlay_path,
        )
    assert not unsafe_overlay_output.exists()

    tampered_overlay = json.loads(runtime_overlay.read_text(encoding="utf-8"))
    tampered_overlay["runtime_mount"]["tree_sha256"] = "0" * 64
    tampered_overlay_path = tmp_path / "tampered-runtime-overlay.json"
    _write_json(tampered_overlay_path, tampered_overlay)
    tampered_overlay_output = tmp_path / "tampered-overlay-run"
    with pytest.raises(
        ValueError,
        match="checked-in runtime lock|digest disagrees",
    ):
        import_harbor_job(
            job,
            tampered_overlay_output,
            run_slug="tampered-overlay-run",
            selection="tampered overlay test run",
            reasoning_effort="max",
            harbor_version="test",
            runtime_overlay_path=tampered_overlay_path,
        )
    assert not tampered_overlay_output.exists()

    lock_path = job / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["retry"]["max_retries"] = 1
    _write_json(lock_path, lock)
    retry_output = tmp_path / "retry-enabled-run"
    with pytest.raises(ValueError, match="job lock"):
        import_harbor_job(
            job,
            retry_output,
            run_slug="retry-enabled-run",
            selection="retry policy test run",
            reasoning_effort="max",
            harbor_version="test",
        )
    assert not retry_output.exists()
    lock["retry"]["max_retries"] = 0
    _write_json(lock_path, lock)

    released_digest = lock["trials"][0]["task"]["digest"]
    lock["trials"][0]["task"]["digest"] = f"sha256:{'0' * 64}"
    _write_json(lock_path, lock)
    modified_task_output = tmp_path / "modified-task-run"
    with pytest.raises(ValueError, match="non-release task pin"):
        import_harbor_job(
            job,
            modified_task_output,
            run_slug="modified-task-run",
            selection="modified task test run",
            reasoning_effort="max",
            harbor_version="test",
        )
    assert not modified_task_output.exists()
    lock["trials"][0]["task"]["digest"] = released_digest
    _write_json(lock_path, lock)

    inconsistent_trajectory = job / "trial-100" / "agent" / "trajectory.json"
    inconsistent = json.loads(inconsistent_trajectory.read_text(encoding="utf-8"))
    inconsistent["agent"]["version"] = "different-version"
    _write_json(inconsistent_trajectory, inconsistent)
    inconsistent_output = tmp_path / "inconsistent-model-run"
    with pytest.raises(ValueError, match="native trajectory"):
        import_harbor_job(
            job,
            inconsistent_output,
            run_slug="inconsistent-run",
            selection="inconsistent model test run",
            reasoning_effort="max",
            harbor_version="test",
            runtime_overlay_path=runtime_overlay,
        )
    assert not inconsistent_output.exists()
    inconsistent["agent"]["version"] = "1.0.0"
    _write_json(inconsistent_trajectory, inconsistent)

    missing_result = job / "trial-100" / "result.json"
    missing_result.rename(missing_result.with_suffix(".missing"))
    partial_output = tmp_path / "partial-model-runs"
    with pytest.raises(ValueError, match="complete current FactoryBench catalog"):
        import_harbor_job(
            job,
            partial_output,
            run_slug="partial-run",
            selection="incomplete test run",
            reasoning_effort="max",
            harbor_version="test",
            runtime_overlay_path=runtime_overlay,
        )
    assert not partial_output.exists()
