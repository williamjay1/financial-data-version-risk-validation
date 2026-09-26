# Round-two analytical files

The original frozen cohort has 5,502 filing windows. `row_id` is CIK plus original accession; `cluster_id` is the historical cofiling sampling unit, not a certified legal corporate group. `registry_event_365` is the directly linked first-registry-event indicator. `sample_weight` is the original design weight. `decision_date + 455 days` determines final-label maturity. A/B share the missingness mask.

Model prediction tables use `experiment`, `block`, `model`, `train_version`, `score_version`, `row_id`, `label`, `pred`, and `sample_weight`. `pred` and `prediction` aliases, where both exist, describe the same probability. Blocks are 2016_2017, 2018_2019 and 2020_2021. AA, AB, BA and BB encode fitting version followed by scoring version. AP and Brier are probabilities/scales 0–1; multiplying a difference by 100 gives percentage points.

`results/development_controls/` contains the frozen design and exact matched deletion row lists, five-seed diagnostics, identical-input control, all four original LightGBM candidate configurations, CPI development/evaluation decomposition, absolute spline/RF results, 710 fitted/reused final artifacts, 1,390 metric rows and 1,287,820 predictions. Twenty matching repeats share the same test set; they are not independent test samples. Ordinary negative matches fix origin year, label and stage, not sampling stratum or total deleted weight.

`datasets/fit_date_<block>.parquet` retains all original rows and A values. B is the coherent pre-fit-date training bundle on eligible mature development rows; outside them B=A. `later_accession`/`later_filed` describe this active choice; `unlimited_later_*` retain historical unlimited choices. The fact lineage provides component/tag/period/unit/source identity. `results/fit_date/models` scores all alternatives with A test features.

`datasets/source_verified_corrected_scale_only.parquet` uses 22 independently listed Nobilis scale contexts. The primary A/B feature changes are one A log-assets cell and one B log-assets cell; proportional ratios cancel. C is a descriptive per-tag alternative, not an additional primary model arm. The earlier four sign claims remain unresolved.

`results/evaluation_diagnostics/perturbation_modes_all_replicates.parquet` has 14,400 metric rows: 200 replicates × 3 blocks × 2 learners × 3 modes × 4 metrics. AA/BB/delta describe the matched replicate's performance under the chosen development/evaluation weighting. The distribution summary has 216 rows (including each of AA, BB and delta). Original saved refitting prediction files and sample multipliers remain in the previous-round directory.

Source exposure, adjacent-horizon and continuity tables are retrospective descriptions. Missing source-history coverage must remain unknown; absent annual reporting is not a bankruptcy or survival label. Raw-source reconstruction is outside the portable prediction-only entry.
