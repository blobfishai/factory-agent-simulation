# nonconformance disposition and rework router

Case: CASE-008
Document control number: SPEC-0008
Effective revision: R2
Superseded revision visible in archive: R10
Subject: failed inspection on WO-0008
Primary measure: nonconforming units named by the disposition
Source finished or header quantity: 5
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: units inside the approved rework scope
Exclusion definition: scrapped or already accepted units
Control: quality disposition and routing revision must name the same lot and operation

## Applicability

Apply only to NS-000008, organization SEA, and CASE-008. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from qualified rework-cell window; external timing is conditional on rework instruction release. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
