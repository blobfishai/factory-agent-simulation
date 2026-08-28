# outside-processing receipt and inspection

Case: CASE-097
Document control number: SPEC-0097
Effective revision: R7
Superseded revision visible in archive: R9
Subject: plated housings returned from processing
Primary measure: supplier shipment quantity
Source finished or header quantity: 119
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: inspection-accepted quantity with matching outside-processing PO
Exclusion definition: rejected, missing, or wrong-lot housings
Control: PO line, supplier lot, inspection result, and dock count

## Applicability

Apply only to NS-000097, organization SEA, and CASE-097. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from receiving and downstream operation window; external timing is conditional on supplier replacement date. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
