# Cancel redundant purchase supply after demand deletion — operating policy

Decision scope: purchase supply after demand deletion.

Control rule: demand deletion, pegging, downstream reservations, and cancellation cutoff. Establish the immutable source record and effective revision, then reconcile open purchase quantity pegged to deleted demand, unreserved, unreceived quantity with no remaining peg, and quantity reserved, received, or re-pegged from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: record the selected option, committed completion, and binding constraint in the existing Control outcome cell; and prepare the reply in the existing email thread and leave it as a draft for review; do not send it.
