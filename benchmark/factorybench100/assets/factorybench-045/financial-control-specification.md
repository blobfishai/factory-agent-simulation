# metrology invoice and approval coding

Case: CASE-045
Document control number: SPEC-0045
Effective revision: R4
Superseded revision visible in archive: R8
Subject: non-PO metrology invoice
Primary measure: invoice gross amount
Source finished or header quantity: 13676
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: approved service value with valid BU and account coding
Exclusion definition: tax, duplicate, or unapproved service value
Control: supplier site, service acceptance, coding, and approval authority
Task-specific financial control: non-PO service approval ceiling
Control threshold: USD 25000.0

## Applicability

Apply only to NS-000045, organization SEA, and CASE-045. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from current accounting-period cutoff; external timing is conditional on supplier invoice PDF. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
