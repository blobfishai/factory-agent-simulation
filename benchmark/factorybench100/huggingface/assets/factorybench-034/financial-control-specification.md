# service acceptance and three-way reconciliation

Case: CASE-034
Document control number: SPEC-0034
Effective revision: R7
Superseded revision visible in archive: R9
Subject: calibration-services PO
Primary measure: ordered service value
Source finished or header quantity: 12166
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: accepted service-entry and matched invoice value
Exclusion definition: unaccepted or unmatched value
Control: receipt, acceptance, invoice, and buyer approval must all be complete
Task-specific financial control: final-close residual balance
Control threshold: USD 0.0

## Applicability

Apply only to NS-000034, organization SEA, and CASE-034. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from current close-processing window; external timing is conditional on supplier's final invoice status. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
