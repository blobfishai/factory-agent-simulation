# Validate an outside-processing invoice — operating policy

Decision scope: outside-processing invoice.

Control rule: PO line, receipt, inspection, invoice, currency, and tolerance. Establish the immutable source record and effective revision, then reconcile invoice amount and billed operation quantity, accepted supplier-operation quantity at the PO rate, and rejected, unreceived, duplicate, or rate-variance value from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: record the selected option, committed completion, and binding constraint in the existing Control outcome cell; and send the scoped completion reply in the existing email thread.
