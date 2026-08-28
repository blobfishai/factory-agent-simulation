# Recover a customer promise after a carrier rollover — operating policy

Decision scope: customer order SO-47003.

Control rule: new sailing cutoff plus port transit and customer dock window. Establish the immutable source record and effective revision, then reconcile finished units committed to the rolled sailing, units already packed and carrier-ready, and units missing the rolled cutoff from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: append one dated decision row to the existing audit tab; do not overwrite prior entries; and mark the existing operations thread complete with the approved check reaction.
