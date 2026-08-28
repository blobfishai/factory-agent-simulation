# Validate a clean three-way-matched invoice — operating policy

Decision scope: supplier invoice INV-0041.

Control rule: supplier, PO line, receipt, currency, tax, and tolerance must reconcile. Establish the immutable source record and effective revision, then reconcile invoice gross amount, PO-backed accepted-receipt amount within tolerance, and unmatched tax, freight, or quantity variance from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: append one dated decision row to the existing audit tab; do not overwrite prior entries; and mark the existing operations thread complete with the approved check reaction.
