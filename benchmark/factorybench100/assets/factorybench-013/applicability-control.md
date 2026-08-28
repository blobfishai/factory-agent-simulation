# scanner log and lot-correction crosswalk

Case: CASE-013
Document control number: SPEC-0013
Effective revision: R7
Superseded revision visible in archive: R9
Subject: wrong-lot inventory scan
Primary measure: candidate scan and lot records
Source finished or header quantity: 4
Effective usage per finished or header unit: 1 RECORDS
Unit: RECORDS
Eligibility definition: scan matching item, location, timestamp, and supervisor confirmation
Exclusion definition: similar scans from other lots or operations
Control: reverse the erroneous lot movement before posting the verified lot

## Applicability

Apply only to NS-000013, organization SEA, and CASE-013. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from transaction interface cutoff; external timing is conditional on scanner-log retention. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
