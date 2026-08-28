# timecard-to-resource-cost reconciliation

Case: CASE-071
Document control number: SPEC-0071
Effective revision: R2
Superseded revision visible in archive: R10
Subject: missing setup labor
Primary measure: signed setup hours at the approved resource rate
Source finished or header quantity: 1020
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: hours not already posted to the correct operation
Exclusion definition: duplicate, unsigned, or wrong-period hours
Control: employee, timecard, operation, rate, and period must reconcile
Task-specific financial control: signed-timecard posting variance
Control threshold: USD 0.0

## Applicability

Apply only to NS-000071, organization SEA, and CASE-071. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from open cost-posting period; external timing is conditional on timecard approval status. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
