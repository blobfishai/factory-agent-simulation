# raw measurement and correction audit trail

Case: CASE-053
Document control number: SPEC-0053
Effective revision: R5
Superseded revision visible in archive: R10
Subject: mistyped dimensional result
Primary measure: candidate measurement and source rows
Source finished or header quantity: 5
Effective usage per finished or header unit: 1 RECORDS
Unit: RECORDS
Eligibility definition: row matching sample, characteristic, instrument, and timestamp
Exclusion definition: other samples and derived summary cells
Control: signed raw reading and correction approval control the exact field change

## Applicability

Apply only to NS-000053, organization SEA, and CASE-053. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from inspection-close window; external timing is conditional on metrology source record. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
