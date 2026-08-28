# safety event and interlock diagnosis

Case: CASE-090
Document control number: SPEC-0090
Effective revision: R7
Superseded revision visible in archive: R8
Subject: safety interlock bypass
Primary measure: assets and operation-hours exposed by the bypass
Source finished or header quantity: 74
Effective usage per finished or header unit: 1 HR
Unit: HR
Eligibility definition: confirmed affected asset with approved corrective scope
Exclusion definition: similar alarms and unrelated assets
Control: safety event, asset, control circuit, isolation, and approval

## Applicability

Apply only to NS-000090, organization SEA, and CASE-090. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from qualified controls-technician window; external timing is conditional on OEM interlock part arrival. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
