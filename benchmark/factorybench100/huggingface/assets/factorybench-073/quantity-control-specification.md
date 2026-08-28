# final count and production-quantity bridge

Case: CASE-073
Document control number: SPEC-0073
Effective revision: R4
Superseded revision visible in archive: R9
Subject: final-count scrap
Primary measure: production quantity reported before final count
Source finished or header quantity: 104
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: good completed units physically verified
Exclusion definition: scrap units signed by the supervisor
Control: good plus scrap plus prior reject must reconcile to operation input

## Applicability

Apply only to NS-000073, organization SEA, and CASE-073. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from operation close window; external timing is conditional on disposition approval. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
