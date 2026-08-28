# shop qualification and maintenance load

Case: CASE-023
Document control number: SPEC-0023
Effective revision: R3
Superseded revision visible in archive: R10
Subject: maintenance operation requiring electrical qualification
Primary measure: repair-hours remaining
Source finished or header quantity: 46
Effective usage per finished or header unit: 1 HR
Unit: HR
Eligibility definition: open hours in qualified electrical shops
Exclusion definition: mechanical-only shops and protected electrical work
Control: shop qualification, active status, tooling, and capacity must all pass

## Applicability

Apply only to NS-000023, organization SEA, and CASE-023. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from internal electrical-shop load; external timing is conditional on contract electrical-shop availability. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
