# packing slip, scale ticket, and interface row

Case: CASE-038
Document control number: SPEC-0038
Effective revision: R4
Superseded revision visible in archive: R10
Subject: receipt interface quantity error
Primary measure: packing-slip quantity
Source finished or header quantity: 162
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: scale-ticket and physical-count quantity
Exclusion definition: transposition overstatement
Control: correct only the erroneous interface transaction before delivery

## Applicability

Apply only to NS-000038, organization SEA, and CASE-038. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from project-stores downstream requirement; external timing is conditional on supplier-confirmed shipped quantity. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
