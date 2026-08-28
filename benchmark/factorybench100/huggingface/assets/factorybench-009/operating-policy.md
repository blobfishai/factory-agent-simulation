# Replace a constrained relay on an active order — operating policy

Decision scope: relay material line on WO-0009.

Control rule: substitute effectivity, conversion ratio, and available lot status. Establish the immutable source record and effective revision, then reconcile remaining relay demand at the active revision, approved substitute stock after conversion ratio, and original relays already issued or substitute lots outside effectivity from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: post the decided option, date, constraint, alternatives, and Oracle reference in the existing operations thread; and record the selected option, committed completion, and binding constraint in the existing Control outcome cell.
