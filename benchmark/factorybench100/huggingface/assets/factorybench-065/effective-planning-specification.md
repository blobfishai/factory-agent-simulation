# service allocation and entitlement register

Case: CASE-065
Document control number: SPEC-0065
Effective revision: R3
Superseded revision visible in archive: R10
Subject: priority service allocation
Primary measure: service demand authorized by allocation policy
Source finished or header quantity: 99
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: stock already reserved to that service request
Exclusion definition: stock protected for higher priority or wrong destination
Control: priority, entitlement, destination, quantity, and need-by must match

## Applicability

Apply only to NS-000065, organization SEA, and CASE-065. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from service dispatch window; external timing is conditional on replenishment to the field destination. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
