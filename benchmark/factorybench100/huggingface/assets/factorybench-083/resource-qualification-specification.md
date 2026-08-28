# asset entitlement and depot diagnosis

Case: CASE-083
Document control number: SPEC-0083
Effective revision: R7
Superseded revision visible in archive: R10
Subject: customer asset depot repair
Primary measure: repair-hours and parts under entitlement
Source finished or header quantity: 74
Effective usage per finished or header unit: 1 HR
Unit: HR
Eligibility definition: qualified depot labor and covered parts
Exclusion definition: cosmetic work and non-entitled damage
Control: asset serial, entitlement, diagnosis, scope, and customer authorization

## Applicability

Apply only to NS-000083, organization SEA, and CASE-083. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from depot bench and technician window; external timing is conditional on repair-part readiness. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
