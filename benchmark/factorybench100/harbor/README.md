---
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

- Reference oracle: 100.00 FactoryScore, 100/100 strict passes
- Incomplete-workflow control: 97.25
- Read-only control: 34.96
- No-control ablation: 68.71
- Deterministic replay sample: 100/100 matched
- Single-mutation omission checks: 300/300 detected

These rows are measured controls, not claims about frontier models.

## Pinned model runs

| Model | Harness | Coverage | FactoryScore | Strict passes | Selection |
|---|---|---:|---:|---:|---|
| [gpt-5.6-luna](model-runs/gpt-5.6-luna-full-100.json) | Harbor 0.21.0 / codex 0.150.1 / max | 100/100 | 89.21 | 4/100 | Full FactoryBench-100 v3.0.0 suite (100/100 tasks); high-level human requests, multi-source investigation, and task-specific deterministic scoring. Runtime overlay changed only the agent image to preinstall Codex 0.150.1; all semantic task and verifier files matched the released tree. |

Coverage is part of the result. A stratified subset is not presented as a
100-task score. Full manifests and task-level traces are mirrored under
`model-runs/`.

## Fields

Each JSONL row includes the natural-language prompt, role, workflow family,
12 heterogeneous context files, reference tools, prerequisite investigation
groups, allowed write tables, weighted human-readable rubric, and metric
contract. Executable worlds, oracle traces,
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
