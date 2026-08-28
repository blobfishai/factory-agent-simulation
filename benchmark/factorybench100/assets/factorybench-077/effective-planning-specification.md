# milestone approval and project supply netting

Case: CASE-077
Document control number: SPEC-0077
Effective revision: R1
Superseded revision visible in archive: R10
Subject: project milestone supply
Primary measure: milestone demand at the authorized project task
Source finished or header quantity: 65
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: same-project on-hand and firm supply
Exclusion definition: common or other-project coverage and late receipts
Control: milestone approval, project, task, quantity, destination, and need-by

## Applicability

Apply only to NS-000077, organization SEA, and CASE-077. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from prototype production slot; external timing is conditional on project-specific supplier readiness. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
