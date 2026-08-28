# Create due work for guarded saw inspections — operating policy

Decision scope: guarded-saw inspection forecast.

Control rule: one work order per eligible forecast row without duplication. Establish the immutable source record and effective revision, then reconcile forecast rows due before the next shutdown, due rows with active assets and safe shutdown windows, and already generated, inactive, or blackout-window rows from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: add the resulting Oracle reference, option, date, and constraint as a comment on the existing case file; and prepare the reply in the existing email thread and leave it as a draft for review; do not send it.
