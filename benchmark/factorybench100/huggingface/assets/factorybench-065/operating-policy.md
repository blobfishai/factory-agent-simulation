# Create constrained supply for a service allocation — operating policy

Decision scope: priority service allocation.

Control rule: priority, entitlement, destination, quantity, and need-by must match. Establish the immutable source record and effective revision, then reconcile service demand authorized by allocation policy, stock already reserved to that service request, and stock protected for higher priority or wrong destination from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: append one dated decision row to the existing audit tab; do not overwrite prior entries; and mark the existing operations thread complete with the approved check reaction.
