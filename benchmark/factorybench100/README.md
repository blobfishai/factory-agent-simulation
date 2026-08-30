# FactoryBench-100 release

FactoryBench-100 contains 100 distinct executable employee decisions across 20
manufacturing and ERP domains. Every task includes a high-level human request,
28 synthetic evidence artifacts, a multi-system starting state, endpoint-pinned
tool contracts, a hidden investigation and calculation graph, three realistic
options, task-specific weighted criteria, an oracle replay, a Harbor 1.4 task,
and a Hugging Face row.

Each Harbor task isolates the authoritative ERP state and trace in a private
root-owned sidecar. The agent container contains no database, runtime, verifier,
or gold state.

## Measured qualification

| Control | FactoryScore | Strict passes |
|---|---:|---:|
| Oracle | 100.00 | 100/100 |
| Noop | 6.00 | 0/100 |
| Shortcut | 40.51 | 0/100 |
| State Only | 66.00 | 0/100 |
| Incomplete Read | 97.04 | 0/100 |
| Write Before Read | 67.33 | 0/100 |
| Missing Readback | 94.00 | 0/100 |
| Unauthorized Write | 98.00 | 0/100 |
| Wrong Value | 98.01 | 0/100 |
| Wrong Decision | 94.02 | 0/100 |
| Wrong Evidence | 97.57 | 0/100 |
| Wrong Target | 96.85 | 0/100 |
| Keyword Stuffing | 97.00 | 0/100 |

The oracle is a solvability reference, not a model result. The 12 negative
controls cover no-op and shortcut behavior, missing handoff or evidence,
write-before-read, missing readback, unauthorized mutation, incorrect values,
incorrect operating choice, substitution of stale or irrelevant evidence, a correct
write made to the wrong existing destination, and keyword-only collaboration output.
All 1200 adversarial executions are rejected.

Release qualification also removes every reference mutation individually. All
300 of 300 omissions reduce the score and fail strict completion.

## Pinned model runs

No version-pinned model run is published for this release.

Subset coverage is explicit and is never extrapolated to all 100 tasks.

## Layout

- `tasks/`: full public task specifications
- `assets/`: the 28 agent-visible policy, email, Slack, PDF, Excel, CSV, JSON, log, and specification sources per task
- `state/`: exact evaluator starting state, kept outside the agent-visible asset room
- `environment/`: schema and MCP-style tool contracts
- `trajectories/oracle/`: real replayed tool traces and state diffs
- `model-runs/`: pinned model manifests and task-level traces
- `verifiers/contracts/`: exact sealed verifier contracts; `verifiers/*.json` contains measured oracle criterion results
- `reports/`: build and qualification evidence
- `huggingface/`: upload-ready dataset mirror
- `harbor/`: 100 portable Harbor task packages
- `website-data.json`: validated input for the Blobfish benchmark explorer

The world is clean-room and maps each Oracle tool to a documented Fusion Cloud
26a REST operation. The implementation and records are independently authored;
the repository does not distribute Oracle code, proprietary UI, or customer data.
