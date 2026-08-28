# lot expiry and reservation ledger

Case: CASE-054
Document control number: SPEC-0054
Effective revision: R6
Superseded revision visible in archive: R8
Subject: expired chemical lot
Primary measure: on-hand quantity in the named lot
Source finished or header quantity: 61
Effective usage per finished or header unit: 1 KG
Unit: KG
Eligibility definition: quantity physically present and traceable to the expired lot
Exclusion definition: other lots and quantity already consumed
Control: expiry, lot, location, and open reservations define containment scope

## Applicability

Apply only to NS-000054, organization SEA, and CASE-054. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from quarantine-location capacity; external timing is conditional on replacement-lot readiness. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
