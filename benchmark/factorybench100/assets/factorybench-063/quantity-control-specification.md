# demand deletion and supply-pegging audit

Case: CASE-063
Document control number: SPEC-0063
Effective revision: R1
Superseded revision visible in archive: R8
Subject: purchase supply after demand deletion
Primary measure: open purchase quantity pegged to deleted demand
Source finished or header quantity: 77
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: unreserved, unreceived quantity with no remaining peg
Exclusion definition: quantity reserved, received, or re-pegged
Control: demand deletion, pegging, downstream reservations, and cancellation cutoff

## Applicability

Apply only to NS-000063, organization SEA, and CASE-063. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from remaining demand coverage; external timing is conditional on supplier cancellation terms. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
