# supplier send-receive-yield bridge

Case: CASE-098
Document control number: SPEC-0098
Effective revision: R1
Superseded revision visible in archive: R10
Subject: outside operation completion
Primary measure: quantity sent to the supplier operation
Source finished or header quantity: 130
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: accepted quantity received and available to the order
Exclusion definition: rejected, missing, or not-yet-received quantity
Control: operation completion cannot exceed accepted returned quantity

## Applicability

Apply only to NS-000098, organization SEA, and CASE-098. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from next internal operation capacity; external timing is conditional on supplier recovery for missing units. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
