# issue-consumption and physical-count reconciliation

Case: CASE-012
Document control number: SPEC-0012
Effective revision: R6
Superseded revision visible in archive: R8
Subject: unused copper on canceled operation 20
Primary measure: quantity previously issued to the canceled operation
Source finished or header quantity: 97
Effective usage per finished or header unit: 1 KG
Unit: KG
Eligibility definition: physically counted unconsumed copper
Exclusion definition: scrap, consumed, or unverified copper
Control: return cannot exceed issued less consumed and must preserve project ownership

## Applicability

Apply only to NS-000012, organization SEA, and CASE-012. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from stores receiving window; external timing is conditional on recount and discrepancy resolution. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
