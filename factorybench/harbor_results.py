"""Import a completed Harbor job as auditable FactoryBench model evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from .catalog import (
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    build_catalog,
    catalog_fingerprint,
    task_fingerprint,
)
from .harbor_receipts import (
    bind_trial_task,
    directory_manifest_digest,
    sha256_file,
    validate_job_lock,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "model_runs"
RUN_SLUG = re.compile(r"^[a-z0-9][a-z0-9.-]{0,79}$")
SHA256_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
ALLOWED_CONCURRENT_TRIALS = frozenset({1, 2, 3, 4})
REQUIRED_SETUP_TIMEOUT_MULTIPLIER = 3.0
RELEASE_DATASET_PATH = REPO_ROOT / "benchmark" / "factorybench100" / "harbor" / "dataset.toml"
RELEASE_TASKS_ROOT = RELEASE_DATASET_PATH.parent / "tasks"
RUNTIME_LOCKS_PATH = REPO_ROOT / "benchmark" / "model-runtime-locks.json"
REQUIRED_RUNTIME_TARGETS = frozenset({"/root/.nvm", "/home/agent/.nvm"})
EFFECTIVE_RUNTIME_TARGET = "/home/agent/.nvm"
HARBOR_TASK_ID_ALIASES = {
    # Harbor task names share a namespace with dataset names, so the final task
    # cannot itself be published as blobfishai/factorybench-100.
    "factorybench-task-100": "factorybench-100",
}
SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "client_secret",
    "code_verifier",
    "cookie",
    "credential",
    "csrf",
    "oauth_code",
    "password",
    "private_key",
    "secret",
    "session_id",
    "token",
)
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)(\b(?:access[_-]?token|api[_-]?key|authorization|client[_-]?secret|"
        r"code[_-]?verifier|password|refresh[_-]?token)\b\s*[:=]\s*[\"']?)[^\s,;\"'}]+"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bpat-[a-z0-9-]{2,12}-[A-Za-z0-9_-]{16,}\b", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----.*?"
        r"-----END(?: [A-Z]+)? PRIVATE KEY-----",
        re.DOTALL,
    ),
)
PRIVATE_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/[^/\s\"']+(?:/[^\s,;\"'}]*)?"),
    re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+(?:\\[^\s,;\"'}]*)?"),
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _scrub_public_value(value: Any, key: str = "") -> Any:
    """Redact credentials and machine-local home paths before public staging."""

    if any(part in key.casefold() for part in SENSITIVE_KEY_PARTS):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            str(child_key): _scrub_public_value(child, str(child_key))
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        return [_scrub_public_value(child) for child in value]
    if isinstance(value, str):
        for pattern in SENSITIVE_TEXT_PATTERNS:
            value = pattern.sub(
                r"\1<redacted>" if pattern.groups else "<redacted>",
                value,
            )
        for pattern in PRIVATE_PATH_PATTERNS:
            value = pattern.sub("<redacted-home-path>", value)
    return value


def _assert_public_value_safe(value: Any, *, location: str = "artifact") -> None:
    """Fail closed if a public artifact still contains recognized sensitive data."""

    if isinstance(value, dict):
        for key, child in value.items():
            if (
                any(part in str(key).casefold() for part in SENSITIVE_KEY_PARTS)
                and isinstance(child, str)
                and child != "<redacted>"
            ):
                raise ValueError(f"{location}: sensitive field was not redacted")
            _assert_public_value_safe(child, location=f"{location}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _assert_public_value_safe(child, location=f"{location}[{index}]")
        return
    if not isinstance(value, str):
        return
    if _scrub_public_value(value) != value:
        raise ValueError(f"{location}: sensitive text remained after redaction")


def _public_value(value: Any, *, location: str) -> Any:
    scrubbed = _scrub_public_value(value)
    _assert_public_value_safe(scrubbed, location=location)
    return scrubbed


def _logical_task_id(published_name: Any) -> str | None:
    if not isinstance(published_name, str) or not published_name.startswith("blobfishai/"):
        return None
    published_task_id = published_name.removeprefix("blobfishai/")
    if not published_task_id or "/" in published_task_id:
        return None
    return HARBOR_TASK_ID_ALIASES.get(published_task_id, published_task_id)


def _finite_number(value: Any, *, minimum: float, maximum: float | None = None) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    return math.isfinite(numeric) and numeric >= minimum and (
        maximum is None or numeric <= maximum
    )


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


def _validate_trial_measurements(
    result: dict[str, Any],
    verdict: dict[str, Any],
    trace_record: dict[str, Any],
    trajectory: dict[str, Any],
    *,
    task_id: str,
    model_name: str,
    agent_version: str,
    trial_name: str,
) -> tuple[float, list[dict[str, Any]], dict[str, Any], str, str]:
    """Reconcile the result, verifier, and native agent receipts for one trial."""

    if (
        not isinstance(result.get("id"), str)
        or not result["id"]
        or result.get("trial_name") != trial_name
        or not isinstance(result.get("started_at"), str)
        or not result["started_at"]
        or not isinstance(result.get("finished_at"), str)
        or not result["finished_at"]
    ):
        raise ValueError(f"trial has incomplete execution identity: {trial_name}")

    score = _exact_factory_score(verdict)
    reported_score = verdict.get("factory_score")
    strict_pass = verdict.get("strict_pass")
    rewards = result.get("verifier_result")
    rewards = rewards.get("rewards") if isinstance(rewards, dict) else None
    reward = rewards.get("reward") if isinstance(rewards, dict) else None
    if (
        not _finite_number(score, minimum=0, maximum=100)
        or not _finite_number(reported_score, minimum=0, maximum=100)
        or not math.isclose(score, float(reported_score), rel_tol=0, abs_tol=1e-8)
        or not isinstance(strict_pass, bool)
        or not _finite_number(reward, minimum=0, maximum=1)
        or not math.isclose(score, float(reward) * 100, rel_tol=0, abs_tol=1e-8)
    ):
        raise ValueError(f"trial score receipts disagree: {trial_name}")

    trace = trace_record.get("trace")
    if (
        trace_record.get("task_id") != task_id
        or not isinstance(trace, list)
        or not all(
            isinstance(entry, dict)
            and isinstance(entry.get("tool"), str)
            and bool(entry["tool"])
            and isinstance(entry.get("arguments"), dict)
            and isinstance(entry.get("success"), bool)
            and "result" in entry
            for entry in trace
        )
    ):
        raise ValueError(f"trial verifier trace is incomplete: {trial_name}")

    trajectory_agent = trajectory.get("agent")
    final_metrics = trajectory.get("final_metrics")
    steps = trajectory.get("steps")
    if (
        trajectory.get("schema_version") != "ATIF-v1.7"
        or not isinstance(trajectory.get("session_id"), str)
        or not trajectory["session_id"]
        or not isinstance(trajectory_agent, dict)
        or trajectory_agent.get("name") != "codex"
        or trajectory_agent.get("model_name") != model_name
        or trajectory_agent.get("version") != agent_version
        or not isinstance(final_metrics, dict)
        or not isinstance(steps, list)
        or not steps
        or not all(isinstance(step, dict) for step in steps)
    ):
        raise ValueError(f"trial native trajectory is incomplete: {trial_name}")
    final_messages = [
        step["message"].strip()
        for step in steps
        if step.get("source") == "agent"
        and isinstance(step.get("message"), str)
        and step["message"].strip()
    ]
    if not final_messages:
        raise ValueError(f"trial has no final agent response: {trial_name}")

    token_fields = {
        "total_prompt_tokens": "n_input_tokens",
        "total_cached_tokens": "n_cache_tokens",
        "total_completion_tokens": "n_output_tokens",
    }
    agent_result = result.get("agent_result")
    if not isinstance(agent_result, dict):
        raise ValueError(f"trial has no agent usage receipt: {trial_name}")
    for metric_key, result_key in token_fields.items():
        metric_value = final_metrics.get(metric_key)
        result_value = agent_result.get(result_key)
        if (
            isinstance(metric_value, bool)
            or not isinstance(metric_value, int)
            or metric_value < 0
            or result_value != metric_value
        ):
            raise ValueError(f"trial token receipts disagree: {trial_name}")
    cost = final_metrics.get("total_cost_usd")
    result_cost = agent_result.get("cost_usd")
    if (
        not _finite_number(cost, minimum=0)
        or not _finite_number(result_cost, minimum=0)
        or not math.isclose(float(cost), float(result_cost), rel_tol=0, abs_tol=1e-12)
    ):
        raise ValueError(f"trial cost receipts disagree: {trial_name}")

    agent_info = result.get("agent_info")
    model_info = agent_info.get("model_info") if isinstance(agent_info, dict) else None
    provider = model_info.get("provider") if isinstance(model_info, dict) else None
    if (
        not isinstance(agent_info, dict)
        or agent_info.get("name") != "codex"
        or agent_info.get("version") != agent_version
        or not isinstance(model_info, dict)
        or model_info.get("name") != model_name
        or not isinstance(provider, str)
        or not provider
    ):
        raise ValueError(f"trial result model metadata disagrees: {trial_name}")
    return score, trace, final_metrics, final_messages[-1], provider


def _trial_dirs(job_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in job_dir.iterdir()
        if path.is_dir() and (path / "result.json").is_file()
    )


def _released_task_digests() -> dict[str, str]:
    dataset = tomllib.loads(RELEASE_DATASET_PATH.read_text(encoding="utf-8"))
    metadata = dataset.get("dataset") or {}
    if (
        metadata.get("name") != "blobfishai/factorybench-100"
        or metadata.get("version") != BENCHMARK_VERSION
    ):
        raise ValueError("released Harbor dataset metadata is stale")
    digests: dict[str, str] = {}
    for row in dataset.get("tasks") or []:
        name = row.get("name") if isinstance(row, dict) else None
        digest = row.get("digest") if isinstance(row, dict) else None
        task_id = _logical_task_id(name)
        if (
            not isinstance(task_id, str)
            or task_id in digests
            or not isinstance(digest, str)
            or not SHA256_DIGEST.fullmatch(digest)
        ):
            raise ValueError("released Harbor dataset contains an invalid task binding")
        digests[task_id] = digest
    if set(digests) != {task["task_id"] for task in build_catalog()}:
        raise ValueError("released Harbor dataset does not cover the current catalog")
    return digests


def _release_semantic_manifest() -> tuple[str, int]:
    """Commit every released task file except the runtime-only Dockerfile."""

    rows: list[str] = []
    for path in sorted(RELEASE_TASKS_ROOT.rglob("*")):
        if not path.is_file() or (
            path.name == "Dockerfile" and path.parent.name == "environment"
        ):
            continue
        relative = path.relative_to(RELEASE_TASKS_ROOT).as_posix()
        rows.append(f"{relative}\0{sha256_file(path)}")
    return hashlib.sha256("\n".join(rows).encode()).hexdigest(), len(rows)


def _validate_job_contract(
    job_dir: Path,
    job: dict[str, Any],
    *,
    expected_task_digests: dict[str, str],
    reasoning_effort: str,
    harbor_version: str,
) -> tuple[str, str, tuple[str, ...], str | None, dict[str, Any]]:
    """Bind source publication metadata to the completed Harbor job itself."""

    config = _read_json(job_dir / "config.json")
    lock = _read_json(job_dir / "lock.json")
    agents = config.get("agents")
    concurrency = config.get("n_concurrent_trials")
    setup_multiplier = config.get("agent_setup_timeout_multiplier")
    environment = config.get("environment")
    if (
        config.get("job_name") != job_dir.name
        or not isinstance(agents, list)
        or len(agents) != 1
        or not isinstance(agents[0], dict)
        or isinstance(concurrency, bool)
        or concurrency not in ALLOWED_CONCURRENT_TRIALS
        or isinstance(setup_multiplier, bool)
        or setup_multiplier != REQUIRED_SETUP_TIMEOUT_MULTIPLIER
        or not isinstance(environment, dict)
        or environment.get("type") != "docker"
    ):
        raise ValueError("Harbor job does not use the required bounded setup-3x policy")

    mounts = environment.get("mounts")
    if not isinstance(mounts, list):
        raise ValueError("Harbor job does not declare its runtime mounts")
    mount_targets: list[str] = []
    mount_sources: set[str] = set()
    for mount in mounts:
        source = mount.get("source") if isinstance(mount, dict) else None
        target = mount.get("target") if isinstance(mount, dict) else None
        if (
            not isinstance(mount, dict)
            or mount.get("type") != "bind"
            or mount.get("read_only") is not True
            or not isinstance(source, str)
            or not source.startswith("/")
            or not isinstance(target, str)
            or not target.startswith("/")
            or target in mount_targets
        ):
            raise ValueError("Harbor job contains an unsafe or ambiguous runtime mount")
        mount_sources.add(source)
        mount_targets.append(target)
    if len(mount_sources) > 1:
        raise ValueError("Harbor job runtime mounts do not share one sealed source tree")
    if set(mount_targets) != REQUIRED_RUNTIME_TARGETS:
        raise ValueError("Harbor job does not use the exact sealed runtime target set")

    agent = agents[0]
    kwargs = agent.get("kwargs")
    model_name = agent.get("model_name")
    agent_version = kwargs.get("version") if isinstance(kwargs, dict) else None
    if (
        agent.get("name") != "codex"
        or not isinstance(kwargs, dict)
        or not isinstance(model_name, str)
        or not model_name
        or not isinstance(agent_version, str)
        or not agent_version
        or kwargs.get("reasoning_effort") != reasoning_effort
        or kwargs.get("reasoning_summary") != "detailed"
        or kwargs.get("web_search") != "disabled"
    ):
        raise ValueError("Harbor job agent metadata disagrees with the published model pin")

    expected_task_ids = set(expected_task_digests)
    stats = job.get("stats")
    if not isinstance(stats, dict):
        raise ValueError("Harbor job has no final execution statistics")
    if (
        job.get("n_total_trials") != len(expected_task_ids)
        or not isinstance(job.get("started_at"), str)
        or not job["started_at"]
        or not isinstance(job.get("finished_at"), str)
        or not job["finished_at"]
        or any(
        isinstance(stats.get(key), bool)
        or not isinstance(stats.get(key), int)
        or stats.get(key) != expected
        for key, expected in {
            "n_completed_trials": len(expected_task_ids),
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        }.items()
        )
    ):
        raise ValueError("Harbor job is not one complete, error-free 100-task execution")

    harbor = lock.get("harbor")
    retry = lock.get("retry")
    locked_trials = lock.get("trials")
    if (
        lock.get("schema_version") != 3
        or not isinstance(harbor, dict)
        or harbor.get("version") != harbor_version
        or harbor.get("is_editable") is not False
        or lock.get("n_concurrent_trials") != concurrency
        or not isinstance(retry, dict)
        or retry.get("max_retries") != 0
        or not isinstance(locked_trials, list)
        or len(locked_trials) != len(expected_task_ids)
    ):
        raise ValueError("Harbor job lock disagrees with the published execution policy")

    locked_task_ids: set[str] = set()
    locked_digests: set[str] = set()
    for trial in locked_trials:
        task = trial.get("task") if isinstance(trial, dict) else None
        locked_agent = trial.get("agent") if isinstance(trial, dict) else None
        locked_environment = trial.get("environment") if isinstance(trial, dict) else None
        if not isinstance(task, dict):
            raise ValueError("Harbor job lock contains an invalid task entry")
        task_id = task.get("name")
        digest = task.get("digest")
        if (
            trial.get("schema_version") != 2
            or trial.get("agent_setup_timeout_multiplier")
            != REQUIRED_SETUP_TIMEOUT_MULTIPLIER
            or not isinstance(locked_agent, dict)
            or locked_agent.get("name") != "codex"
            or locked_agent.get("model_name") != model_name
            or not isinstance(locked_agent.get("kwargs"), dict)
            or locked_agent["kwargs"].get("version") != agent_version
            or locked_agent["kwargs"].get("reasoning_effort") != reasoning_effort
            or locked_agent["kwargs"].get("reasoning_summary") != "detailed"
            or locked_agent["kwargs"].get("web_search") != "disabled"
            or not isinstance(locked_environment, dict)
            or locked_environment.get("type") != "docker"
            or locked_environment.get("mounts") != mounts
            or not isinstance(task_id, str)
            or task.get("version") != BENCHMARK_VERSION
            or task.get("type") != "local"
            or task.get("source") != "tasks"
            or not isinstance(digest, str)
            or not SHA256_DIGEST.fullmatch(digest)
            or expected_task_digests.get(task_id) != digest
        ):
            raise ValueError("Harbor job lock contains a non-release task pin")
        locked_task_ids.add(task_id)
        locked_digests.add(digest)
    if locked_task_ids != expected_task_ids or len(locked_digests) != len(expected_task_ids):
        raise ValueError("Harbor job lock does not bind every exact-release task once")
    mounted_source = next(iter(mount_sources)) if mount_sources else None
    return model_name, agent_version, tuple(sorted(mount_targets)), mounted_source, lock


def _validate_runtime_overlay(
    overlay: dict[str, Any],
    *,
    task_count: int,
    mounted_targets: tuple[str, ...],
    mounted_source: str | None = None,
    agent_version: str | None = None,
    verify_source: bool = True,
) -> None:
    required_overlay_keys = {
        "schema_version",
        "benchmark_version",
        "task_count",
        "tasks_compared",
        "semantic_files_byte_identical",
        "semantic_file_count",
        "semantic_tree_sha256",
        "unchanged_contract",
        "runtime",
        "runtime_mount",
    }
    if not required_overlay_keys <= set(overlay) or not set(overlay) <= (
        required_overlay_keys | {"artifact"}
    ):
        raise ValueError("runtime overlay contains an unsupported field")
    semantic_tree_sha256, semantic_file_count = _release_semantic_manifest()
    if (
        overlay.get("schema_version") != "factorybench.runtime-overlay.v1"
        or overlay.get("benchmark_version") != BENCHMARK_VERSION
        or overlay.get("task_count") != task_count
        or overlay.get("tasks_compared") != task_count
        or overlay.get("semantic_files_byte_identical") is not True
        or not isinstance(overlay.get("semantic_file_count"), int)
        or overlay["semantic_file_count"] != semantic_file_count
        or not isinstance(overlay.get("semantic_tree_sha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", overlay["semantic_tree_sha256"])
        or overlay["semantic_tree_sha256"] != semantic_tree_sha256
        or not isinstance(overlay.get("unchanged_contract"), str)
        or not overlay["unchanged_contract"].strip()
    ):
        raise ValueError("runtime overlay does not bind the complete current release")
    if "/Users/" in json.dumps(overlay, sort_keys=True):
        raise ValueError("runtime overlay exposes a machine-local source path")

    runtime_mount = overlay.get("runtime_mount")
    if runtime_mount is None:
        if mounted_targets or mounted_source is not None:
            raise ValueError("runtime overlay omits the job's mounted runtime")
        return
    targets = runtime_mount.get("targets") if isinstance(runtime_mount, dict) else None
    runtime = overlay.get("runtime")
    if (
        not isinstance(runtime_mount, dict)
        or set(runtime_mount)
        != {"id", "read_only", "targets", "tree_sha256", "files", "bytes"}
        or runtime_mount.get("read_only") is not True
        or not isinstance(targets, list)
        or not all(isinstance(target, str) and target.startswith("/") for target in targets)
        or len(set(targets)) != len(targets)
        or set(targets) != REQUIRED_RUNTIME_TARGETS
        or tuple(sorted(targets)) != mounted_targets
        or not isinstance(runtime_mount.get("tree_sha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", runtime_mount["tree_sha256"])
        or not isinstance(runtime_mount.get("files"), int)
        or runtime_mount["files"] <= 0
        or not isinstance(runtime_mount.get("bytes"), int)
        or runtime_mount["bytes"] <= 0
        or "source" in runtime_mount
        or not isinstance(runtime_mount.get("id"), str)
        or not runtime_mount["id"]
        or not isinstance(runtime, dict)
        or set(runtime) != {"codex", "node", "nvm"}
        or runtime.get("codex") != agent_version
        or not isinstance(runtime.get("node"), str)
        or not runtime["node"]
        or not isinstance(runtime.get("nvm"), str)
        or not runtime["nvm"]
    ):
        raise ValueError("runtime overlay does not describe a sealed read-only runtime")
    locks = _read_json(RUNTIME_LOCKS_PATH)
    if locks.get("schemaVersion") != "blobfish.agent-runtime-locks.v1":
        raise ValueError("unsupported checked-in runtime lock schema")
    candidates = [
        lock
        for lock in locks.get("runtimes") or []
        if isinstance(lock, dict)
        and lock.get("id") == runtime_mount["id"]
        and lock.get("agent") == "codex"
        and lock.get("agentVersion") == agent_version
        and lock.get("nodeVersion") == runtime["node"]
        and lock.get("nvmVersion") == runtime["nvm"]
        and lock.get("mountTarget") == EFFECTIVE_RUNTIME_TARGET
        and lock.get("mountTargets") == sorted(targets)
    ]
    if len(candidates) != 1:
        raise ValueError("runtime overlay has no unique checked-in runtime lock")
    runtime_lock = candidates[0]
    if (
        runtime_lock.get("treeSha256") != runtime_mount["tree_sha256"]
        or runtime_lock.get("files") != runtime_mount["files"]
        or runtime_lock.get("bytes") != runtime_mount["bytes"]
    ):
        raise ValueError("runtime overlay disagrees with its checked-in runtime lock")
    if not verify_source:
        return
    if not isinstance(mounted_source, str) or not mounted_source:
        raise ValueError("runtime overlay cannot be verified without its mounted source")
    runtime_root = Path(mounted_source).expanduser().resolve()
    required_paths = runtime_lock.get("requiredPaths")
    forbidden_paths = runtime_lock.get("forbiddenPaths")
    if not isinstance(required_paths, list) or not required_paths or not all(
        isinstance(relative, str)
        and relative
        and (runtime_root / relative).is_file()
        for relative in required_paths
    ):
        raise ValueError("mounted runtime lacks its pinned Node or Codex executable")
    if not isinstance(forbidden_paths, list) or any(
        not isinstance(relative, str)
        or not relative
        or (runtime_root / relative).exists()
        for relative in forbidden_paths
    ):
        raise ValueError("mounted runtime contains a forbidden checked-in path")
    tree_sha256, files, total_bytes = directory_manifest_digest(runtime_root)
    if (
        runtime_mount.get("tree_sha256") != tree_sha256
        or runtime_mount.get("files") != files
        or runtime_mount.get("bytes") != total_bytes
    ):
        raise ValueError("runtime overlay digest disagrees with the mounted source tree")


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
    manifest_path = output / f"{run_slug}.json"
    run_artifact_root = output / run_slug
    if manifest_path.exists() or run_artifact_root.exists():
        raise ValueError(f"model run already exists and is immutable: {run_slug}")
    if not isinstance(selection, str) or not selection.strip():
        raise ValueError("model run selection disclosure must be non-empty")
    tasks = {task["task_id"]: task for task in build_catalog()}
    job = _read_json(job_dir / "result.json")
    job_id = job.get("id")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Harbor job lacks an immutable job id")
    released_task_digests = _released_task_digests()
    (
        pinned_model_name,
        pinned_agent_version,
        mounted_targets,
        mounted_source,
        job_lock,
    ) = _validate_job_contract(
        job_dir,
        job,
        expected_task_digests=released_task_digests,
        reasoning_effort=reasoning_effort,
        harbor_version=harbor_version,
    )
    runtime_overlay = None
    if runtime_overlay_path is not None:
        runtime_overlay_artifact = f"{run_slug}/runtime-overlay.json"
        runtime_overlay = _read_json(runtime_overlay_path)
        _validate_runtime_overlay(
            runtime_overlay,
            task_count=len(tasks),
            mounted_targets=mounted_targets,
            mounted_source=mounted_source,
            agent_version=pinned_agent_version,
        )
        runtime_overlay = runtime_overlay | {"artifact": runtime_overlay_artifact}
    elif mounted_targets:
        raise ValueError("Harbor job mounted a runtime but no runtime overlay was disclosed")

    trials: list[dict[str, Any]] = []
    trial_artifacts: list[tuple[Path, dict[str, Any]]] = []
    trial_locks: list[dict[str, Any]] = []
    trial_ids: set[str] = set()
    providers: set[str] = set()
    for trial_dir in _trial_dirs(job_dir):
        result = _read_json(trial_dir / "result.json")
        if result.get("exception_info") is not None:
            raise ValueError(f"trial has an exception: {trial_dir.name}")
        result_config = result.get("config")
        if (
            not isinstance(result_config, dict)
            or result_config.get("job_id") != job_id
        ):
            raise ValueError(f"trial belongs to another Harbor job: {trial_dir.name}")
        resolved_task, task_receipt, trial_lock = bind_trial_task(
            trial_dir=trial_dir,
            result=result,
            tasks_root=RELEASE_TASKS_ROOT,
            benchmark_version=BENCHMARK_VERSION,
        )
        verdict = _read_json(trial_dir / "verifier" / "verdict.json")
        trace_record = _read_json(trial_dir / "verifier" / "trace.json")
        trajectory = _read_json(trial_dir / "agent" / "trajectory.json")
        task_id = verdict.get("task_id")
        if not isinstance(task_id, str) or task_id not in tasks:
            raise ValueError(f"unknown FactoryBench task in Harbor job: {task_id}")
        if (
            resolved_task.name != task_id
            or task_receipt["task_id"] != task_id
            or task_receipt["harbor_task_digest"] != released_task_digests[task_id]
        ):
            raise ValueError(f"trial task receipt disagrees with its verdict: {trial_dir.name}")
        trial_locks.append(trial_lock)
        score, trace, final_metrics, final_response, provider = _validate_trial_measurements(
            result,
            verdict,
            trace_record,
            trajectory,
            task_id=task_id,
            model_name=pinned_model_name,
            agent_version=pinned_agent_version,
            trial_name=trial_dir.name,
        )
        trial_ids.add(result["id"])
        providers.add(provider)
        public_verdict = _public_value(verdict, location=f"{trial_dir.name}.verdict")
        public_trace = _public_value(trace, location=f"{trial_dir.name}.trace")
        public_final_response = _public_value(
            final_response,
            location=f"{trial_dir.name}.final_response",
        )
        trial_record = {
            "task_id": task_id,
            "benchmark_task_sha256": task_fingerprint(tasks[task_id]),
            "harbor_task_digest": task_receipt["harbor_task_digest"],
            "trial_task_checksum": task_receipt["trial_task_checksum"],
            "trial_lock_sha256": task_receipt["trial_lock_sha256"],
            "published_files": task_receipt["published_files"],
            "published_bytes": task_receipt["published_bytes"],
            "family": tasks[task_id]["family"],
            "score": score,
            "strict_pass": verdict["strict_pass"],
            "tool_calls": len(trace),
            "successful_tool_calls": sum(1 for entry in trace if entry.get("success")),
            "rejected_tool_calls": sum(1 for entry in trace if not entry.get("success")),
            "cost_usd": final_metrics.get("total_cost_usd"),
            "tokens": {
                "input": final_metrics.get("total_prompt_tokens"),
                "cached": final_metrics.get("total_cached_tokens"),
                "output": final_metrics.get("total_completion_tokens"),
            },
            "final_response": public_final_response,
            "final_response_sha256": _canonical_json_sha256(public_final_response),
            "public_trace_sha256": _canonical_json_sha256(public_trace),
            "started_at": result.get("started_at"),
            "finished_at": result.get("finished_at"),
            "task_checksum": result.get("task_checksum"),
            "source_receipts": {
                "result_sha256": sha256_file(trial_dir / "result.json"),
                "trajectory_sha256": sha256_file(trial_dir / "agent" / "trajectory.json"),
                "verdict_sha256": sha256_file(trial_dir / "verifier" / "verdict.json"),
                "trace_sha256": sha256_file(trial_dir / "verifier" / "trace.json"),
            },
            "verdict": public_verdict,
            "trace": public_trace,
        }
        _assert_public_value_safe(trial_record, location=f"{trial_dir.name}.artifact")
        artifact_path = output / run_slug / "trials" / f"{task_id}.json"
        trial_artifacts.append((artifact_path, trial_record))
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
    trials.sort(key=lambda trial: trial["task_id"])
    trial_artifacts.sort(key=lambda item: item[0].as_posix())
    if len({trial["task_id"] for trial in trials}) != len(trials):
        raise ValueError("Harbor job contains duplicate task trials")
    if len(trial_ids) != len(trials):
        raise ValueError("Harbor job contains duplicate immutable trial ids")
    observed_task_ids = {trial["task_id"] for trial in trials}
    expected_task_ids = set(tasks)
    if observed_task_ids != expected_task_ids:
        missing = sorted(expected_task_ids - observed_task_ids)
        unexpected = sorted(observed_task_ids - expected_task_ids)
        raise ValueError(
            "Harbor job must contain the complete current FactoryBench catalog; "
            f"missing={missing}, unexpected={unexpected}"
        )
    validate_job_lock(job_lock, trial_locks, expected_trials=len(tasks))
    scores = [trial["score"] for trial in trials]
    if not any(score > 0 for score in scores):
        raise ValueError("Harbor job produced no positive FactoryScore on any task")
    calls = [trial["tool_calls"] for trial in trials]
    costs = [trial["cost_usd"] for trial in trials if trial["cost_usd"] is not None]
    if len(providers) != 1:
        raise ValueError(f"job does not have one pinned model provider: {providers}")

    family_scores = {
        family: round(
            statistics.mean(
                trial["score"] for trial in trials if trial["family"] == family
            ),
            2,
        )
        for family in sorted({trial["family"] for trial in trials})
    }
    model_name = pinned_model_name
    agent_version = pinned_agent_version
    provider = next(iter(providers))
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
            "provider": provider,
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
        "featured_task_id": "factorybench-001",
        "trials": trials,
    }
    if runtime_overlay is not None:
        manifest["runtime_overlay"] = runtime_overlay
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{run_slug}-import-",
        dir=output.parent,
    ) as temporary:
        staged_output = Path(temporary) / "model-runs"
        for artifact_path, trial_record in trial_artifacts:
            _write_json(staged_output / artifact_path.relative_to(output), trial_record)
        if runtime_overlay is not None:
            _write_json(
                staged_output / str(runtime_overlay["artifact"]),
                runtime_overlay,
            )
        staged_manifest = staged_output / manifest_path.relative_to(output)
        _write_json(staged_manifest, manifest)

        output.mkdir(parents=True, exist_ok=True)
        staged_run_root = staged_output / run_slug
        staged_run_root.replace(run_artifact_root)
        try:
            # The top-level manifest is the commit marker: release loaders never
            # discover a run until every task artifact is present.
            staged_manifest.replace(manifest_path)
        except BaseException:
            shutil.rmtree(run_artifact_root)
            raise
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
