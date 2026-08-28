# interplant availability and reservation ledger

Case: CASE-056
Document control number: SPEC-0056
Effective revision: R1
Superseded revision visible in archive: R10
Subject: relay lot transfer
Primary measure: destination shortage
Source finished or header quantity: 83
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: source-plant available quantity after reservations
Exclusion definition: quarantined, project-owned, or safety-stock quantity
Control: lot, ownership, transit, and destination reservation must remain valid

## Applicability

Apply only to NS-000056, organization SEA, and CASE-056. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from interplant handling and transit window; external timing is conditional on external replenishment date. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
