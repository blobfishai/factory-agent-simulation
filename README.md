# Factory Agent Simulation

This repository contains the executable **FactoryBench-100** world and release:
100 long-horizon manufacturing ERP tasks across order release, material planning,
procurement, receiving, three-way match, shop-floor issue, quality, costing,
interplant recovery, and maintenance.

The world is clean-room and Oracle-shaped. It uses familiar manufacturing ERP
entities and controls in a synthetic Northstar Controls dataset; it does not ship
Oracle code, UI, schemas copied from an Oracle product, or customer data.

## What is public

- An isolated SQLite starting state for every task
- 36 typed tools across `oracle_erp`, `plant_docs`, and `factory_harness`
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
| Incomplete workflow | 81.81 | 0/100 |
| Read only | 46.00 | 0/100 |
| No controls | 15.34 | 0/100 |

The reference oracle establishes solvability; it is not a model submission. The
other rows are deliberately impaired controls that demonstrate diagnostic range.
Release qualification also detects all 240 single-mutation omissions, proving
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
- `assets/` — policy, starting state, and verifier contract
- `environment/` — SQLite schema and tool contracts
- `trajectories/` — replayed oracle tool traces and state diffs
- `reports/` — build and qualification evidence
- `huggingface/` — dataset-card and JSONL upload tree
- `harbor/` — 100 portable Harbor 1.4 tasks
- `website-data.json` — Blobfish benchmark explorer payload

## Design lineage

The workflow data shape is grounded in production-style manufacturing operations:
multi-record order intake, SKU/vendor/department preflight, approval limits,
strict transaction rollback, lot and warehouse inventory, amount reconciliation,
and production recovery. Public presentation and distribution take inspiration
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
