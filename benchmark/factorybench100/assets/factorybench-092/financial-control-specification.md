# invoice batch and close-calendar match

Case: CASE-092
Document control number: SPEC-0092
Effective revision: R2
Superseded revision visible in archive: R10
Subject: final invoice batch item
Primary measure: invoice gross amount
Source finished or header quantity: 20127
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: PO and receipt matched amount inside tolerance
Exclusion definition: duplicate, unmatched, or post-cutoff value
Control: batch item, supplier, match, approval, and accounting date
Task-specific financial control: document-specific matching tolerance
Control threshold: USD 100.64

## Applicability

Apply only to NS-000092, organization SEA, and CASE-092. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from final validation and posting cutoff; external timing is conditional on supplier invoice source. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
