"""Fail-closed Harbor task receipts for FactoryBench model runs."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
HARBOR_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
PUBLISH_DIRECT_FILES = ("task.toml", "instruction.md", "README.md")
PUBLISH_DIRECTORIES = ("environment", "tests", "solution", "steps")
IGNORED_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo", "~")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_manifest_digest(root: Path) -> tuple[str, int, int]:
    """Hash a runtime tree with the public first-party receipt protocol."""

    root = root.resolve()
    if not root.is_dir() or (root / ".git").exists():
        raise ValueError(f"runtime source is missing or contains repository metadata: {root}")
    entries = list(root.rglob("*"))
    for entry in entries:
        if entry.is_symlink() and not entry.resolve().is_relative_to(root):
            raise ValueError(f"runtime symlink escapes its sealed source tree: {entry}")
    files = sorted(
        path
        for path in entries
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != ".DS_Store"
        and not path.name.endswith(IGNORED_SUFFIXES)
    )
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        total_bytes += size
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), len(files), total_bytes


def _publishable_files(task_dir: Path) -> list[Path]:
    files: set[Path] = set()
    for name in PUBLISH_DIRECT_FILES:
        path = task_dir / name
        if path.is_file():
            files.add(path)
    for name in PUBLISH_DIRECTORIES:
        directory = task_dir / name
        if directory.is_dir():
            files.update(path for path in directory.rglob("*") if path.is_file())
    return sorted(
        (
            path
            for path in files
            if "__pycache__" not in path.relative_to(task_dir).parts
            and path.name != ".DS_Store"
            and not path.name.endswith(IGNORED_SUFFIXES)
        ),
        key=lambda path: path.relative_to(task_dir).as_posix(),
    )


def harbor_task_digest(task_dir: Path) -> tuple[str, int, int]:
    """Recompute Harbor 0.21's durable publisher digest and payload size."""

    task_dir = task_dir.resolve()
    files = _publishable_files(task_dir)
    outer = hashlib.sha256()
    total_bytes = 0
    for path in files:
        relative = path.relative_to(task_dir).as_posix()
        total_bytes += path.stat().st_size
        outer.update(f"{relative}\0{sha256_file(path)}\n".encode())
    return f"sha256:{outer.hexdigest()}", len(files), total_bytes


def _legacy_directory_checksum(directory: Path) -> str | None:
    descriptors: list[str] = []
    for path in directory.iterdir():
        if path.is_symlink():
            raise ValueError(f"cannot independently verify symlinked task entry: {path}")
        if path.is_dir():
            child_checksum = _legacy_directory_checksum(path)
            if child_checksum is None:
                continue
            properties = (f"dirhash:{child_checksum}", f"name:{path.name}")
        elif path.is_file():
            properties = (f"data:{sha256_file(path)}", f"name:{path.name}")
        else:
            continue
        descriptors.append("\0".join(sorted(properties)))
    if not descriptors:
        return None
    return hashlib.sha256("\0\0".join(sorted(descriptors)).encode()).hexdigest()


def legacy_task_checksum(task_dir: Path) -> str:
    """Recompute Harbor's legacy full-directory ``dirhash`` receipt."""

    checksum = _legacy_directory_checksum(task_dir.resolve())
    if checksum is None:
        raise ValueError(f"cannot checksum an empty task directory: {task_dir}")
    return checksum


def _resolve_release_task_path(configured: str, tasks_root: Path) -> Path:
    tasks_root = tasks_root.resolve()
    configured_path = Path(configured).expanduser()
    if configured_path.is_absolute():
        resolved = configured_path.resolve()
    elif (
        ".." not in configured_path.parts
        and len(configured_path.parts) >= 3
        and configured_path.parts[-3:-1] == ("harbor", "tasks")
    ):
        resolved = (tasks_root / configured_path.name).resolve()
    else:
        raise ValueError(f"unbound Harbor task path: {configured}")
    if resolved.parent != tasks_root or not resolved.is_dir():
        raise ValueError(f"Harbor task path is outside the supplied release: {configured}")
    return resolved


def bind_trial_task(
    *,
    trial_dir: Path,
    result: dict[str, Any],
    tasks_root: Path,
    benchmark_version: str,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Bind one result and per-trial lock to the exact checked-in task bytes."""

    label = trial_dir.name
    task_name = result.get("task_name")
    task_checksum = result.get("task_checksum")
    result_config = result.get("config")
    configured_task = (
        result_config.get("task") if isinstance(result_config, dict) else None
    )
    configured_path = (
        configured_task.get("path") if isinstance(configured_task, dict) else None
    )
    if not isinstance(task_name, str) or not isinstance(configured_path, str):
        raise ValueError(f"{label}: result lacks exact task provenance")
    if not isinstance(task_checksum, str) or not SHA256_PATTERN.fullmatch(task_checksum):
        raise ValueError(f"{label}: result has an invalid legacy task checksum")
    if result.get("trial_name") not in (None, trial_dir.name):
        raise ValueError(f"{label}: result trial name disagrees with its directory")

    resolved_task = _resolve_release_task_path(configured_path, tasks_root)
    result_task_id = result.get("task_id")
    if isinstance(result_task_id, dict) and isinstance(result_task_id.get("path"), str):
        if _resolve_release_task_path(result_task_id["path"], tasks_root) != resolved_task:
            raise ValueError(f"{label}: result task paths disagree")

    task_toml = tomllib.loads(
        (resolved_task / "task.toml").read_text(encoding="utf-8")
    )
    task_metadata = task_toml.get("task") or {}
    logical_task_id = (task_toml.get("metadata") or {}).get("task_id")
    if (
        task_metadata.get("name") != task_name
        or task_metadata.get("version") != benchmark_version
        or logical_task_id != resolved_task.name
    ):
        raise ValueError(f"{label}: released task identity disagrees with the result")

    lock_path = trial_dir / "lock.json"
    lock = _read_json(lock_path)
    lock_task = lock.get("task")
    lock_task_path = lock_task.get("path") if isinstance(lock_task, dict) else None
    if (
        lock.get("schema_version") != 2
        or not isinstance(lock_task, dict)
        or not isinstance(lock_task_path, str)
        or _resolve_release_task_path(lock_task_path, tasks_root) != resolved_task
        or lock_task.get("name") != resolved_task.name
        or lock_task.get("version") != benchmark_version
        or lock_task.get("type") != "local"
        or lock_task.get("source") != "tasks"
    ):
        raise ValueError(f"{label}: per-trial lock is not the exact local release task")
    lock_digest = lock_task.get("digest")
    if not isinstance(lock_digest, str) or not HARBOR_DIGEST_PATTERN.fullmatch(lock_digest):
        raise ValueError(f"{label}: per-trial lock has an invalid task digest")

    computed_digest, published_files, published_bytes = harbor_task_digest(resolved_task)
    if lock_digest != computed_digest:
        raise ValueError(f"{label}: lock digest disagrees with the released task bytes")
    if task_checksum != legacy_task_checksum(resolved_task):
        raise ValueError(f"{label}: result checksum disagrees with the released task tree")

    return resolved_task, {
        "task_id": resolved_task.name,
        "published_name": task_name,
        "harbor_task_digest": lock_digest,
        "trial_task_checksum": task_checksum,
        "trial_lock_sha256": sha256_file(lock_path),
        "published_files": published_files,
        "published_bytes": published_bytes,
    }, lock


def validate_job_lock(
    job_lock: dict[str, Any],
    trial_locks: list[dict[str, Any]],
    *,
    expected_trials: int,
) -> None:
    """Require every per-trial lock to match its job-lock entry exactly."""

    job_trials = job_lock.get("trials")
    if not isinstance(job_trials, list) or len(job_trials) != expected_trials:
        raise ValueError("Harbor job lock does not contain the complete trial set")
    if len(trial_locks) != expected_trials:
        raise ValueError("Harbor run does not contain the complete per-trial lock set")

    def by_task(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        mapped: dict[str, dict[str, Any]] = {}
        for row in rows:
            task = row.get("task") if isinstance(row, dict) else None
            task_id = task.get("name") if isinstance(task, dict) else None
            if not isinstance(task_id, str) or task_id in mapped:
                raise ValueError("Harbor locks contain duplicate or invalid task identities")
            mapped[task_id] = row
        return mapped

    if by_task(job_trials) != by_task(trial_locks):
        raise ValueError("Harbor per-trial locks do not exactly match the job lock")
