# FactoryBench-100 release

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
| Oracle | 100.00 | 100/100 |
| Incomplete Workflow | 81.81 | 0/100 |
| Read Only | 46.00 | 0/100 |
| No Control | 15.34 | 0/100 |

The oracle is a solvability reference, not a model result. Negative controls are
deliberately impaired and demonstrate that the evaluator distinguishes complete,
partially complete, read-only, and control-skipping behavior.

Release qualification also removes every reference mutation individually. All
240 of 240 omissions reduce the score and fail strict completion.

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
