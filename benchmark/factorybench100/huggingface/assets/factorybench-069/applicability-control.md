# service-bulletin effectivity register

Case: CASE-069
Document control number: SPEC-0069
Effective revision: R7
Superseded revision visible in archive: R8
Subject: released service bulletin
Primary measure: candidate bulletin revisions
Source finished or header quantity: 3
Effective usage per finished or header unit: 1 FILES
Unit: FILES
Eligibility definition: released revision applicable to asset model and serial
Exclusion definition: draft, superseded, or wrong-model bulletins
Control: bulletin number, revision, release, model, serial, and work order must match

## Applicability

Apply only to NS-000069, organization SEA, and CASE-069. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from repair-work start date; external timing is conditional on engineering release record. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
