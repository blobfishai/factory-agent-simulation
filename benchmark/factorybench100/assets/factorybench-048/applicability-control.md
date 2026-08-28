# sanctions match and legal-entity evidence

Case: CASE-048
Document control number: SPEC-0048
Effective revision: R7
Superseded revision visible in archive: R8
Subject: sanctions-screening match
Primary measure: open supplier commitments screened
Source finished or header quantity: 3
Effective usage per finished or header unit: 1 ORDERS
Unit: ORDERS
Eligibility definition: orders tied to the confirmed legal-entity match
Exclusion definition: false positives and unrelated affiliates
Control: legal entity, address, ownership, screening list, and legal direction must correlate

## Applicability

Apply only to NS-000048, organization SEA, and CASE-048. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from replacement-source readiness; external timing is conditional on legal screening disposition. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
