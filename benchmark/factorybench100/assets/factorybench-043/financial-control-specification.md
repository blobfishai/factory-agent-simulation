# credit memo and hold-release reconciliation

Case: CASE-043
Document control number: SPEC-0043
Effective revision: R2
Superseded revision visible in archive: R9
Subject: existing invoice hold on INV-0043
Primary measure: held variance amount
Source finished or header quantity: 402
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: credit memo applied to the same invoice and reason
Exclusion definition: unapplied or unrelated credit value
Control: credit, invoice, hold, and manager release approval must match
Task-specific financial control: credit-to-hold residual variance
Control threshold: USD 0.0

## Applicability

Apply only to NS-000043, organization SEA, and CASE-043. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from next payment-run cutoff; external timing is conditional on supplier credit memo. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
