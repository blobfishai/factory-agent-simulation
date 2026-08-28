# compressor roster and maintenance calendar

Case: CASE-027
Document control number: SPEC-0027
Effective revision: R7
Superseded revision visible in archive: R8
Subject: quarterly compressor program
Primary measure: eligible active compressors in the forecast horizon
Source finished or header quantity: 14
Effective usage per finished or header unit: 1 ASSETS
Unit: ASSETS
Eligibility definition: assets with approved quarterly pattern and no existing forecast
Exclusion definition: inactive assets, blackout dates, and duplicate forecasts
Control: generate only due rows inside the bounded horizon
Effective trigger threshold: 1 ASSETS

## Applicability

Apply only to NS-000027, organization SEA, and CASE-027. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.

## Reconciliation rule

Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.

## Timing and authority

Internal timing comes from shutdown calendar availability; external timing is conditional on contractor coverage by month. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.

## Output control

The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.
