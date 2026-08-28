# line-down shortage and sole-source exception

Case: CASE-035
Document control number: SPEC-0035
Effective revision: R1
Superseded revision visible in archive: R10
Subject: line-down component demand
Primary measure: immediate uncovered component requirement
Source finished or header quantity: 101
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: usable stock and firm inbound supply before need
Exclusion definition: reserved stock and supply arriving after the line-down point
Control: sole-source exception, exact shortage, and emergency freight authority

## Applicability

Apply only to NS-000035, organization SEA, and CASE-035. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from line recovery and receiving window; external timing is conditional on approved supplier's emergency ready date. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
