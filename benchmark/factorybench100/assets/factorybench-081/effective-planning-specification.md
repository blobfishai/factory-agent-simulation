# technician entitlement and field-stock ledger

Case: CASE-081
Document control number: SPEC-0081
Effective revision: R5
Superseded revision visible in archive: R8
Subject: technician critical-relay stock
Primary measure: entitled min-max replenishment quantity
Source finished or header quantity: 109
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: usable van and regional stock already allocated
Exclusion definition: reserved, quarantined, or wrong-owner relays
Control: technician, territory, entitlement, min-max, and destination

## Applicability

Apply only to NS-000081, organization SEA, and CASE-081. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from dispatch route and depot cutoff; external timing is conditional on regional replenishment arrival. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
