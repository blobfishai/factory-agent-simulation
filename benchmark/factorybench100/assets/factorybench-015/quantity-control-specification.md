# timecard, rate, and calibration reconciliation

Case: CASE-015
Document control number: SPEC-0015
Effective revision: R2
Superseded revision visible in archive: R8
Subject: test-bench resource actual
Primary measure: signed test-bench hours presented for posting
Source finished or header quantity: 130
Effective usage per finished or header unit: 1 HR
Unit: HR
Eligibility definition: hours inside the calibration window and correct operation
Exclusion definition: duplicate, out-of-window, or unsigned hours
Control: employee, operation, rate, and calibration interval must reconcile

## Applicability

Apply only to NS-000015, organization SEA, and CASE-015. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from open resource-transaction period; external timing is conditional on corrected timecard availability. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
