# final inspection and rework-material calculation

Case: CASE-055
Document control number: SPEC-0055
Effective revision: R7
Superseded revision visible in archive: R9
Subject: failed final-inspection quantity
Primary measure: units rejected by final inspection
Source finished or header quantity: 72
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: units with approved rework disposition and recoverable BOM
Exclusion definition: scrap and accepted units
Control: supply covers only approved rework yield and component demand

## Applicability

Apply only to NS-000055, organization SEA, and CASE-055. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from rework-cell capacity; external timing is conditional on replacement-component readiness. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
