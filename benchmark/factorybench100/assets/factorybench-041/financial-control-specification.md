# invoice, PO, receipt, and tolerance reconciliation

Case: CASE-041
Document control number: SPEC-0041
Effective revision: R7
Superseded revision visible in archive: R10
Subject: supplier invoice INV-0041
Primary measure: invoice gross amount
Source finished or header quantity: 13127
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: PO-backed accepted-receipt amount within tolerance
Exclusion definition: unmatched tax, freight, or quantity variance
Control: supplier, PO line, receipt, currency, tax, and tolerance must reconcile
Task-specific financial control: document-specific matching tolerance
Control threshold: USD 65.64

## Applicability

Apply only to NS-000041, organization SEA, and CASE-041. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from open accounting and payment cycle; external timing is conditional on supplier PDF invoice. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
