# supplier acknowledgment and PO schedule

Case: CASE-032
Document control number: SPEC-0032
Effective revision: R5
Superseded revision visible in archive: R10
Subject: open purchase order PO-0032
Primary measure: open quantity covered by the acknowledgment
Source finished or header quantity: 60
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: quantity and date explicitly confirmed by the supplier
Exclusion definition: closed lines and quantities omitted from the acknowledgment
Control: supplier reference, PO line, quantity, and promised date must correlate

## Applicability

Apply only to NS-000032, organization SEA, and CASE-032. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from downstream production need date; external timing is conditional on signed supplier acknowledgment. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
