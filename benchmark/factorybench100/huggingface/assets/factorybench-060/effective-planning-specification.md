# kanban card, consumption, and open-supply ledger

Case: CASE-060
Document control number: SPEC-0060
Effective revision: R5
Superseded revision visible in archive: R8
Subject: kanban breach
Primary measure: replenishment needed to restore the approved card level
Source finished or header quantity: 127
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: usable stock and firm inbound within replenishment time
Exclusion definition: reserved stock and duplicate open supply
Control: breach approval, card size, minimum, maximum, and open supply

## Applicability

Apply only to NS-000060, organization SEA, and CASE-060. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from line-side consumption window; external timing is conditional on supplier or source-org replenishment. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
