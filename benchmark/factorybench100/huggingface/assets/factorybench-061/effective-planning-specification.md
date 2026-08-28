# revised demand and supply-pegging workbook

Case: CASE-061
Document control number: SPEC-0061
Effective revision: R6
Superseded revision visible in archive: R9
Subject: copper demand spike
Primary measure: revised demand inside the planning horizon
Source finished or header quantity: 55
Effective usage per finished or header unit: 1 KG
Unit: KG
Eligibility definition: usable on-hand and firm supply before need
Exclusion definition: reserved, late, or unfirm coverage
Control: net only the incremental demand and avoid double coverage

## Applicability

Apply only to NS-000061, organization SEA, and CASE-061. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from qualified production need date; external timing is conditional on supplier copper lead time. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
