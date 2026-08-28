# outside-processing three-way match

Case: CASE-074
Document control number: SPEC-0074
Effective revision: R5
Superseded revision visible in archive: R10
Subject: outside-processing invoice
Primary measure: invoice amount and billed operation quantity
Source finished or header quantity: 17656
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: accepted supplier-operation quantity at the PO rate
Exclusion definition: rejected, unreceived, duplicate, or rate-variance value
Control: PO line, receipt, inspection, invoice, currency, and tolerance
Task-specific financial control: document-specific matching tolerance
Control threshold: USD 88.28

## Applicability

Apply only to NS-000074, organization SEA, and CASE-074. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from payment and production-close cutoff; external timing is conditional on supplier invoice and operation report. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
