# meter history and lubrication threshold

Case: CASE-026
Document control number: SPEC-0026
Effective revision: R6
Superseded revision visible in archive: R10
Subject: meter-based lubrication program
Primary measure: meter usage since last lubrication
Source finished or header quantity: 2150
Effective usage per finished or header unit: 1 HOURS
Unit: HOURS
Eligibility definition: usage accepted after removing reset and duplicate readings
Exclusion definition: invalid spikes and readings before the last service
Control: effective meter threshold and blackout calendar determine the due date
Effective trigger threshold: 1800 HOURS

## Applicability

Apply only to NS-000026, organization SEA, and CASE-026. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from production-safe lubrication window; external timing is conditional on lubricant-kit readiness. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
