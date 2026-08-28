# Stop supply for a duplicated customer release — operating policy

Decision scope: duplicate EDI release on SO-47005.

Control rule: customer PO, line, revision, quantity, and ship window must all duplicate an existing release. Establish the immutable source record and effective revision, then reconcile purchase quantity created from the suspect release, unconsumed quantity traceable only to the duplicate, and quantity reserved or pegged to legitimate demand from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: send the scoped completion reply in the existing email thread; and record the selected option, committed completion, and binding constraint in the existing Control outcome cell.
