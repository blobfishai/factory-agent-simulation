# supplier recall and lot genealogy

Case: CASE-086
Document control number: SPEC-0086
Effective revision: R3
Superseded revision visible in archive: R10
Subject: supplier recall scope
Primary measure: on-hand and WIP relays from recalled supplier lots
Source finished or header quantity: 81
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: traceable quantity inside named lot and date ranges
Exclusion definition: other suppliers, lots, and consumed-outside-scope units
Control: supplier, item, lot, receipt, genealogy, and recall effectivity

## Applicability

Apply only to NS-000086, organization SEA, and CASE-086. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from quarantine and production impact window; external timing is conditional on replacement compliant supply. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
