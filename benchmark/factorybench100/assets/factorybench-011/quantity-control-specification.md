# lot shelf-life and certificate ledger

Case: CASE-011
Document control number: SPEC-0011
Effective revision: R5
Superseded revision visible in archive: R10
Subject: adhesive issue to WO-0011
Primary measure: adhesive quantity required by operation 10
Source finished or header quantity: 86
Effective usage per finished or header unit: 1 KG
Unit: KG
Eligibility definition: FEFO lot quantity with valid shelf life and certificate
Exclusion definition: expired, reserved, or wrong-revision adhesive
Control: issue the earliest-expiry conforming lot without breaking its reservation

## Applicability

Apply only to NS-000011, organization SEA, and CASE-011. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from operation consumption window; external timing is conditional on replacement-lot arrival. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
