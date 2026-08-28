# carrier rollover and delivery calendar

Case: CASE-003
Document control number: SPEC-0003
Effective revision: R4
Superseded revision visible in archive: R8
Subject: customer order SO-47003
Primary measure: finished units committed to the rolled sailing
Source finished or header quantity: 53
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: units already packed and carrier-ready
Exclusion definition: units missing the rolled cutoff
Control: new sailing cutoff plus port transit and customer dock window

## Applicability

Apply only to NS-000003, organization SEA, and CASE-003. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from packing capacity before each cutoff; external timing is conditional on carrier's confirmed next-sailing and airfreight quotes. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
