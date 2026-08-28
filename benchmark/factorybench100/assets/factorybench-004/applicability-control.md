# substitution effectivity matrix

Case: CASE-004
Document control number: SPEC-0004
Effective revision: R5
Superseded revision visible in archive: R9
Subject: obsolete controller configuration on SO-47004
Primary measure: open order lines at the obsolete revision
Source finished or header quantity: 4
Effective usage per finished or header unit: 1 LINES
Unit: LINES
Eligibility definition: lines inside the approved substitute effectivity
Exclusion definition: completed or out-of-effectivity serials
Control: engineering change, customer configuration, and serial breakpoint must all match

## Applicability

Apply only to NS-000004, organization SEA, and CASE-004. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from remaining configuration-validation window; external timing is conditional on supplier availability for the approved substitute. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
