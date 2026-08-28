# production status and period cutoff

Case: CASE-094
Document control number: SPEC-0094
Effective revision: R4
Superseded revision visible in archive: R9
Subject: unfinished production at cutoff
Primary measure: remaining operation-hours and quantity
Source finished or header quantity: 53
Effective usage per finished or header unit: 1 HR
Unit: HR
Eligibility definition: work physically incomplete and unreported
Exclusion definition: completed quantity and current-period actuals
Control: physical status, operation transactions, period cutoff, and revised dates

## Applicability

Apply only to NS-000094, organization SEA, and CASE-094. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from first next-period qualified slot; external timing is conditional on missing input readiness. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
