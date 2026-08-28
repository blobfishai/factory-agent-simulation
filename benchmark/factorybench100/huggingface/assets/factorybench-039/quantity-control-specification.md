# inspection acceptance and project ownership

Case: CASE-039
Document control number: SPEC-0039
Effective revision: R5
Superseded revision visible in archive: R8
Subject: accepted project copper receipt
Primary measure: quantity received for the project PO
Source finished or header quantity: 62
Effective usage per finished or header unit: 1 KG
Unit: KG
Eligibility definition: inspection-accepted quantity with matching project and task
Exclusion definition: rejected or common-owned quantity
Control: delivery must preserve project, task, lot, and accepted status

## Applicability

Apply only to NS-000039, organization SEA, and CASE-039. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from project-stores handling window; external timing is conditional on supplier replacement for rejected copper. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
