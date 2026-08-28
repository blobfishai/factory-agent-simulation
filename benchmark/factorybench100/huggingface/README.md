---
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

FactoryBench-100 is a 100-task benchmark for long-horizon enterprise ERP agents.
Each independently authored task runs in an isolated SQLite snapshot and exposes
documented Oracle Fusion Cloud 26a REST operations alongside Gmail v1, Drive v3,
Sheets v4, and Slack Web API operations over synthetic state.

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

- Reference oracle: 100.00 FactoryScore, 100/100 strict passes
- Incomplete-workflow control: 85.71
- Read-only control: 42.86
- No-control ablation: 14.29
- Deterministic replay sample: 10/10 matched
- Single-mutation omission checks: 300/300 detected

These rows are measured controls, not claims about frontier models.

## Pinned model runs

| Model | Harness | Coverage | FactoryScore | Strict passes | Selection |
|---|---|---:|---:|---:|---|
| [gpt-5.6-luna](model-runs/gpt-5.6-luna-full-100.json) | Harbor 0.21.0 / codex 0.150.1 / medium | 100/100 | 85.29 | 0/100 | Full v2 suite (100/100 tasks). Codex 0.150.1 was preinstalled in the agent image; all prompts, tools, private sidecars, and verifiers were byte-identical to the released tasks. |

Coverage is part of the result. A stratified subset is not presented as a
100-task score. Full manifests and task-level traces are mirrored under
`model-runs/`.

## Fields

Each JSONL row includes the natural-language prompt, role, workflow family,
12 heterogeneous context files, required tools and reads, allowed write tables,
human-readable rubric, and metric contract. Executable worlds, oracle traces,
exact verifier specifications, and Harbor tasks live in the source repository.

## Links

- Website: https://blobfish.ai/benchmarks/factorybench-100
- Source and executable world: https://github.com/blobfishai/factory-agent-simulation
- Harbor: https://hub.harborframework.com/datasets/blobfishai/factorybench-100/latest

## Influences

The release takes design inspiration from
[Enterprise-Bench](https://hub.harborframework.com/datasets/Enterprise-Bench/l1-l2-bench/latest),
[ERP-Bench](https://hub.harborframework.com/datasets/agentic-labs/erp-bench/latest),
[Mercor APEX](https://www.mercor.com/apex/apex-accounting-leaderboard/), and
[Archipelago](https://github.com/Mercor-Intelligence/archipelago). All task
records and implementations in FactoryBench are independently authored.
