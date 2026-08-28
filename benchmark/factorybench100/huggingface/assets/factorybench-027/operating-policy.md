# Generate the quarterly compressor forecast — operating policy

Decision scope: quarterly compressor program.

Control rule: generate only due rows inside the bounded horizon. Establish the immutable source record and effective revision, then reconcile eligible active compressors in the forecast horizon, assets with approved quarterly pattern and no existing forecast, and inactive assets, blackout dates, and duplicate forecasts from independent records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. The final mutation must be atomic and limited to the supported record and measure.

Required closeout records: mark the existing operations thread complete with the approved check reaction; and append one dated decision row to the existing audit tab; do not overwrite prior entries.
