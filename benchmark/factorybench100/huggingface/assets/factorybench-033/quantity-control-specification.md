# safety bulletin and open-quantity ledger

Case: CASE-033
Document control number: SPEC-0033
Effective revision: R6
Superseded revision visible in archive: R8
Subject: resin PO affected by safety bulletin
Primary measure: open resin quantity on named lots
Source finished or header quantity: 79
Effective usage per finished or header unit: 1 KG
Unit: KG
Eligibility definition: unreceived and unconsumed quantity safe to cancel
Exclusion definition: received, consumed, or unaffected resin
Control: bulletin material code, lot scope, and cancellation authority

## Applicability

Apply only to NS-000033, organization SEA, and CASE-033. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from replacement-resin coverage; external timing is conditional on supplier cancellation deadline. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
