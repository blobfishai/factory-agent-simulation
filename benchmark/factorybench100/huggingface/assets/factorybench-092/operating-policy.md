# Validate the final matched invoice batch item — operating policy

Decision scope: final invoice batch item.

Control rule: batch item, supplier, match, approval, and accounting date. Establish the immutable source record and effective revision, then reconcile invoice gross amount, PO and receipt matched amount inside tolerance, and duplicate, unmatched, or post-cutoff value from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: post the decided option, date, constraint, alternatives, and Oracle reference in the existing operations thread; and record the selected option, committed completion, and binding constraint in the existing Control outcome cell.
