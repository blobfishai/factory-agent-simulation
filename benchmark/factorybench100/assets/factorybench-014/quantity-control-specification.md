# electronic traveler and serial ledger

Case: CASE-014
Document control number: SPEC-0014
Effective revision: R1
Superseded revision visible in archive: R10
Subject: serial-controlled panel completion
Primary measure: serials assigned to the final operation
Source finished or header quantity: 119
Effective usage per finished or header unit: 1 SERIALS
Unit: SERIALS
Eligibility definition: serials with every traveler signature and passed test
Exclusion definition: missing-signature, duplicate, or failed-test serials
Control: completed quantity must equal the distinct eligible serial set

## Applicability

Apply only to NS-000014, organization SEA, and CASE-014. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from final-operation completion window; external timing is conditional on missing signature resolution. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
