# invoice freight and PO charge policy

Case: CASE-042
Document control number: SPEC-0042
Effective revision: R1
Superseded revision visible in archive: R8
Subject: freight variance on INV-0042
Primary measure: invoice amount including freight
Source finished or header quantity: 13264
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: PO-supported goods and allowed charges
Exclusion definition: freight excluded from the contract above tolerance
Control: hold only the documented exception with the approved reason
Task-specific financial control: contract freight tolerance
Control threshold: USD 50.0

## Applicability

Apply only to NS-000042, organization SEA, and CASE-042. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from payment-run cutoff; external timing is conditional on supplier freight explanation. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
