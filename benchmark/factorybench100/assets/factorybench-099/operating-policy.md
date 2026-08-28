# Record yield loss from rejected processed parts — operating policy

Decision scope: outside-processing yield loss.

Control rule: accepted plus rejected plus missing must reconcile to sent quantity. Establish the immutable source record and effective revision, then reconcile quantity sent for processing, accepted processed quantity, and inspection-rejected and missing quantity from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: post the decided option, date, constraint, alternatives, and Oracle reference in the existing operations thread; and prepare the reply in the existing email thread and leave it as a draft for review; do not send it.
