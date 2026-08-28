# WIP physical status and close calendar

Case: CASE-075
Document control number: SPEC-0075
Effective revision: R6
Superseded revision visible in archive: R8
Subject: incomplete WIP at period close
Primary measure: remaining operation-hours and quantity
Source finished or header quantity: 67
Effective usage per finished or header unit: 1 HR
Unit: HR
Eligibility definition: work demonstrably incomplete at cutoff
Exclusion definition: completed quantity and costs belonging in the current period
Control: physical status, operation transactions, cutoff, and customer commitment

## Applicability

Apply only to NS-000075, organization SEA, and CASE-075. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from first next-period qualified slot; external timing is conditional on missing-material recovery. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
