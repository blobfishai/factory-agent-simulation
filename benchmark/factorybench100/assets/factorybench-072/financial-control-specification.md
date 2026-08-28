# material scan and WIP-cost reconciliation

Case: CASE-072
Document control number: SPEC-0072
Effective revision: R3
Superseded revision visible in archive: R8
Subject: duplicated copper material issue
Primary measure: cost and quantity posted by the suspect scan
Source finished or header quantity: 1152
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: one legitimate issue supported by consumption
Exclusion definition: duplicate issue quantity and cost
Control: scanner identity, timestamp, lot, operation, and physical stock prove duplication
Task-specific financial control: duplicate-issue residual variance
Control threshold: USD 0.0

## Applicability

Apply only to NS-000072, organization SEA, and CASE-072. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from open material-cost period; external timing is conditional on cycle-count confirmation. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
