# outside-processing yield reconciliation

Case: CASE-099
Document control number: SPEC-0099
Effective revision: R2
Superseded revision visible in archive: R8
Subject: outside-processing yield loss
Primary measure: quantity sent for processing
Source finished or header quantity: 58
Effective usage per finished or header unit: 1 EA
Unit: EA
Eligibility definition: accepted processed quantity
Exclusion definition: inspection-rejected and missing quantity
Control: accepted plus rejected plus missing must reconcile to sent quantity

## Applicability

Apply only to NS-000099, organization SEA, and CASE-099. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from remaining production requirement; external timing is conditional on supplier replacement and credit response. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
