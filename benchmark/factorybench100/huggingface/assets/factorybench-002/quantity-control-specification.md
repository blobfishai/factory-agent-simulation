# export classification and end-use register

Case: CASE-002
Document control number: SPEC-0002
Effective revision: R3
Superseded revision visible in archive: R10
Subject: defense order SO-47002
Primary measure: total ordered controller quantity
Source finished or header quantity: 80
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: domestic lines released by trade compliance
Exclusion definition: export-controlled lines awaiting a license
Control: release only quantities whose destination and end-use are cleared

## Applicability

Apply only to NS-000002, organization SEA, and CASE-002. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from domestic build capacity that preserves the held line; external timing is conditional on counsel's export-license decision date. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
