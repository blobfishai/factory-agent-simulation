# project issue, consumption, and count bridge

Case: CASE-079
Document control number: SPEC-0079
Effective revision: R3
Superseded revision visible in archive: R9
Subject: unused project material in WIP
Primary measure: project material issued to the canceled operation
Source finished or header quantity: 87
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: physically counted unconsumed same-project lot
Exclusion definition: consumed, scrapped, or other-project quantity
Control: operation cancellation, project ownership, lot, and count must reconcile

## Applicability

Apply only to NS-000079, organization SEA, and CASE-079. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from project-stores return window; external timing is conditional on future project demand. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
