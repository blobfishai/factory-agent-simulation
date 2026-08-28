# executed contract and supplier-site terms

Case: CASE-044
Document control number: SPEC-0044
Effective revision: R3
Superseded revision visible in archive: R10
Subject: payment terms on INV-0044
Primary measure: invoice amount governed by the contract
Source finished or header quantity: 13539
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: amount at the signed supplier-site terms
Exclusion definition: value under an obsolete master term
Control: executed agreement, effective date, supplier site, and invoice must match
Task-specific financial control: unsupported monetary variance after applying signed terms
Control threshold: USD 0.0

## Applicability

Apply only to NS-000044, organization SEA, and CASE-044. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from discount and payment calendar; external timing is conditional on signed contract terms. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
