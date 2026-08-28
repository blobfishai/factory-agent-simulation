# label nonconformance and supplier RMA

Case: CASE-040
Document control number: SPEC-0040
Effective revision: R6
Superseded revision visible in archive: R9
Subject: mislabeled relay receipt
Primary measure: received quantity under the affected label
Source finished or header quantity: 73
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: units covered by the supplier return authorization
Exclusion definition: correctly labeled or already consumed units
Control: label nonconformance, lot, PO line, and RMA quantity must match

## Applicability

Apply only to NS-000040, organization SEA, and CASE-040. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from return-dock pickup window; external timing is conditional on supplier RMA and replacement date. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
