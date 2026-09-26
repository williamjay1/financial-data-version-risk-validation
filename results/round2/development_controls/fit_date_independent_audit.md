# Independent fit-date reconstruction audit

Scientific checks PASS. No training performed.

- Six fitted models and twelve archived anchors reproduced exactly (maximum probability difference 0).
- All 54 AP/Brier/ROC calculations matched within 1.11e-16.
- Every selected source filing date strictly precedes the final fit date; original maturity guards hold.
- All A test features, labels, weights and identities match the frozen main cohort; feature masks are unchanged.
- Ten features independently reconstructed from the selected component ledger match exactly.
- Latest source dates are at or after fitting in 6/8/6 training records, but only 3/4/2 records have different numerical model inputs versus the fit-date construction. Most latest-B training sources were already disclosed by fitting.
- The owner excluded the stale manifest self-hash; all remaining output bindings were rechecked and pass. No numerical input or prediction changed.

This verifies the saved reconstruction and outputs, not historical API snapshots or original XBRL context authentication.
