# Factory Agent Simulation

This repository contains the executable **FactoryBench-100** world and release:
100 distinct long-horizon enterprise workflows across 20 manufacturing, supply,
procurement, receiving, payables, quality, maintenance, project, field-service,
compliance, and close-control families.

The world is clean-room and synthetic. Every Oracle tool maps one-to-one to a
documented Oracle Fusion Cloud 26a REST operation, and every collaboration tool
maps to a documented Gmail v1, Drive v3, Sheets v4, or Slack Web API operation.
It ships no Oracle code, proprietary UI, or customer data.

## What is public

- An isolated multi-system SQLite starting state for every task
- 87 typed, source-pinned operations across Oracle Fusion, Gmail, Drive, Sheets, Slack, and the benchmark harness
- 12 task-specific source artifacts per task: policies, email, Slack, PDFs, Excel, CSV, approvals, specifications, and ERP exports
- 100 unique call sequences with a maximum pairwise sequence similarity of 0.7778
- Required read-before-write controls and transaction validation
- Exact state, answer, write-scope, and tool-validity checks
- Replayed oracle trajectories and three measured negative controls
- Harbor isolation with the ERP state and trace in a private root-owned sidecar
- Upload-ready Hugging Face and Harbor distributions
- Website data for the public task, asset, environment, and trajectory explorer

The single metric is **FactoryScore**: `100 × deterministic workflow checks
passed / checks available`, averaged over evaluated tasks. Strict completion is
supporting evidence, not a second benchmark metric.

## Qualification results

| Measured control | FactoryScore | Strict passes |
|---|---:|---:|
| Reference oracle | 100.00 | 100/100 |
| Incomplete workflow | 85.71 | 0/100 |
| Read only | 42.86 | 0/100 |
| No controls | 14.29 | 0/100 |

The reference oracle establishes solvability; it is not a model submission. The
other rows are deliberately impaired controls that demonstrate diagnostic range.

## Full-suite model run

The published `gpt-5.6-luna` run evaluated all 100 v2 tasks with Codex 0.150.1
at medium reasoning effort. It achieved a **FactoryScore of 85.29**, averaged
32.31 tool calls per task, and cost $2.726084 in total ($0.027261 per task).
All 100 trials completed without infrastructure exceptions. Strict completion
was 0/100 because that supporting diagnostic rejects any invalid exploratory
tool call; the primary FactoryScore retains credit for each deterministic
workflow check the agent completed. The release includes every trajectory,
verdict, reward record, and the disclosed agent-image runtime overlay.
Release qualification also detects all 300 single-mutation omissions, proving
that no reference write is dispensable under the published verifier contract.

## Run locally

Python 3.12 or newer is required.

```sh
python3.12 -m pip install -e '.[dev]'
python3.12 -m pytest -q
python3.12 -m factorybench.evaluation
python3.12 -m factorybench.release
```

Run one task through the actual stdio MCP server (the `factorybench-server`
name remains as a compatibility alias):

```sh
factorybench-mcp \
  --task factorybench-001 \
  --db /tmp/factorybench-001.db \
  --fresh
```

The server accepts `initialize`, `tools/list`, and `tools/call` JSON-RPC messages
on stdin. The generated Harbor tasks also expose a terminal-friendly `tool` CLI.
Inside Harbor, the agent container has no database, runtime, verifier, or gold
state; it can reach the private ERP sidecar only through the declared tools.
The checked-in `benchmark/factorybench100/environment/mcp.json` can be copied
directly into Codex, Claude Desktop, or another stdio MCP client.

## Release outputs

The checked-in release is under [`benchmark/factorybench100`](benchmark/factorybench100):

- `tasks/` — complete task specifications
- `assets/` — 1,200 source artifacts plus starting state and verifier contracts
- `environment/` — SQLite schema and tool contracts
- `trajectories/` — replayed oracle tool traces and state diffs
- `reports/` — build and qualification evidence
- `huggingface/` — dataset-card and JSONL upload tree
- `harbor/` — 100 portable Harbor 1.4 tasks
- `website-data.json` — Blobfish benchmark explorer payload

## Design lineage

The workflow data shape is grounded in production-style operations: evidence
split across ERP, email, Drive, Sheets, Slack, vendor PDFs, and technical files;
explicit approvals; strict transaction rollback; lot and serial inventory;
amount reconciliation; write-back; and stakeholder communication. Public
presentation and distribution take inspiration
from [Mercor APEX](https://www.mercor.com/apex/apex-accounting-leaderboard/),
[Archipelago](https://github.com/Mercor-Intelligence/archipelago),
[Enterprise-Bench](https://hub.harborframework.com/datasets/Enterprise-Bench/l1-l2-bench/latest),
and [ERP-Bench](https://hub.harborframework.com/datasets/agentic-labs/erp-bench/latest).
FactoryBench tasks, records, tools, and verifiers are independently authored.

## Links

- Website: https://blobfish.ai/benchmarks/factorybench-100
- Hugging Face: https://huggingface.co/datasets/SamuelChien821/factorybench-100
- Harbor: https://hub.harborframework.com/datasets/blobfishai/factorybench-100/latest

Code is Apache-2.0. Dataset content is CC BY 4.0; see `LICENSE` and
`LICENSE-DATA`.
