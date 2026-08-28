# alarm history and reliability trigger matrix

Case: CASE-025
Document control number: SPEC-0025
Effective revision: R5
Superseded revision visible in archive: R9
Subject: repeated bearing alarm on ASSET-025
Primary measure: qualifying alarms inside the reliability window
Source finished or header quantity: 7
Effective usage per finished or header unit: 1 ALARMS
Unit: ALARMS
Eligibility definition: distinct alarms meeting duration and severity thresholds
Exclusion definition: duplicate telemetry and acknowledged nuisance events
Control: the third qualifying alarm plus reliability approval triggers planned work
Effective trigger threshold: 3 ALARMS

## Applicability

Apply only to NS-000025, organization SEA, and CASE-025. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from next production-safe maintenance window; external timing is conditional on bearing-kit readiness. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
