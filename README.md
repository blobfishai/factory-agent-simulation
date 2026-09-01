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
- 94 typed, source-pinned operations across Oracle Fusion, Gmail, Drive, Sheets, Slack, and the benchmark harness
- 28 task-specific source artifacts per task: policies, email, Slack, PDFs, Excel, CSV, approvals, specifications, revision history, capacity, inventory, and ERP exports
- 100 unique raw tool sequences and 100 unique semantic action graphs, with no duplicated reference workflow
- High-level employee requests that leave the investigation path to the agent
- Scored discovery-before-mutation evidence, persisted provider payloads, and post-write readback
- Task-specific calculations, decisions, state, answer, containment, and tool-validity checks
- Replayed oracle trajectories, exact deterministic replay, and twelve measured negative controls
- Harbor isolation with six Streamable HTTP MCP endpoints backed by ERP state and a trace in a private root-owned sidecar
- Upload-ready Hugging Face and Harbor distributions
- Website data for the public task, asset, environment, and trajectory explorer

The single metric is **FactoryScore**: `100 × passed deterministic criterion
weight / available criterion weight`, averaged over evaluated tasks. Strict
completion is supporting evidence, not a second benchmark metric.

## Qualification results

The v3.3.5 release executes 1,400 canonical trials:

- 100/100 reference-oracle strict passes at 100.00 FactoryScore
- 100/100 exact deterministic replay matches
- 1,200/1,200 correct rejections across no-op, shortcut, state-only,
  incomplete-read, write-before-read, missing-readback, unauthorized-write,
  wrong-value, wrong-decision, wrong-evidence, wrong-target, and
  keyword-stuffing controls
- 300/300 supplemental single-mutation omissions detected

Every decision mode grades the outcome date of all three alternatives, not only
the recommended one. v3.3 adds the `baseline_program_date`,
`alternative_program_date`, and `escalated_program_date` answer fields and their
graded calculations to the five forecast-mode tasks, which previously graded
only the recommended outcome.

The reference oracle establishes solvability; it is not a model submission. The
other executions are deliberately impaired controls that demonstrate diagnostic range.
Schema-valid but business-wrong writes are accepted by the sandbox just as they
would be by the provider. They persist as actual state and fail the task-specific
payload or readback criteria; the API never reveals a hidden approved value.

## Full-suite model run

Only version-pinned full-suite model runs are eligible for the public leaderboard.
Each accepted manifest publishes coverage, aggregate and task-level FactoryScores,
exceptions, tool calls, cost, trajectories, verifier verdicts, reward records,
and any disclosed runtime overlay. Results are imported directly from Harbor;
they are never reconstructed from oracle traces or carried forward across a
benchmark version change.

The published v3.3.5 leaderboard row is a single exact-release Harbor run of
`gpt-5.6-luna` through Codex 0.151.0 at maximum reasoning: 100/100 tasks,
76.20 mean FactoryScore, zero exceptions, one attempt per task, and zero
retries. Sixty-two tasks scored at least 80, 79 scored at least 60, and no task
scored zero (range 13.50–100.00). The featured Luma-lamp commitment task scored
88.67 and includes its complete public trajectory, verifier verdict, reward
record, final response, and source receipts.

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
on stdin. Generated Harbor tasks declare six Streamable HTTP MCP endpoints; the
terminal-friendly `tool` client sends the same MCP `tools/call` requests.
Inside Harbor, the agent container has no database, runtime, verifier, or gold
state; it can reach the private ERP sidecar only through the declared tools.
The checked-in `benchmark/factorybench100/environment/mcp.json` can be copied
directly into Codex, Claude Desktop, or another stdio MCP client.

## Release outputs

The checked-in release is under [`benchmark/factorybench100`](benchmark/factorybench100):

- `tasks/` — complete task specifications
- `assets/` — 2,800 agent-visible source artifacts
- `state/` — exact evaluator starting state, outside the agent-visible asset room
- `environment/` — SQLite schema and tool contracts
- `trajectories/` — replayed oracle tool traces and state diffs
- `verifiers/contracts/` — sealed deterministic verifier contracts
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
