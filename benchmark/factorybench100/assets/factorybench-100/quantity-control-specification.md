# outside-processing PO final reconciliation

Case: CASE-100
Document control number: SPEC-0100
Effective revision: R3
Superseded revision visible in archive: R9
Subject: outside-processing PO closure
Primary measure: ordered outside-operation quantity
Source finished or header quantity: 49
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: accepted receipts with fully matched invoice coverage
Exclusion definition: rejected, missing, unreceived, or uninvoiced balance
Control: ordered, sent, accepted, invoiced, and paid quantities must all reconcile

## Applicability

Apply only to NS-000100, organization SEA, and CASE-100. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from production and accounting close windows; external timing is conditional on supplier final statement. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
