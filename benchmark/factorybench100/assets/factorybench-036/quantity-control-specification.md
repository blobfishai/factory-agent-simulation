# packing slip, PO, lot, and certificate

Case: CASE-036
Document control number: SPEC-0036
Effective revision: R2
Superseded revision visible in archive: R8
Subject: relay shipment against PO-0036
Primary measure: packing-slip and PO quantity
Source finished or header quantity: 112
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: physically counted relays with matching supplier lot and certificate
Exclusion definition: overage, wrong lot, or uncertified units
Control: PO line, receipt organization, lot, certificate, and dock count must reconcile

## Applicability

Apply only to NS-000036, organization SEA, and CASE-036. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from inspection capacity before put-away; external timing is conditional on supplier certificate and packing slip. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
