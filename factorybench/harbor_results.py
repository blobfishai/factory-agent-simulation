"""Import a completed Harbor job as auditable FactoryBench model evidence."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

from .catalog import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    build_catalog,
    catalog_fingerprint,
    task_fingerprint,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "model_runs"
RUN_SLUG = re.compile(r"^[a-z0-9][a-z0-9.-]{0,79}$")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _exact_factory_score(verdict: dict[str, Any]) -> float:
    """Recover the unrounded per-task percentage from deterministic checks."""

    passed_weight = verdict.get("passed_weight")
    total_weight = verdict.get("total_weight")
    if isinstance(passed_weight, (int, float)) and isinstance(total_weight, (int, float)) and total_weight:
        return float(passed_weight) / float(total_weight) * 100
    checks = verdict.get("checks")
    if isinstance(checks, list) and checks and all(isinstance(check, dict) for check in checks):
        return sum(bool(check.get("passed")) for check in checks) / len(checks) * 100
    return float(verdict["factory_score"])


def _trial_dirs(job_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in job_dir.iterdir()
        if path.is_dir() and (path / "result.json").is_file()
    )


def import_harbor_job(
    job_dir: Path,
    output: Path,
    *,
    run_slug: str,
    selection: str,
    reasoning_effort: str,
    harbor_version: str,
    run_url: str | None = None,
    runtime_overlay_path: Path | None = None,
) -> dict[str, Any]:
    if not RUN_SLUG.fullmatch(run_slug):
        raise ValueError("run slug must use lowercase letters, numbers, dots, and hyphens")
    job = _read_json(job_dir / "result.json")
    if job.get("stats", {}).get("n_errored_trials"):
        raise ValueError("cannot publish a Harbor job with errored trials")

    tasks = {task["task_id"]: task for task in build_catalog()}
    trials: list[dict[str, Any]] = []
    for trial_dir in _trial_dirs(job_dir):
        result = _read_json(trial_dir / "result.json")
        if result.get("exception_info") is not None:
            raise ValueError(f"trial has an exception: {trial_dir.name}")
        verdict = _read_json(trial_dir / "verifier" / "verdict.json")
        trace_record = _read_json(trial_dir / "verifier" / "trace.json")
        trajectory = _read_json(trial_dir / "agent" / "trajectory.json")
        task_id = str(verdict["task_id"])
        if task_id not in tasks:
            raise ValueError(f"unknown FactoryBench task in Harbor job: {task_id}")
        trace = trace_record.get("trace")
        if not isinstance(trace, list):
            raise ValueError(f"trial trace is missing: {trial_dir.name}")
        final_metrics = trajectory.get("final_metrics") or {}
        agent = trajectory.get("agent") or {}
        trial_record = {
            "task_id": task_id,
            "benchmark_task_sha256": task_fingerprint(tasks[task_id]),
            "family": tasks[task_id]["family"],
            "score": _exact_factory_score(verdict),
            "strict_pass": bool(verdict["strict_pass"]),
            "tool_calls": len(trace),
            "successful_tool_calls": sum(1 for entry in trace if entry.get("success")),
            "rejected_tool_calls": sum(1 for entry in trace if not entry.get("success")),
            "cost_usd": final_metrics.get("total_cost_usd"),
            "tokens": {
                "input": final_metrics.get("total_prompt_tokens"),
                "cached": final_metrics.get("total_cached_tokens"),
                "output": final_metrics.get("total_completion_tokens"),
            },
            "started_at": result.get("started_at"),
            "finished_at": result.get("finished_at"),
            "task_checksum": result.get("task_checksum"),
            "verdict": verdict,
            "trace": trace,
        }
        _write_json(output / run_slug / "trials" / f"{task_id}.json", trial_record)
        trials.append(
            {
                key: value
                for key, value in trial_record.items()
                if key not in {"verdict", "trace"}
            }
            | {"artifact": f"{run_slug}/trials/{task_id}.json"}
        )

    if not trials:
        raise ValueError("Harbor job contains no completed trials")
    if len({trial["task_id"] for trial in trials}) != len(trials):
        raise ValueError("Harbor job contains duplicate task trials")

    scores = [trial["score"] for trial in trials]
    calls = [trial["tool_calls"] for trial in trials]
    costs = [trial["cost_usd"] for trial in trials if trial["cost_usd"] is not None]
    model_names = {
        (_read_json(path / "agent" / "trajectory.json").get("agent") or {}).get("model_name")
        for path in _trial_dirs(job_dir)
    }
    agent_versions = {
        (_read_json(path / "agent" / "trajectory.json").get("agent") or {}).get("version")
        for path in _trial_dirs(job_dir)
    }
    if len(model_names) != 1 or None in model_names:
        raise ValueError(f"job does not have one pinned model: {model_names}")
    if len(agent_versions) != 1 or None in agent_versions:
        raise ValueError(f"job does not have one pinned agent version: {agent_versions}")

    family_scores = {
        family: round(
            statistics.mean(
                trial["score"] for trial in trials if trial["family"] == family
            ),
            2,
        )
        for family in sorted({trial["family"] for trial in trials})
    }
    model_name = str(next(iter(model_names)))
    agent_version = str(next(iter(agent_versions)))
    runtime_overlay = None
    if runtime_overlay_path is not None:
        runtime_overlay_artifact = f"{run_slug}/runtime-overlay.json"
        runtime_overlay = _read_json(runtime_overlay_path) | {
            "artifact": runtime_overlay_artifact
        }
        _write_json(output / runtime_overlay_artifact, runtime_overlay)
    manifest = {
        "schema_version": "factorybench.model-run.v1",
        "benchmark": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "catalog_sha256": catalog_fingerprint(list(tasks.values())),
        "run_slug": run_slug,
        "job_id": job.get("id"),
        "run_url": run_url,
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "selection": selection,
        "model": {
            "name": model_name,
            "agent": "codex",
            "agent_version": agent_version,
            "reasoning_effort": reasoning_effort,
        },
        "harness": {"name": "Harbor", "version": harbor_version},
        "aggregate": {
            "tasks": len(trials),
            "mean_factory_score": round(statistics.mean(scores), 2),
            "strict_passes": sum(1 for trial in trials if trial["strict_pass"]),
            "strict_pass_rate": round(
                sum(1 for trial in trials if trial["strict_pass"]) / len(trials) * 100,
                2,
            ),
            "average_tool_calls": round(statistics.mean(calls), 2),
            "average_cost_usd": round(statistics.mean(costs), 6) if costs else None,
            "total_cost_usd": round(sum(costs), 6) if costs else None,
            "family_scores": family_scores,
        },
        "featured_task_id": trials[0]["task_id"],
        "trials": trials,
    }
    if runtime_overlay is not None:
        manifest["runtime_overlay"] = runtime_overlay
    _write_json(output / f"{run_slug}.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a completed Harbor FactoryBench job")
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--run-slug", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--reasoning-effort", required=True)
    parser.add_argument("--harbor-version", default="0.21.0")
    parser.add_argument("--run-url")
    parser.add_argument("--runtime-overlay", type=Path)
    args = parser.parse_args()
    manifest = import_harbor_job(
        args.job_dir,
        args.output,
        run_slug=args.run_slug,
        selection=args.selection,
        reasoning_effort=args.reasoning_effort,
        harbor_version=args.harbor_version,
        run_url=args.run_url,
        runtime_overlay_path=args.runtime_overlay,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
