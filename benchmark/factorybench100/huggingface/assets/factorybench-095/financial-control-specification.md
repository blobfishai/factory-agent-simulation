# maintenance timecard and cost reconciliation

Case: CASE-095
Document control number: SPEC-0095
Effective revision: R5
Superseded revision visible in archive: R10
Subject: omitted maintenance labor
Primary measure: signed labor value for the maintenance order
Source finished or header quantity: 782
Effective usage per finished or header unit: 1 USD
Unit: USD
Eligibility definition: hours inside asset work and open period not already posted
Exclusion definition: duplicate, unrelated, or post-cutoff hours
Control: technician, asset, maintenance order, rate, timecard, and period
Task-specific financial control: signed-maintenance-labor posting variance
Control threshold: USD 0.0

## Applicability

Apply only to NS-000095, organization SEA, and CASE-095. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from final cost-posting window; external timing is conditional on supervisor timecard approval. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
