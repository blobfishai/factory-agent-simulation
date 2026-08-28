# supplier audit and conditional-use scope

Case: CASE-046
Document control number: SPEC-0046
Effective revision: R5
Superseded revision visible in archive: R9
Subject: conditional molded-parts source
Primary measure: candidate supplier sites
Source finished or header quantity: 4
Effective usage per finished or header unit: 1 SITES
Unit: SITES
Eligibility definition: site passing audit, insurance, and trial-lot quality
Exclusion definition: expired, failed, or unapproved sites
Control: conditional use is limited by item, quantity, duration, and approval

## Applicability

Apply only to NS-000046, organization SEA, and CASE-046. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from continuity demand before incumbent recovery; external timing is conditional on trial-lot and insurance validity. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
