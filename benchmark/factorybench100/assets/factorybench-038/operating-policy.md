# Correct a transposed receiving quantity — operating policy

Decision scope: receipt interface quantity error.

Control rule: correct only the erroneous interface transaction before delivery. Establish the immutable source record and effective revision, then reconcile packing-slip quantity, scale-ticket and physical-count quantity, and transposition overstatement from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: add the resulting Oracle reference, option, date, and constraint as a comment on the existing case file; and append one dated decision row to the existing audit tab; do not overwrite prior entries.
