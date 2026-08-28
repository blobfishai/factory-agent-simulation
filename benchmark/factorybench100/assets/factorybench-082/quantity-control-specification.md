# RMA, serial, and ownership reconciliation

Case: CASE-082
Document control number: SPEC-0082
Effective revision: R6
Superseded revision visible in archive: R9
Subject: returned field controller
Primary measure: serialized units received from the service event
Source finished or header quantity: 120
Effective usage per finished or header unit: 1 SERIALS
Unit: SERIALS
Eligibility definition: serials matching the RMA and customer asset
Exclusion definition: different serials, accessories, and advance replacement
Control: RMA, serial, ownership, failure code, and quarantine location

## Applicability

Apply only to NS-000082, organization SEA, and CASE-082. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from secure quarantine capacity; external timing is conditional on depot diagnostic timing. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
