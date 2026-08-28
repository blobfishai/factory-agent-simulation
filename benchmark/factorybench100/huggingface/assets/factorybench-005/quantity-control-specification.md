# EDI duplicate-release comparison

Case: CASE-005
Document control number: SPEC-0005
Effective revision: R6
Superseded revision visible in archive: R10
Subject: duplicate EDI release on SO-47005
Primary measure: purchase quantity created from the suspect release
Source finished or header quantity: 103
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: unconsumed quantity traceable only to the duplicate
Exclusion definition: quantity reserved or pegged to legitimate demand
Control: customer PO, line, revision, quantity, and ship window must all duplicate an existing release

## Applicability

Apply only to NS-000005, organization SEA, and CASE-005. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from remaining valid demand coverage; external timing is conditional on supplier cancellation cutoff. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
