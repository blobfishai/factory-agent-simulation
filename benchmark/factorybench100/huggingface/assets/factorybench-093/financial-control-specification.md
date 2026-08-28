# duplicate-invoice fingerprint reconciliation

Case: CASE-093
Document control number: SPEC-0093
Effective revision: R3
Superseded revision visible in archive: R8
Subject: suspected duplicate invoice
Primary measure: second invoice amount presented for close
Source finished or header quantity: 20264
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: payable value unique to the second invoice after duplicate testing
Exclusion definition: amount already represented by the original invoice
Control: supplier, number normalization, date, amount, PO, and attachment hash must match after legitimate tax and credit differences are removed
Task-specific financial control: duplicate invoice payable amount
Control threshold: USD 0.0

## Applicability

Apply only to NS-000093, organization SEA, and CASE-093. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from payment-run cutoff; external timing is conditional on supplier duplicate confirmation. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
