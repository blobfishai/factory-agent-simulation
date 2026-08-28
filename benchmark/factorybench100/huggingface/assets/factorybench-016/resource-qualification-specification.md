# downtime diagnosis and alternate-cell load

Case: CASE-016
Document control number: SPEC-0016
Effective revision: R3
Superseded revision visible in archive: R9
Subject: assembly operation exposed to spindle failure
Primary measure: machine-hours needed to preserve the order
Source finished or header quantity: 46
Effective usage per finished or header unit: 1 HR
Unit: HR
Eligibility definition: qualified alternate-cell hours with tooling and operator
Exclusion definition: down primary-cell hours and protected alternate load
Control: alternate must be active, qualified, and non-displacing

## Applicability

Apply only to NS-000016, organization SEA, and CASE-016. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from finite load on each qualified assembly cell; external timing is conditional on repair team's spindle restoration estimate. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
