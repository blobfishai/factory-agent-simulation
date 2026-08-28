# overtime authorization and finite schedule

Case: CASE-019
Document control number: SPEC-0019
Effective revision: R6
Superseded revision visible in archive: R9
Subject: weekend backlog recovery
Primary measure: operation-hours in the approved backlog scope
Source finished or header quantity: 67
Effective usage per finished or header unit: 1 HR
Unit: HR
Eligibility definition: authorized weekend hours with qualified crew
Exclusion definition: hours outside the named orders or approval cap
Control: only listed orders and cost center may use the overtime window

## Applicability

Apply only to NS-000019, organization SEA, and CASE-019. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from weekend workcenter and inspection coverage; external timing is conditional on temporary labor availability. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
