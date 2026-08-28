# FactoryBench-100 release

FactoryBench-100 contains 100 distinct executable employee decisions across 20
manufacturing and ERP domains. Every task includes a high-level human request,
12 synthetic evidence artifacts, a multi-system starting state, endpoint-pinned
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
| Incomplete Workflow | 97.25 | 0/100 |
| Read Only | 34.96 | 0/100 |
| No Control | 68.71 | 0/100 |

The oracle is a solvability reference, not a model result. Negative controls are
deliberately impaired and demonstrate that the evaluator distinguishes complete,
partially complete, read-only, and control-skipping behavior.

Release qualification also removes every reference mutation individually. All
300 of 300 omissions reduce the score and fail strict completion.

## Pinned model runs

| Model | Harness | Coverage | FactoryScore | Strict passes | Selection |
|---|---|---:|---:|---:|---|
| [gpt-5.6-luna](model-runs/gpt-5.6-luna-full-100.json) | Harbor 0.21.0 / codex 0.150.1 / max | 100/100 | 89.21 | 4/100 | Full FactoryBench-100 v3.0.0 suite (100/100 tasks); high-level human requests, multi-source investigation, and task-specific deterministic scoring. Runtime overlay changed only the agent image to preinstall Codex 0.150.1; all semantic task and verifier files matched the released tree. |

Subset coverage is explicit and is never extrapolated to all 100 tasks.

## Layout

- `tasks/`: full public task specifications
- `assets/`: policy, email, Slack, PDFs, Excel workbooks, specifications, starting state, and expected checks
- `environment/`: schema and MCP-style tool contracts
- `trajectories/oracle/`: real replayed tool traces and state diffs
- `model-runs/`: pinned model manifests and task-level traces
- `verifiers/`: per-task criterion results from release qualification
- `reports/`: build and qualification evidence
- `huggingface/`: upload-ready dataset mirror
- `harbor/`: 100 portable Harbor task packages
- `website-data.json`: validated input for the Blobfish benchmark explorer

The world is clean-room and maps each Oracle tool to a documented Fusion Cloud
26a REST operation. The implementation and records are independently authored;
the repository does not distribute Oracle code, proprietary UI, or customer data.
