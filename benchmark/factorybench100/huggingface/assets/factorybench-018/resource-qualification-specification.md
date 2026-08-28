# supplier outage and alternate-source capacity

Case: CASE-018
Document control number: SPEC-0018
Effective revision: R5
Superseded revision visible in archive: R8
Subject: outside-coating operation
Primary measure: coating quantity due before assembly
Source finished or header quantity: 60
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: quantity the approved alternate can accept
Exclusion definition: WIP already at the closed supplier or outside alternate capacity
Control: alternate source, PO line, process spec, and ship window must match

## Applicability

Apply only to NS-000018, organization SEA, and CASE-018. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from downstream cure and assembly slots; external timing is conditional on alternate coater's confirmed turnaround. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
