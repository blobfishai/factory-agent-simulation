# diagnostic report identity and checksum register

Case: CASE-024
Document control number: SPEC-0024
Effective revision: R4
Superseded revision visible in archive: R8
Subject: vendor diagnostic report for ASSET-024
Primary measure: candidate diagnostic documents
Source finished or header quantity: 3
Effective usage per finished or header unit: 1 FILES
Unit: FILES
Eligibility definition: document matching asset serial, failure date, and checksum
Exclusion definition: reports for similar assets or superseded revisions
Control: only the immutable matching report may be linked to the open order

## Applicability

Apply only to NS-000024, organization SEA, and CASE-024. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from maintenance document-review window; external timing is conditional on vendor's signed report revision. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
