# Receive accepted plated housings from processing — operating policy

Decision scope: plated housings returned from processing.

Control rule: PO line, supplier lot, inspection result, and dock count. Establish the immutable source record and effective revision, then reconcile supplier shipment quantity, inspection-accepted quantity with matching outside-processing PO, and rejected, missing, or wrong-lot housings from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: prepare the reply in the existing email thread and leave it as a draft for review; do not send it; and add the resulting Oracle reference, option, date, and constraint as a comment on the existing case file.
