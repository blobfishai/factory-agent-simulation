# service reservation and spare-issue ledger

Case: CASE-084
Document control number: SPEC-0084
Effective revision: R1
Superseded revision visible in archive: R8
Subject: reserved emergency spare
Primary measure: spare quantity required by the repair operation
Source finished or header quantity: 59
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: reservation tied to the same service request and asset
Exclusion definition: stock reserved for higher-priority events or wrong ownership
Control: reservation, service priority, item, lot, and repair operation

## Applicability

Apply only to NS-000084, organization SEA, and CASE-084. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from emergency technician window; external timing is conditional on regional replacement-stock arrival. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
