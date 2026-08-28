# Transfer a constrained relay lot between plants — operating policy

Decision scope: relay lot transfer.

Control rule: lot, ownership, transit, and destination reservation must remain valid. Establish the immutable source record and effective revision, then reconcile destination shortage, source-plant available quantity after reservations, and quarantined, project-owned, or safety-stock quantity from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: record the selected option, committed completion, and binding constraint in the existing Control outcome cell; and prepare the reply in the existing email thread and leave it as a draft for review; do not send it.
