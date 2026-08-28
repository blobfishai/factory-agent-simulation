# inspection forecast and shutdown reconciliation

Case: CASE-028
Document control number: SPEC-0028
Effective revision: R1
Superseded revision visible in archive: R9
Subject: guarded-saw inspection forecast
Primary measure: forecast rows due before the next shutdown
Source finished or header quantity: 11
Effective usage per finished or header unit: 1 WORK_ORDERS
Unit: WORK_ORDERS
Eligibility definition: due rows with active assets and safe shutdown windows
Exclusion definition: already generated, inactive, or blackout-window rows
Control: one work order per eligible forecast row without duplication
Effective trigger threshold: 1 WORK_ORDERS

## Applicability

Apply only to NS-000028, organization SEA, and CASE-028. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from approved shutdown windows; external timing is conditional on guard-inspection kit readiness. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
