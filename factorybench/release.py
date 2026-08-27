"""Build the public FactoryBench-100 release tree and website payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from .catalog import BENCHMARK_NAME, BENCHMARK_VERSION, FAMILIES, build_catalog
from .evaluation import POLICIES, policy_steps, qualify, run_episode
from .server import tool_definitions
from .world import READ_TOOLS

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "benchmark" / "factorybench100"
SOURCE_URL = "https://github.com/blobfishai/factory-agent-simulation"
HF_URL = "https://huggingface.co/datasets/SamuelChien821/factorybench-100"
HARBOR_URL = "https://hub.harborframework.com/datasets/blobfishai/factorybench-100/latest"
PAGE_URL = "https://blobfish.ai/benchmarks/factorybench-100"
HARBOR_PYTHON_IMAGE = "python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17"

FAMILY_LABELS = {
    "order_release": "Order release",
    "material_shortage": "Material shortage",
    "supplier_selection": "Supplier selection",
    "inbound_receipt": "Inbound receipt",
    "invoice_match": "Three-way match",
    "production_issue": "Production issue",
    "quality_exception": "Quality exception",
    "completion_costing": "Completion & costing",
    "transfer_reschedule": "Transfer & reschedule",
    "maintenance_recovery": "Maintenance recovery",
}

FAMILY_DESCRIPTIONS = {
    "order_release": "Validate credit, ATP, and BOM controls before releasing and reserving a discrete work order.",
    "material_shortage": "Net requirements against usable stock, source the shortage, and route approval.",
    "supplier_selection": "Evaluate eligibility, price, lead time, quality, and approval limits before PO award.",
    "inbound_receipt": "Receive an approved PO, inspect the lot, and release only accepted stock.",
    "invoice_match": "Apply deterministic PO-receipt-invoice quantity and amount tolerances.",
    "production_issue": "Issue reserved material by FEFO and start production only after full staging.",
    "quality_exception": "Quarantine a failed lot and open an owned nonconformance with disposition.",
    "completion_costing": "Complete operations, reconcile output and scrap, and post WIP variance.",
    "transfer_reschedule": "Move surplus between plants and recover the dependent production schedule.",
    "maintenance_recovery": "Open maintenance, select a qualified alternate center, reroute, and reschedule.",
}


def _write_text(path: Path, value: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    _write_text(path, "".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _harbor_task_digest(task_dir: Path) -> str:
    """Match Harbor 0.21's content digest for the generated task shape."""

    files: list[Path] = []
    for name in ("task.toml", "instruction.md", "README.md"):
        path = task_dir / name
        if path.exists():
            files.append(path)
    for name in ("environment", "tests", "solution", "steps"):
        directory = task_dir / name
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())

    ignored_suffixes = (".pyc", ".swp", ".swo", "~")
    files = [
        path
        for path in files
        if "__pycache__" not in path.relative_to(task_dir).parts
        and path.name != ".DS_Store"
        and not path.name.endswith(ignored_suffixes)
    ]
    outer = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(task_dir).as_posix()):
        relative = path.relative_to(task_dir).as_posix()
        outer.update(f"{relative}\0{_sha256(path)}\n".encode())
    return f"sha256:{outer.hexdigest()}"


def _harbor_dataset_manifest(tasks_root: Path) -> str:
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
    return "\n".join(lines) + "\n"


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "task_name": task["title"],
        "world_id": "northstar-controls-erp-v1",
        "prompt": task["instruction"],
        "role": task["role"],
        "family": task["family"],
        "level": task["level"],
        "as_of": task["as_of"],
        "context_files": [f"assets/{task['task_id']}/policy.md", f"assets/{task['task_id']}/starting-state.json"],
        "required_tools": [step["tool"] for step in task["oracle_steps"]],
        "required_reads": task["required_reads"],
        "required_read_calls": task["required_read_calls"],
        "answer_schema": task["answer_schema"],
        "allowed_write_tables": task["allowed_write_tables"],
        "rubric": [assertion["description"] for assertion in task["expected"]["assertions"]]
        + [
            "Complete all required policy and ERP reads before the first write.",
            "Submit the exact requested answer fields.",
            "Keep every write inside the declared task scope.",
            "Complete without rejected tool calls.",
        ],
        "metric": task["evaluation"],
        "metadata": {
            "benchmark": BENCHMARK_NAME,
            "benchmark_version": BENCHMARK_VERSION,
            "organization": "Northstar Controls Manufacturing",
            "primary_plant": "SEA",
            "source_shape": "synthetic Oracle-shaped manufacturing ERP",
            "synthetic": True,
        },
    }


def _stage_for_tool(tool: str) -> str:
    if tool == "search_documents":
        return "policy"
    if tool in READ_TOOLS:
        return "inspect"
    if tool == "submit_answer":
        return "submit"
    return "transact"


def _website_data(
    tasks: list[dict[str, Any]],
    qualification: dict[str, Any],
    representative_episodes: dict[str, dict[str, Any]],
    release_root: Path,
) -> dict[str, Any]:
    tools = tool_definitions()
    tool_server = {
        "search_documents": "plant_docs",
        "submit_answer": "factory_harness",
    }
    reference_calls = sorted(len(task["oracle_steps"]) for task in tasks)
    result_by_policy = {result["policy"]: result for result in qualification["results"]}
    names = {
        "oracle": "Reference oracle",
        "incomplete_workflow": "Incomplete-workflow control",
        "read_only": "Read-only control",
        "no_control": "No-control ablation",
    }
    notes = {
        "oracle": "Measured solvability ceiling from replaying the checked-in reference workflow; not a model submission.",
        "incomplete_workflow": "Measured ablation that omits the final ERP mutation while still submitting the oracle answer.",
        "read_only": "Measured control that performs the required reads but makes no ERP changes or answer submission.",
        "no_control": "Measured ablation that skips all policy and preflight reads; the environment rejects its writes.",
    }
    leaderboard = []
    for rank, policy in enumerate(POLICIES, start=1):
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
        policy_doc = next(row for row in task["seed_tables"]["documents"] if row["category"] == task["family"])
        populated_tables = {table: rows for table, rows in task["seed_tables"].items() if rows}
        asset_paths = {
            "policy": Path("assets") / task_id / "policy.md",
            "state": Path("assets") / task_id / "starting-state.json",
            "checks": Path("assets") / task_id / "expected-checks.json",
        }
        summaries.append(
            {
                "id": task_id,
                "ordinal": ordinal,
                "title": task["title"],
                "category": task["family"],
                "organization": "Northstar Controls Manufacturing",
                "asOf": task["as_of"],
                "summary": task["instruction"],
                "documents": 2,
                "referenceToolCalls": len(task["oracle_steps"]),
                "sample": True,
                "datasetUrl": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/tasks/{task_id}.json",
            }
        )
        samples[task_id] = {
            "taskId": task_id,
            "prompt": task["instruction"],
            "gradedCriteria": [assertion["description"] for assertion in task["expected"]["assertions"]]
            + ["Read-before-write control", "Exact answer fields", "Write-scope containment", "Error-free execution"],
            "assets": [
                {
                    "path": asset_paths["policy"].as_posix(),
                    "url": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/{asset_paths['policy'].as_posix()}",
                    "name": "policy.md",
                    "format": "Markdown",
                    "bytes": (release_root / asset_paths["policy"]).stat().st_size,
                    "preview": policy_doc["body"],
                    "role": "governing_policy",
                    "note": "Versioned synthetic operating policy retrieved through plant_docs.",
                },
                {
                    "path": asset_paths["state"].as_posix(),
                    "url": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/{asset_paths['state'].as_posix()}",
                    "name": "starting-state.json",
                    "format": "JSON",
                    "bytes": (release_root / asset_paths["state"]).stat().st_size,
                    "preview": f"{sum(len(rows) for rows in populated_tables.values())} seeded records across {len(populated_tables)} populated ERP tables.",
                    "role": "primary",
                    "note": "Exact synthetic records used to seed the isolated SQLite world.",
                },
                {
                    "path": asset_paths["checks"].as_posix(),
                    "url": f"{SOURCE_URL}/blob/main/benchmark/factorybench100/{asset_paths['checks'].as_posix()}",
                    "name": "expected-checks.json",
                    "format": "JSON",
                    "bytes": (release_root / asset_paths["checks"]).stat().st_size,
                    "preview": f"{len(task['expected']['assertions']) + 4} deterministic workflow checks plus exact answer fields.",
                    "role": "verifier",
                    "note": "Public check contract; no LLM judge participates in scoring.",
                },
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
    for family in FAMILIES:
        episode = representative_episodes[family]
        task = next(item for item in tasks if item["task_id"] == episode["task_id"])
        events: list[dict[str, Any]] = [
            {"index": 0, "kind": "message", "text": task["instruction"]}
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
                    {"key": "policy", "label": "Policy"},
                    {"key": "inspect", "label": "Inspect"},
                    {"key": "transact", "label": "Transact"},
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
            "tagline": "100 executable manufacturing ERP workflows over an Oracle-shaped factory world.",
            "question": "Can an agent run the factory workflow—not just describe the next screen?",
            "taskCount": len(tasks),
            "categoryNoun": "workflow family",
            "categories": [{"key": family, "label": FAMILY_LABELS[family], "count": 10} for family in FAMILIES],
            "world": {"tools": len(tools), "tables": 33, "documents": 10},
            "referenceCalls": {"min": min(reference_calls), "median": statistics.median(reference_calls), "max": max(reference_calls)},
            "deterministicVerifier": True,
            "mcp": {"package": "factory-agent-simulation", "version": BENCHMARK_VERSION, "protocolVersion": "2025-03-26", "serverName": "factorybench"},
            "contractPins": [
                {"name": "World", "value": "northstar-controls-erp-v1"},
                {"name": "Database", "value": "SQLite task snapshot"},
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
                    "description": "100 × deterministic workflow checks passed / checks available, averaged over tasks.",
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
                "server": tool_server.get(tool["name"], "oracle_erp"),
            }
            for tool in tools
        ],
        "trajectories": trajectories,
        "methodology": [
            {
                "title": "One metric, inspectable evidence",
                "body": "FactoryScore is the mean percentage of deterministic checks passed. Each task checks required reads before writes, exact ERP state transitions, exact answer fields, write-scope containment, and tool-call validity. Strict completion is shown as supporting evidence, not a second benchmark metric.",
            },
            {
                "title": "Real workflow shape, synthetic company data",
                "body": "The suite is a clean-room simulation shaped by real manufacturing operations: multi-record order intake, SKU and supplier preflight, approval limits, transactional rollback, lot-level inventory, tax-and-amount reconciliation, and production recovery. It contains no Oracle binaries, proprietary screens, customer records, or copied benchmark tasks.",
            },
            {
                "title": "Qualification before publication",
                "body": f"The release replays every reference workflow, replays a deterministic sample twice, runs three negative controls, and removes every reference mutation one at a time. Qualification passed: {qualification['results'][0]['strict_passes']}/100 reference strict passes; {qualification['mutation_omissions']['detected']}/{qualification['mutation_omissions']['total']} mutation omissions were detected; impaired controls remain below the oracle.",
            },
            {
                "title": "Public inspirations and design boundary",
                "body": "Enterprise-Bench informed noisy multi-system task framing; ERP-Bench informed long-horizon manufacturing coverage; Mercor APEX informed the public task, asset, environment, and trajectory presentation. FactoryBench tasks, records, tools, and verifiers are independently authored and executable under this repository's licenses.",
            },
        ],
        "architectureComparison": {
            "title": "The same evaluation spine, assembled for manufacturing ERP",
            "intro": "Archipelago and FactoryBench share the central idea that an agent should act through tools in an isolated world and be graded from observable outcomes. FactoryBench adds a released Oracle-shaped schema, task-level control checks, exact answer fields, and full public oracle replays.",
            "leftLabel": "Mercor Archipelago",
            "rightLabel": "Blobfish FactoryBench-100",
            "rows": [
                {"layer": "Environment", "left": "Containerized task environments with snapshot lifecycle", "right": "Per-task SQLite snapshots generated from public synthetic seed records"},
                {"layer": "Tool surface", "left": "MCP gateway and environment servers", "right": "Three MCP namespaces: oracle_erp, plant_docs, factory_harness"},
                {"layer": "Agent run", "left": "Agent runner records tool interaction", "right": "Harness records every read, transaction, rejection, and submission"},
                {"layer": "Grading", "left": "Before/after snapshot graders", "right": "State assertions + read order + exact answer + write scope + errors"},
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
    shutil.copy2(REPO_ROOT / "factorybench" / "schema.sql", environment / "schema.sql")
    shutil.copy2(REPO_ROOT / "factorybench" / "harbor_service.py", environment / "service.py")
    shutil.copy2(REPO_ROOT / "factorybench" / "harbor_tool.py", environment / "tool")
    (environment / "service.py").chmod(0o755)
    (environment / "tool").chmod(0o755)
    _write_json(
        environment / "task.json",
        {
            "task_id": task["task_id"],
            "as_of": task["as_of"],
            "seed_tables": task["seed_tables"],
            "required_reads": task["required_reads"],
            "required_read_calls": task["required_read_calls"],
            "answer_schema": task["answer_schema"],
            "allowed_write_tables": task["allowed_write_tables"],
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
COPY runtime.py schema.sql service.py task.json /opt/factorybench/
RUN chmod 0755 /opt/factorybench/service.py \\
    && chmod 0444 /opt/factorybench/runtime.py /opt/factorybench/schema.sql /opt/factorybench/task.json
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
      erp:
        condition: service_healthy
    environment:
      FACTORYBENCH_SERVICE_URL: http://erp:8765/call
    networks: [factorybench]
    volumes:
      - factorybench-evidence:/var/lib/factorybench-evidence:ro
  erp:
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
  factorybench:
    internal: true
volumes:
  factorybench-evidence:
""",
    )
    _write_text(task_dir / "instruction.md", task["instruction"] + "\n")
    description = json.dumps(task["instruction"])
    _write_text(
        task_dir / "task.toml",
        f'''schema_version = "1.4"

[task]
name = "{harbor_task_name}"
version = "{BENCHMARK_VERSION}"
description = {description}
authors = [{{ name = "Blobfish AI" }}]
keywords = ["manufacturing", "erp", "oracle-shaped", "stateful", "deterministic"]

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

[metadata]
benchmark = "FactoryBench-100"
world_id = "northstar-controls-erp-v1"
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


def _dataset_card(tasks: list[dict[str, Any]], qualification: dict[str, Any]) -> str:
    return f"""---
license: cc-by-4.0
task_categories:
- tool-use
- question-answering
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

FactoryBench-100 is a 100-task benchmark for long-horizon manufacturing ERP
agents. Each task runs in an isolated SQLite snapshot and uses an Oracle-shaped,
clean-room schema spanning order management, planning, procurement, receiving,
inventory, manufacturing, quality, costing, and maintenance.

Harbor runs the authoritative SQLite state and trace in a private root-owned
sidecar. The agent container receives only the task instruction, typed tool CLI,
and tool schemas; it does not receive the database, runtime, verifier, or gold
state.

The data is entirely synthetic. No Oracle software, proprietary UI, customer
record, or copied task is included.

## Metric

The single metric is **FactoryScore**:

`100 × deterministic workflow checks passed / checks available`, averaged over
all evaluated tasks.

Checks cover read-before-write controls, exact ERP state transitions, exact
answer fields, write-scope containment, and error-free execution. Strict pass is
reported only as supporting evidence.

## Qualification

- Reference oracle: {qualification['results'][0]['mean_score']:.2f} FactoryScore, {qualification['results'][0]['strict_passes']}/{len(tasks)} strict passes
- Incomplete-workflow control: {qualification['results'][1]['mean_score']:.2f}
- Read-only control: {qualification['results'][2]['mean_score']:.2f}
- No-control ablation: {qualification['results'][3]['mean_score']:.2f}
- Deterministic replay sample: {qualification['determinism_sample_size']}/{qualification['determinism_sample_size']} matched
- Single-mutation omission checks: {qualification['mutation_omissions']['detected']}/{qualification['mutation_omissions']['total']} detected

These rows are measured controls, not claims about frontier models.

## Fields

Each JSONL row includes the natural-language prompt, role, workflow family,
context-file paths, required tools and reads, allowed write tables, human-readable
rubric, and metric contract. Executable worlds, oracle traces, exact verifier
specifications, and Harbor tasks live in the source repository.

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


def _release_readme(qualification: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {result['policy'].replace('_', ' ').title()} | {result['mean_score']:.2f} | {result['strict_passes']}/100 |"
        for result in qualification["results"]
    )
    return f"""# FactoryBench-100 release

FactoryBench-100 contains 100 executable manufacturing ERP tasks across ten
workflow families. Every task includes a prompt, synthetic starting-state
records, a policy asset, tool contracts, an oracle replay, exact state and answer
checks, a Harbor 1.4 task, and a Hugging Face row.

Each Harbor task isolates the authoritative ERP state and trace in a private
root-owned sidecar. The agent container contains no database, runtime, verifier,
or gold state.

## Measured qualification

| Control | FactoryScore | Strict passes |
|---|---:|---:|
{rows}

The oracle is a solvability reference, not a model result. Negative controls are
deliberately impaired and demonstrate that the evaluator distinguishes complete,
partially complete, read-only, and control-skipping behavior.

Release qualification also removes every reference mutation individually. All
{qualification['mutation_omissions']['detected']} of {qualification['mutation_omissions']['total']} omissions reduce the score and fail strict completion.

## Layout

- `tasks/`: full public task specifications
- `assets/`: governing policy, starting state, and expected check contract
- `environment/`: schema and MCP-style tool contracts
- `trajectories/oracle/`: real replayed tool traces and state diffs
- `verifiers/`: per-task criterion results from release qualification
- `reports/`: build and qualification evidence
- `huggingface/`: upload-ready dataset mirror
- `harbor/`: 100 portable Harbor task packages
- `website-data.json`: validated input for the Blobfish benchmark explorer

The world is clean-room and Oracle-shaped. “Oracle” describes familiar ERP
entities and controls; this repository does not distribute or emulate Oracle
proprietary code, UI, or customer data.
"""


def build_release(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    tasks = build_catalog()
    qualification = qualify(tasks)
    if not qualification["qualification_passed"]:
        raise RuntimeError("qualification failed; release was not emitted")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    tools = tool_definitions()

    _write_text(output / "README.md", _release_readme(qualification))
    _write_json(output / "reports" / "qualification.json", qualification)
    _write_json(output / "environment" / "tool-contracts.json", {"servers": [{"server": "factorybench", "tools": tools}]})
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
            policy = next(row for row in task["seed_tables"]["documents"] if row["category"] == task["family"])
            _write_text(output / "assets" / task_id / "policy.md", f"# {policy['title']}\n\n{policy['body']}\n")
            _write_json(output / "assets" / task_id / "starting-state.json", task["seed_tables"])
            _write_json(output / "assets" / task_id / "expected-checks.json", task["expected"])
            episode = run_episode(task, "oracle", scratch / f"{task_id}.db")
            _write_json(output / "trajectories" / "oracle" / f"{task_id}.json", episode)
            _write_json(output / "verifiers" / f"{task_id}.json", {key: value for key, value in episode.items() if key not in {"trace", "state_diff"}})
            if task["variant"] == 1:
                representative_episodes[task["family"]] = episode
            _harbor_task(output / "harbor", task)

    _write_jsonl(output / "tasks" / "tasks.jsonl", public_rows)
    _write_text(output / "huggingface" / "README.md", _dataset_card(tasks, qualification))
    _write_jsonl(output / "huggingface" / "data" / "tasks.jsonl", public_rows)
    _write_json(output / "huggingface" / "contracts" / "tool-contracts.json", {"servers": [{"server": "factorybench", "tools": tools}]})
    shutil.copytree(output / "assets", output / "huggingface" / "assets")
    _write_text(output / "huggingface" / ".gitattributes", "*.jsonl filter=lfs diff=lfs merge=lfs -text\n")

    _write_text(
        output / "harbor" / "dataset.toml",
        _harbor_dataset_manifest(output / "harbor" / "tasks"),
    )
    _write_text(output / "harbor" / "README.md", _dataset_card(tasks, qualification))

    shutil.copy2(REPO_ROOT / "LICENSE", output / "LICENSE")
    shutil.copy2(REPO_ROOT / "NOTICE", output / "NOTICE")
    shutil.copy2(REPO_ROOT / "LICENSE-DATA", output / "LICENSE-DATA")
    shutil.copy2(REPO_ROOT / "LICENSE-DATA", output / "huggingface" / "LICENSE")
    shutil.copy2(REPO_ROOT / "LICENSE-DATA", output / "huggingface" / "LICENSE-DATA")
    shutil.copy2(REPO_ROOT / "LICENSE", output / "harbor" / "LICENSE")
    shutil.copy2(REPO_ROOT / "NOTICE", output / "harbor" / "NOTICE")
    shutil.copy2(REPO_ROOT / "LICENSE-DATA", output / "harbor" / "LICENSE-DATA")

    website = _website_data(tasks, qualification, representative_episodes, output)
    _write_json(output / "website-data.json", website)

    artifact_files = sorted(path for path in output.rglob("*") if path.is_file())
    build_report = {
        "benchmark": BENCHMARK_NAME,
        "version": BENCHMARK_VERSION,
        "task_count": len(tasks),
        "family_count": len(FAMILIES),
        "tool_count": len(tools),
        "metric": "FactoryScore",
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
