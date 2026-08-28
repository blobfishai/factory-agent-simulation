# relay substitute and effectivity matrix

Case: CASE-009
Document control number: SPEC-0009
Effective revision: R3
Superseded revision visible in archive: R8
Subject: relay material line on WO-0009
Primary measure: remaining relay demand at the active revision
Source finished or header quantity: 64
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: approved substitute stock after conversion ratio
Exclusion definition: original relays already issued or substitute lots outside effectivity
Control: substitute effectivity, conversion ratio, and available lot status

## Applicability

Apply only to NS-000009, organization SEA, and CASE-009. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from remaining install-window capacity; external timing is conditional on supplier replenishment for the original relay. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
