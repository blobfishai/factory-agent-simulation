# project ownership and lot availability

Case: CASE-076
Document control number: SPEC-0076
Effective revision: R7
Superseded revision visible in archive: R9
Subject: project-owned relay transfer
Primary measure: project demand at the destination
Source finished or header quantity: 54
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: same-project, same-task available lot quantity
Exclusion definition: common, other-project, quarantined, or reserved quantity
Control: project, task, lot, source, destination, and approval must persist

## Applicability

Apply only to NS-000076, organization SEA, and CASE-076. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from material-handling window; external timing is conditional on project replenishment timing. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
