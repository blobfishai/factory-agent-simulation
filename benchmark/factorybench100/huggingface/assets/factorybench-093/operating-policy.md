# Hold a duplicate invoice found in reconciliation — operating policy

Decision scope: suspected duplicate invoice.

Control rule: supplier, number normalization, date, amount, PO, and attachment hash must match after legitimate tax and credit differences are removed. Establish the immutable source record and effective revision, then reconcile second invoice amount presented for close, payable value unique to the second invoice after duplicate testing, and amount already represented by the original invoice from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: mark the existing operations thread complete with the approved check reaction; and prepare the reply in the existing email thread and leave it as a draft for review; do not send it.
