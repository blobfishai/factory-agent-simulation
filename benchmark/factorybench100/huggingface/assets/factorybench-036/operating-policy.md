# Receive a lot-controlled relay shipment — operating policy

Decision scope: relay shipment against PO-0036.

Control rule: PO line, receipt organization, lot, certificate, and dock count must reconcile. Establish the immutable source record and effective revision, then reconcile packing-slip and PO quantity, physically counted relays with matching supplier lot and certificate, and overage, wrong lot, or uncertified units from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: send the scoped completion reply in the existing email thread; and record the selected option, committed completion, and binding constraint in the existing Control outcome cell.
