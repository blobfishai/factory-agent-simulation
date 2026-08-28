# forecast consumption and supplier promise

Case: CASE-062
Document control number: SPEC-0062
Effective revision: R7
Superseded revision visible in archive: R10
Subject: forecast-consumption jump
Primary measure: firm supply quantity pegged to consumed forecast
Source finished or header quantity: 74
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: quantity supplier confirmed for an earlier date
Exclusion definition: unconfirmed or unrelated supply
Control: sales-order consumption, pegging, supplier promise, and finite dates

## Applicability

Apply only to NS-000062, organization SEA, and CASE-062. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from receiving and production window; external timing is conditional on supplier pull-in acknowledgment. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
