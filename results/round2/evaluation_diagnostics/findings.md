# Evaluation diagnostics round 2

All outputs use frozen empirical data and saved predictions. No model was refitted. All added analyses are post hoc explanatory diagnostics.

## Unrounded four-cell AP contrasts (percentage points)

| Block | Input AB-AA | Fit BA-AA | Interaction | Total BB-AA |
|---|---:|---:|---:|---:|
|2016_2017|-2.777217242|4.945023004|0.671314244|2.839120007|
|2018_2019|1.367323556|1.432364885|-0.032122284|2.767566157|
|2020_2021|0.112106036|1.901084712|-0.246900209|1.766290539|

## Paired AP perturbation modes

| Block | Model | Mode | Median pp | 5th–95th pp | Positive fraction |
|---|---|---|---:|---:|---:|
|2016_2017|LGBM|development_only|-0.194578|[-8.992209, 8.623044]|0.485|
|2016_2017|LGBM|evaluation_only|2.815577|[0.204974, 5.624917]|0.980|
|2016_2017|LGBM|joint|-0.026517|[-9.848049, 9.049766]|0.500|
|2016_2017|LR|development_only|-0.006069|[-0.223697, 0.007029]|0.085|
|2016_2017|LR|evaluation_only|-0.005642|[-0.025260, 0.001012]|0.085|
|2016_2017|LR|joint|-0.007595|[-0.308168, 0.010202]|0.125|
|2018_2019|LGBM|development_only|1.887232|[-11.857783, 16.056851]|0.595|
|2018_2019|LGBM|evaluation_only|2.966468|[0.527865, 7.344082]|0.980|
|2018_2019|LGBM|joint|2.047111|[-11.587614, 15.167238]|0.600|
|2018_2019|LR|development_only|-0.001130|[-0.069667, 0.014735]|0.415|
|2018_2019|LR|evaluation_only|-0.083155|[-1.182720, 0.032646]|0.125|
|2018_2019|LR|joint|-0.000485|[-0.057161, 0.028799]|0.470|
|2020_2021|LGBM|development_only|0.852418|[-7.085490, 7.971842]|0.595|
|2020_2021|LGBM|evaluation_only|1.513212|[-3.453086, 2.782291]|0.660|
|2020_2021|LGBM|joint|1.045517|[-6.631583, 9.161098]|0.600|
|2020_2021|LR|development_only|-0.010767|[-0.055567, 0.013166]|0.200|
|2020_2021|LR|evaluation_only|-0.009327|[-0.049326, 0.013218]|0.215|
|2020_2021|LR|joint|-0.015157|[-0.110073, 0.021340]|0.250|

These are the same paired draws in three computational modes, not independent experiments or additive variance components. Empirical quantiles are not confidence limits. Evaluation-only uses the same 200 draws as joint and development-only; the older conditional table uses its separate frozen 1000-draw seed.

## Full-cohort version exposure

label,exposure_group,raw_n,within_label_weighted_fraction,continuity_known_raw_n,continuity_unknown_raw_n,continuity_within_known_weighted_fraction

0,no_later_bundle,1266,0.2444037143469527,1266,0,0.4576734218147824

0,later_without_raw_change,2766,0.5362271847170565,2766,0,0.6883174211148241

0,later_with_raw_change,1282,0.2193691009359906,1282,0,0.6448864197733862

1,no_later_bundle,108,0.574468085106383,108,0,0.1018518518518518

1,later_without_raw_change,55,0.2925531914893617,55,0,0.309090909090909

1,later_with_raw_change,25,0.1329787234042553,25,0,0.2


The denominator is all landmarks with the specified label. Continuity is the presence of a subsequent original annual filing in a fixed 365-day interval. It is a retrospective reporting-process variable, not a deployment feature or proof of survival.

## Adjacent source horizons

transition,newly_available_n,existing_bundle_accession_switch_n,raw_components_changed_tolerance_landmarks_n,model_features_changed_landmarks_n,same_source_raw_values_changed_n

365_to_730,1301,125,484,483,0

730_to_latest,7,13,10,10,0

90_to_365,2603,136,801,801,0


Source switching among previously available bundles is distinct from newly obtaining a bundle. Identical selected source accessions must not change raw values in this frozen reconstruction.

## Selected B sources after final fit date

block,fit_cutoff,raw_n,refit_raw_denominator,fraction_all_refit_weighted,model_input_changed_landmarks

2016_2017,2016-01-01,6,2024,0.0021648005601243,3

2018_2019,2018-01-01,8,3167,0.0034160148180739,6

2020_2021,2020-01-01,6,4161,0.0019032794868969,2


Use the separately reported same-day category if requiring strict availability before the start of the cutoff date. The table describes the final refit partition, not tuning/validation fits.

## File interface

- `perturbation_modes_all_replicates.parquet/csv`: replicate × block × model × mode × metric, AA/BB/delta in metric units.
- `perturbation_modes_distribution_summary.csv`: each AA/BB/delta distribution, all raw probability-scale metrics (multiply AP by100 for percentage points).
- `independent_four_cell_metrics.csv`, `four_cell_decomposition_unrounded.csv`, `independent_conditional_1000_summary.csv`: independent arithmetic and conditional interval reproduction.
- `version_exposure_by_landmark.parquet`, `version_exposure_summary.csv`: exposure and future continuation with explicit denominators.
- `adjacent_horizon_by_landmark.parquet`, `adjacent_horizon_summary.csv`, `adjacent_horizon_raw_component_changes.parquet`: accession and value changes between nested horizons.
- `raw_component_change_magnitudes.parquet`, `raw_component_magnitude_summary.csv`, `raw_component_sign_categories.csv`: Figure2-ready source values and separate scale/sign summaries.
- `training_B_source_timing_by_landmark.parquet`, `training_B_source_timing_summary.csv`: final-fitting information boundary.
- `design.json`, `manifest.json`, and audit JSONs: source hashes, fixed definitions and validation.

No plot or manuscript file was created or changed.
