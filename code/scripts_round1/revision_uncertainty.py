"""Revision-stage, design-weight refitting and fixed-fit event influence.

All inputs are frozen D: caches. This module never changes the original model,
protocol, cohort, or uncertainty files. Run --prepare, --self-test, --timing,
then --run. --timing runs the first two of the fixed 200 replicates, not a
separate pilot selected after seeing outcomes. --run resumes completed draws.
"""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
             'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '2'
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import time
import traceback

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_vintage_models as vm
import uncertainty_vintage as uv

OUT = ROOT / 'revision_20260922/results/uncertainty'
PREFIX = ROOT / 'results/models_20260921T093517075175Z'
SEED = 20260922
N_REPLICATES = 200
THREADS = 2
MODELS = ('LR', 'LGBM')
SIGN_TOL = 1e-12
LIMITS = [
    'Revision-stage analysis after original test results were known; not original preregistration.',
    'Rao-Wu-Yue rescaled positive weights perturb the noncase SRS stratum only; all certainty clusters and registry outcomes remain fixed.',
    'The full trajectory of every sampled cluster receives the same multiplier in development and test, with the same draw across versions, learners and blocks.',
    'Weighted quantiles, AP, top-budget selection, tree splits and discrete candidate selection are nonsmooth. These 200 empirical replicate distributions do not establish exact 95% confidence coverage.',
    'All observed rows remain with positive rescaled weights. LightGBM min_child_samples and bin construction are not equivalent to physically duplicating/deleting rows. This is a design-weight perturbation diagnostic, not an ordinary iid case bootstrap.',
    'Model seeds and algorithm configuration stay fixed. Variation includes reestimated preprocessing, weighted candidate selection and fitting under the perturbed design weights, not randomness from changing model seeds.',
    'No event superpopulation, registry undercapture, source extraction error, inaccessible-XBRL nonresponse or future macroeconomic uncertainty is represented.',
    'Three chronological blocks are correlated domains, not three independent macroeconomic experiments.',
    'Event-cluster deletion is a fixed-fit influence diagnostic: all that cluster\'s test trajectories are removed, but development and learned models are not refitted.',
    'Sampling clusters reflect shared accessions, not necessarily complete legal corporate groups. No groupwise AP additivity or causal effect attribution is asserted.',
]


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    vm.write_json(path, value)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def source_record(path):
    path = Path(path).resolve()
    vm.require(path.drive.lower() == 'd:', f'D: input required: {path}')
    return {'path': str(path), 'sha256': vm.sha256(path)}


def sources():
    files = {
        'cohort': ROOT / 'datasets/model_cohort.parquet',
        'sampling_frame': ROOT / 'datasets/sampling_frame.parquet',
        'sampling_summary': ROOT / 'results/sampling_frame_summary.json',
        'protocol': ROOT / 'phase2_protocol.json',
        'model_manifest': Path(str(PREFIX) + '_manifest.json'),
        'main_predictions': Path(str(PREFIX) + '_test_predictions.parquet'),
        'frozen_predictions': Path(str(PREFIX) + '_frozen_a_predictions.parquet'),
        'main_metrics': Path(str(PREFIX) + '_metrics.csv'),
        'model_script': ROOT / 'scripts/run_vintage_models.py',
        'conditional_uncertainty_script': ROOT / 'scripts/uncertainty_vintage.py',
    }
    for stem in ('uncertainty_20260921T093555450801Z', 'uncertainty_20260921T093555459899Z'):
        for p in sorted((ROOT / 'results').glob(stem + '*')):
            files[p.name] = p
    return {k: source_record(v) for k, v in files.items()}


def load_context():
    protocol = read(ROOT / 'phase2_protocol.json')
    binding = vm.verify_training_binding(ROOT / 'datasets/model_cohort.parquet',
                                         ROOT / 'phase2_protocol.json', protocol)
    manifest = read(str(PREFIX) + '_manifest.json')
    vm.require(manifest['status'] == 'completed', 'Original run incomplete')
    vm.require(manifest['input_sha256'] == binding['input_sha256'], 'Original cohort differs')
    vm.require(manifest['source_script_sha256'] == vm.sha256(ROOT / 'scripts/run_vintage_models.py'),
               'Original model implementation changed')
    df = vm.validate_cohort(pd.read_parquet(ROOT / 'datasets/model_cohort.parquet'))
    splits = vm.make_splits(df)
    vm.require(all(not s['issues'] for s in splits), 'Original time splits not viable')
    frame = pd.read_parquet(ROOT / 'datasets/sampling_frame.parquet')
    design = uv.SamplingDesign.from_frame(frame)
    sm = read(ROOT / 'results/sampling_frame_summary.json')
    vm.require(vm.sha256(ROOT / 'datasets/sampling_frame.parquet') == sm['frame_sha256'], 'Frame hash mismatch')
    for k in ('noncase_population_clusters', 'noncase_sample_clusters', 'certainty_clusters'):
        vm.require(design.manifest()[k] == sm[k], f'Sampling design mismatch {k}')
    main = uv.normalize_predictions(pd.read_parquet(str(PREFIX) + '_test_predictions.parquet'), design)
    frozen = uv.normalize_predictions(pd.read_parquet(str(PREFIX) + '_frozen_a_predictions.parquet'), design)
    main = main[main.model.isin(MODELS) & main.version.isin(['A', 'B'])].copy()
    frozen = frozen[frozen.model.isin(MODELS)].copy()
    for table in (main, frozen):
        vm.require(set(table.row_id) == set(df.loc[np.concatenate([s['indices']['test'] for s in splits]), 'row_id']),
                   'Prediction/cohort test rows differ')
    noncase_map = {v: i for i, v in enumerate(design.sampled_noncase)}
    nc = df.sampling_stratum.eq('noncase_srs').to_numpy()
    positions = np.full(len(df), -1, dtype=int)
    positions[nc] = [noncase_map[c] for c in df.loc[nc, 'cluster_id']]
    vm.require(not df.loc[nc, 'registry_event_365'].any(), 'Positive noncase stratum unexpected')
    return {'df': df, 'splits': splits, 'design': design, 'main': main,
            'frozen': frozen, 'positions': positions, 'binding': binding}


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = load_context()
    plan_path = OUT / 'design.json'
    if plan_path.exists():
        plan = read(plan_path)
        vm.require(plan['n_replicates'] == N_REPLICATES and plan['seed'] == SEED, 'Plan differs')
        vm.require(plan['sources'] == sources(), 'Frozen source changed after plan')
        return plan
    vm.require(shutil.disk_usage(OUT).free > 5 * 1024 ** 3, 'Less than 5 GiB free on D:')
    plan = {
        'status': 'FROZEN_BEFORE_REVISION_RUN', 'created_utc': now(),
        'route': {'route': 'SCI', 'reason': 'Applied ML evaluation methodology and empirical version sensitivity',
                  'primary_standard': 'Faithful temporal pipeline, paired comparisons, design-aware uncertainty and traceable scope',
                  'do_not_use': 'Causal or event-superpopulation interpretation unsupported by this design',
                  'next_workflow': 'sci-full-workflow'},
        'n_replicates': N_REPLICATES, 'seed': SEED, 'model_seed': vm.SEED,
        'threads': THREADS, 'n_parallel_replicates': 1,
        'resource_budget': {'memory_estimate_gib': 2, 'disk_budget_gib': 2,
                            'free_d_bytes_at_prepare': shutil.disk_usage(OUT).free,
                            'full_fits_per_replicate': 12, 'candidate_fits_per_replicate': 48,
                            'first_timing_replicates': [0, 1], 'fixed_total_fits': 12000,
                            'time_estimate': 'Measure first two complete draws, then report before remaining draws'},
        'weight_design': ctx['design'].manifest(), 'sources': sources(),
        'reestimated_in_every_replicate': ['weighted 1%/99% clipping', 'weighted median imputation',
            'weighted mean/SD for LR', 'four-candidate validation AP selection with original exact-tie rule',
            'final weighted model fit', 'weighted evaluation and 5% weighted-mass cutoff'],
        'unchanged': ['cohort and A/B missing masks', 'time splits and 455-day maturity rule',
                      'candidate grid', 'certainty clusters and labels', 'model seeds'],
        'primary_display': 'All 200 paired point differences, empirical median, 5/95 and 2.5/97.5 percentiles, positive/negative/tie fractions; quantiles are not labeled confidence intervals',
        'validity_reporting': 'All candidate failures and invalid paired cells retained; no replacement draws',
        'event_influence': 'Union of test-positive sampling clusters; delete each cluster globally from all test rows with models fixed; primary block summary restricts to clusters positive in that block',
        'score_propagation': 'Refitted A/B and frozen-A input replacement; signed/absolute probability and weighted midrank changes by raw input changed/unchanged, plus label strata',
        'change_tolerance': 'abs(A-B)>1e-12*max(1,abs(A),abs(B)); identical initial missing mask',
        'probability_zero_tolerance': 1e-12, 'rank': 'fraction of weighted test mass above score plus half mass tied at score; smaller is higher risk',
        'old_conditional_intervals': 'Preserved unchanged in original results; source hashes recorded, no overwrite',
        'three_rejection_hypotheses': [
            'Observed refit differences change sign frequently under design-weight perturbation, indicating insufficient support for a directional generalization.',
            'Deleting one test-positive sampling cluster changes the paired difference sign, indicating event composition leverage.',
            'Prediction changes on unchanged inputs are large under refitting but absent under frozen-A scoring, indicating fitted-pipeline propagation rather than direct feature changes alone.'
        ], 'primary_risk': 'Nonregular candidate selection with sparse development events',
        'limitations': LIMITS,
    }
    save(plan_path, plan)
    multipliers = uv.rescaled_multipliers(len(ctx['design'].sampled_noncase),
                                        ctx['design'].population_noncase, N_REPLICATES, SEED)
    np.save(OUT / 'replicate_multipliers.npy', multipliers, allow_pickle=False)
    pd.DataFrame({'multiplier_column': range(multipliers.shape[1]),
                  'cluster_id': ctx['design'].sampled_noncase}).to_csv(OUT / 'replicate_cluster_order.csv', index=False)
    save(OUT / 'replicate_weights_manifest.json', {
        'created_utc': now(), 'n_replicates': N_REPLICATES, 'seed': SEED,
        'shape': list(multipliers.shape), 'min_multiplier': multipliers.min(),
        'max_multiplier': multipliers.max(), 'row_sums_min': multipliers.sum(1).min(),
        'row_sums_max': multipliers.sum(1).max(), 'all_1000_noncase_clusters_including_zero_domain': True,
        'files': [source_record(OUT / 'replicate_multipliers.npy'), source_record(OUT / 'replicate_cluster_order.csv')],
    })
    return plan


def row_weights(ctx, multipliers):
    w = ctx['df'].sample_weight.to_numpy(copy=True)
    active = ctx['positions'] >= 0
    w[active] *= multipliers[ctx['positions'][active]]
    vm.require(np.all(w > 0), 'Nonpositive Rao-Wu weights')
    vm.require(np.all(w[~active] == 1), 'Certainty weights changed')
    return w


def fit_replicate(ctx, replicate, multipliers):
    start = time.perf_counter()
    df = ctx['df']; w = row_weights(ctx, multipliers)
    y = df.registry_event_365.to_numpy()
    records = []; predictions = []; states = []; failures = []
    for split in ctx['splits']:
        block = split['block']
        tr, va, re, te = [split['indices'][k] for k in ('tuning_train', 'validation', 'refit', 'test')]
        for version in ('A', 'B'):
            raw = df[[version + '_' + f for f in vm.FEATURES] + vm.COMMON_FEATURES].to_numpy(float)
            for name in MODELS:
                state = {'replicate': replicate, 'block': block, 'version': version, 'model': name,
                         'candidates': [], 'status': 'pending'}
                try:
                    prep = vm.WeightedPreprocessor(scale=name == 'LR').fit(raw[tr], w[tr])
                    state['tuning_preprocessing'] = prep.manifest()
                    xtr, xva = prep.transform(raw[tr]), prep.transform(raw[va])
                    candidates = []
                    for num, pars in enumerate(vm.model_grid(name)):
                        cr = {'candidate': num, 'parameters': pars}
                        try:
                            model, messages, converged = vm.fit_model(name, pars, xtr, y[tr], w[tr], THREADS)
                            vm.require(converged, 'Candidate convergence warning')
                            pred = model.predict_proba(xva)[:, 1]
                            # Preserve original floating arithmetic as well as
                            # metric definition: exact AP ties select first.
                            measures, _ = vm.evaluate(y[va], pred, w[va], calibration=False)
                            vm.require(np.isfinite(measures['average_precision']), 'Invalid validation AP')
                            cr.update(status='ok', warnings=messages, validation_metrics=measures)
                            candidates.append((measures['average_precision'], num, pars))
                        except Exception as exc:
                            cr.update(status='failed', error=repr(exc))
                        state['candidates'].append(cr)
                    vm.require(len(candidates) == len(vm.model_grid(name)), 'Incomplete original candidate grid')
                    best = max(candidates, key=lambda z: (z[0], -z[1]))
                    prep = vm.WeightedPreprocessor(scale=name == 'LR').fit(raw[re], w[re])
                    model, messages, converged = vm.fit_model(name, best[2], prep.transform(raw[re]), y[re], w[re], THREADS)
                    vm.require(converged, 'Final convergence warning')
                    pred = model.predict_proba(prep.transform(raw[te]))[:, 1]
                    measures = uv.MetricCache(y[te], pred).evaluate(w[te])
                    state.update(status='ok', selected_candidate=best[1], selected_parameters=best[2],
                                 selected_validation_ap=best[0], final_warnings=messages,
                                 final_preprocessing=prep.manifest())
                    records.append({'replicate': replicate, 'block': block, 'model': name,
                                    'version': version, 'selected_candidate': best[1], **measures})
                    p = df.loc[te, ['row_id', 'cluster_id', 'cik', 'registry_event_365', 'sample_weight']].copy()
                    p['replicate_weight'] = w[te]; p['prediction'] = pred
                    p['replicate'] = replicate; p['block'] = block; p['model'] = name; p['version'] = version
                    predictions.append(p)
                except Exception as exc:
                    state.update(status='failed', error=repr(exc), traceback=traceback.format_exc())
                    failures.append({k: state.get(k) for k in ('replicate', 'block', 'model', 'version', 'error')})
                states.append(state)
    return {'metrics': pd.DataFrame(records),
            'predictions': pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame(),
            'state': {'replicate': replicate, 'elapsed_seconds': time.perf_counter() - start,
                      'status': 'complete' if not failures else 'complete_with_failed_cells',
                      'failures': failures, 'cells': states}}


def write_replicate(result, folder):
    folder.mkdir(parents=True, exist_ok=True)
    result['metrics'].to_csv(folder / 'metrics.csv', index=False)
    result['predictions'].to_parquet(folder / 'predictions.parquet', index=False)
    save(folder / 'pipeline_state.json', result['state'])
    save(folder / 'completed.json', {'created_utc': now(), 'status': result['state']['status'],
        'script_sha256': vm.sha256(__file__), 'design_sha256': vm.sha256(OUT / 'design.json'),
        'files': [source_record(folder / f) for f in ('metrics.csv', 'predictions.parquet', 'pipeline_state.json')]})


def check_reproduction(ctx):
    folder = OUT / 'point_reproduction'
    if (folder / 'audit.json').exists():
        audit = read(folder / 'audit.json')
        vm.require(audit['status'] == 'PASS', 'Previous reproduction failed')
        return audit
    result = fit_replicate(ctx, -1, np.ones(len(ctx['design'].sampled_noncase)))
    vm.require(not result['state']['failures'], 'Point reproduction has fit failures')
    old = ctx['main']; new = result['predictions']
    merged = old.merge(new, on=['row_id', 'block', 'model', 'version'], suffixes=('_old', '_new'), validate='one_to_one')
    vm.require(len(merged) == len(old) == len(new), 'Reproduction rows differ')
    max_error = float(np.abs(merged.pred - merged.prediction_new).max())
    vm.require(max_error <= 1e-7, f'Point reproduction scores differ: {max_error}')
    point = point_metrics(ctx['main'], 'refit_vintages')
    pairs = result['metrics'].merge(point, on=['block', 'model', 'version'], suffixes=('_new', '_old'))
    errors = {k: float(np.abs(pairs[k + '_new'] - pairs[k + '_old']).max()) for k in uv.METRICS}
    vm.require(max(errors.values()) <= 1e-8, f'Reproduction metrics differ: {errors}')
    old_metrics = pd.read_csv(str(PREFIX) + '_metrics.csv')
    chosen = result['metrics'].merge(old_metrics[['block', 'model', 'version', 'selected_candidate']],
                                    on=['block', 'model', 'version'], suffixes=('_new', '_old'))
    vm.require(chosen.selected_candidate_new.eq(chosen.selected_candidate_old).all(), 'Point selected candidate differs')
    write_replicate(result, folder)
    audit = {'status': 'PASS', 'checked_utc': now(), 'model_threads_old': 4, 'model_threads_new': 2,
             'maximum_probability_difference': max_error, 'maximum_metric_differences': errors,
             'all_12_selected_candidates_identical': True, 'elapsed_seconds': result['state']['elapsed_seconds']}
    save(folder / 'audit.json', audit)
    return audit


def point_metrics(table, mode):
    rows = []
    for (block, name, ver), sub in table.groupby(['block', 'model', 'version'], sort=True):
        m = uv.MetricCache(sub.label, sub.pred).evaluate(sub.sample_weight)
        rows.append({'analysis_mode': mode, 'block': block, 'model': name, 'version': ver, **m})
    return pd.DataFrame(rows)


def paired_metric_table(wide, id_columns):
    rows = []
    for keys, cell in wide.groupby(id_columns, sort=True):
        if not isinstance(keys, tuple): keys = (keys,)
        base = dict(zip(id_columns, keys))
        indexed = cell.set_index('version')
        for metric in uv.METRICS:
            a = indexed.at['A', metric] if 'A' in indexed.index else np.nan
            b = indexed.at['B', metric] if 'B' in indexed.index else np.nan
            rows.append({**base, 'metric': metric, 'A': a, 'B': b,
                         'difference_B_minus_A': b - a, 'valid': bool(np.isfinite(a) and np.isfinite(b))})
    return pd.DataFrame(rows)


def weighted_midrank(p, w):
    p = np.asarray(p); w = np.asarray(w)
    _, group = np.unique(-p, return_inverse=True)
    mass = np.bincount(group, weights=w)
    return (np.cumsum(mass) - mass / 2)[group] / w.sum()


def score_propagation(ctx):
    df = ctx['df'].set_index('row_id'); rows = []; summaries = []
    for mode, table in [('refit_vintages', ctx['main']), ('frozen_A_inputs', ctx['frozen'])]:
        for (block, name), cell in table.groupby(['block', 'model'], sort=True):
            a = cell[cell.version.eq('A')].set_index('row_id').sort_index()
            b = cell[cell.version.eq('B')].set_index('row_id').sort_index()
            vm.require(a.index.equals(b.index), 'Score pair row mismatch')
            features_a = df.loc[a.index, ['A_' + f for f in vm.FEATURES]].to_numpy(float)
            features_b = df.loc[a.index, ['B_' + f for f in vm.FEATURES]].to_numpy(float)
            finite = np.isfinite(features_a)
            vm.require(np.array_equal(finite, np.isfinite(features_b)), 'Changed missing masks')
            threshold = 1e-12 * np.maximum(1, np.maximum(np.abs(features_a), np.abs(features_b)))
            changed_features = finite & (np.abs(features_a - features_b) > threshold)
            changed = changed_features.any(axis=1)
            p = a[['cluster_id', 'cik', 'label', 'sample_weight']].copy().reset_index()
            p['analysis_mode'] = mode; p['block'] = block; p['model'] = name
            p['input_changed'] = changed; p['changed_input_count'] = changed_features.sum(1)
            p['pred_A'] = a.pred.to_numpy(); p['pred_B'] = b.pred.to_numpy()
            p['score_difference'] = p.pred_B - p.pred_A
            p['absolute_score_difference'] = np.abs(p.score_difference)
            p['score_changed'] = p.absolute_score_difference.gt(1e-12)
            p['weighted_midrank_A'] = weighted_midrank(p.pred_A, p.sample_weight)
            p['weighted_midrank_B'] = weighted_midrank(p.pred_B, p.sample_weight)
            p['weighted_midrank_difference'] = p.weighted_midrank_B - p.weighted_midrank_A
            p['absolute_weighted_midrank_difference'] = np.abs(p.weighted_midrank_difference)
            p['raw_rank_A'] = p.pred_A.rank(method='average', ascending=False)
            p['raw_rank_B'] = p.pred_B.rank(method='average', ascending=False)
            p['raw_rank_difference'] = p.raw_rank_B - p.raw_rank_A
            if mode == 'frozen_A_inputs':
                vm.require(not p.loc[~p.input_changed, 'score_changed'].any(), 'Frozen-A unchanged inputs yield changed scores')
            rows.append(p)
            for group_name, mask in [('all', np.ones(len(p), bool)), ('inputs_changed', changed), ('inputs_unchanged', ~changed)]:
                for label_group, label_mask in [('all', np.ones(len(p), bool)), ('positive', p.label.eq(1)), ('negative', p.label.eq(0))]:
                    sub = p.loc[mask & label_mask]; weights = sub.sample_weight.to_numpy()
                    record = {'analysis_mode': mode, 'block': block, 'model': name, 'input_group': group_name,
                              'label_group': label_group, 'raw_rows': len(sub), 'raw_positive_windows': int(sub.label.sum()),
                              'distinct_ciks': sub.cik.nunique(), 'distinct_clusters': sub.cluster_id.nunique(),
                              'weighted_mass': weights.sum(), 'weighted_mass_denominator': p.sample_weight.sum()}
                    if len(sub):
                        record['weighted_score_changed_fraction'] = np.average(sub.score_changed, weights=weights)
                        record['weighted_input_changed_fraction'] = np.average(sub.input_changed, weights=weights)
                        record['weighted_rank_changed_fraction'] = np.average(sub.absolute_weighted_midrank_difference > 1e-12, weights=weights)
                        for val in ['score_difference', 'absolute_score_difference', 'weighted_midrank_difference',
                                    'absolute_weighted_midrank_difference', 'raw_rank_difference']:
                            record[val + '_weighted_mean'] = np.average(sub[val], weights=weights)
                            for q in (0.05, 0.25, 0.5, 0.75, 0.95):
                                record[f'{val}_weighted_q{int(q * 100):02d}'] = vm.weighted_quantile(sub[val], weights, q)
                    summaries.append(record)
    pd.concat(rows, ignore_index=True).to_parquet(OUT / 'score_rank_row_diagnostics.parquet', index=False)
    pd.DataFrame(summaries).to_csv(OUT / 'score_rank_group_summary.csv', index=False)


def deletion_diagnostics(ctx):
    candidates = sorted(ctx['main'].loc[ctx['main'].label.eq(1), 'cluster_id'].unique())
    pd.DataFrame({'cluster_id': candidates}).to_csv(OUT / 'test_positive_cluster_deletion_set.csv', index=False)
    output = []; summaries = []
    for mode, table in [('refit_vintages', ctx['main']), ('frozen_A_inputs', ctx['frozen'])]:
        for (block, name), cell in table.groupby(['block', 'model'], sort=True):
            a = cell[cell.version.eq('A')].set_index('row_id').sort_index()
            b = cell[cell.version.eq('B')].set_index('row_id').sort_index()
            vm.require(a.index.equals(b.index), 'Delete pair row mismatch')
            y = a.label.to_numpy(); w = a.sample_weight.to_numpy()
            cache_a = uv.MetricCache(y, a.pred); cache_b = uv.MetricCache(y, b.pred)
            base_a = cache_a.evaluate(w); base_b = cache_b.evaluate(w)
            for cluster in candidates:
                removed = a.cluster_id.eq(cluster).to_numpy()
                rw = w.copy(); rw[removed] = 0
                ma = cache_a.evaluate(rw); mb = cache_b.evaluate(rw)
                common = {'analysis_mode': mode, 'block': block, 'model': name, 'deleted_cluster': cluster,
                          'removed_test_rows': int(removed.sum()), 'removed_positive_windows': int(y[removed].sum()),
                          'removed_ciks': '|'.join(sorted(a.loc[removed, 'cik'].unique())),
                          'remaining_test_rows': int((~removed).sum()), 'remaining_positive_windows': int(y[~removed].sum()),
                          'refit_performed': False}
                for metric in uv.METRICS:
                    delta = mb[metric] - ma[metric]; original = base_b[metric] - base_a[metric]
                    output.append({**common, 'metric': metric, 'A_after_delete': ma[metric], 'B_after_delete': mb[metric],
                                   'baseline_difference_B_minus_A': original, 'difference_B_minus_A': delta,
                                   'change_from_baseline_difference': delta - original,
                                   'strict_sign_reversal': bool((delta > SIGN_TOL and original < -SIGN_TOL) or (delta < -SIGN_TOL and original > SIGN_TOL)),
                                   'post_delete_tie': bool(abs(delta) <= SIGN_TOL), 'valid': bool(np.isfinite(delta))})
    allrows = pd.DataFrame(output)
    allrows.to_csv(OUT / 'event_cluster_leave_one_out.csv', index=False)
    relevant = allrows[allrows.removed_positive_windows.gt(0)]
    for keys, cell in relevant.groupby(['analysis_mode', 'block', 'model', 'metric']):
        worst = cell.loc[cell.change_from_baseline_difference.abs().idxmax()]
        summaries.append(dict(zip(['analysis_mode', 'block', 'model', 'metric'], keys)) | {
            'baseline_difference_B_minus_A': cell.baseline_difference_B_minus_A.iloc[0],
            'positive_bearing_clusters_deleted': len(cell), 'valid_deletions': int(cell.valid.sum()),
            'strict_sign_reversals': int(cell.strict_sign_reversal.sum()), 'post_delete_ties': int(cell.post_delete_tie.sum()),
            'minimum_difference': cell.difference_B_minus_A.min(), 'maximum_difference': cell.difference_B_minus_A.max(),
            'largest_absolute_influence_cluster': worst.deleted_cluster,
            'largest_absolute_influence_ciks': worst.removed_ciks,
            'largest_signed_influence': worst.change_from_baseline_difference,
            'difference_after_most_influential_deletion': worst.difference_B_minus_A})
    pd.DataFrame(summaries).to_csv(OUT / 'event_cluster_leave_one_out_summary.csv', index=False)


def self_test():
    # Reuse original independently enumerated finite-population identities.
    inherited = uv.self_test()
    p = np.array([0.8, 0.8, 0.4]); w = np.array([1., 3., 2.])
    ranks = weighted_midrank(p, w)
    assert np.allclose(ranks, [1/3, 1/3, 5/6])
    order = np.array([2, 0, 1])
    assert np.allclose(weighted_midrank(p[order], w[order]), ranks[order])
    cluster = np.array(['c', 'c', 'n', 'n', 'z'])
    base_w = np.array([1., 1., 4., 4., 4.]); factors = {'c': 1., 'n': .25, 'z': 2.}
    rw = base_w * np.array([factors[k] for k in cluster])
    assert rw[0] == rw[1] == 1 and rw[2] == rw[3] == 1
    y = np.array([1, 0, 0, 1, 0]); scores = np.array([.9, .4, .5, .2, .1])
    keep = cluster != 'c'; delete_w = base_w.copy(); delete_w[~keep] = 0
    ma = uv.MetricCache(y, scores).evaluate(delete_w)
    mb = uv.MetricCache(y[keep], scores[keep]).evaluate(base_w[keep])
    for metric in uv.METRICS: assert np.isclose(ma[metric], mb[metric])
    prep1 = vm.WeightedPreprocessor(scale=True).fit(np.array([[0.], [1.], [9.]]), np.array([1., 1., 1.]))
    prep2 = vm.WeightedPreprocessor(scale=True).fit(np.array([[0.], [1.], [9.]]), np.array([1., 1., 20.]))
    assert prep1.median_[0] == 1 and prep2.median_[0] == 9
    assert not np.array_equal(prep1.mean_, prep2.mean_)
    save(OUT / 'self_test.json', {'status': 'PASS', 'created_utc': now(), 'data_kind': 'SYNTHETIC_ONLY',
        'inherited_test_count': len(inherited['tests']), 'additional_tests': [
            'Weighted midrank exact ties and row-order invariance', 'Same cluster trajectory multiplier and fixed certainty',
            'Whole-cluster zero weighting equals physical test deletion for all four metrics',
            'Weighted preprocessing is reestimated when replicate weights change'],
        'script_sha256': vm.sha256(__file__), 'inherited_known_population': inherited['known_population']})


def run(timing_only=False):
    plan = prepare(); ctx = load_context()
    vm.require((OUT / 'self_test.json').exists() and read(OUT / 'self_test.json')['status'] == 'PASS', 'Run self-test first')
    lock = OUT / 'running.lock'
    with lock.open('x', encoding='utf-8') as f: f.write(json.dumps({'pid': os.getpid(), 'started_utc': now()}))
    try:
        with threadpool_limits(limits=THREADS):
            check_reproduction(ctx)
            mult = np.load(OUT / 'replicate_multipliers.npy', allow_pickle=False)
            vm.require(mult.shape == (N_REPLICATES, len(ctx['design'].sampled_noncase)), 'Multiplier shape mismatch')
            wm = read(OUT / 'replicate_weights_manifest.json')
            for rec in wm['files']: vm.require(vm.sha256(rec['path']) == rec['sha256'], 'Multiplier source changed')
            times = []
            for rep in range(2 if timing_only else N_REPLICATES):
                folder = OUT / 'replicates' / f'replicate_{rep:03d}'
                if (folder / 'completed.json').exists():
                    done = read(folder / 'completed.json')
                    vm.require(done['script_sha256'] == vm.sha256(__file__), 'Script differs across replicate run')
                    vm.require(done['design_sha256'] == vm.sha256(OUT / 'design.json'), 'Design differs across run')
                    for rec in done['files']: vm.require(vm.sha256(rec['path']) == rec['sha256'], 'Completed replicate changed')
                    state = read(folder / 'pipeline_state.json')
                else:
                    result = fit_replicate(ctx, rep, mult[rep])
                    write_replicate(result, folder); state = result['state']
                times.append(state['elapsed_seconds'])
                save(OUT / 'progress.json', {'updated_utc': now(), 'completed_through': rep,
                     'fixed_n_replicates': N_REPLICATES, 'last_elapsed_seconds': times[-1],
                     'mean_elapsed_seconds': np.mean(times), 'last_status': state['status'],
                     'script_sha256': vm.sha256(__file__)})
                print(json.dumps({'replicate': rep, 'seconds': round(times[-1], 3), 'status': state['status']}), flush=True)
            if timing_only:
                save(OUT / 'resource_timing.json', {'created_utc': now(), 'first_two_seconds': times,
                     'estimated_200_seconds': float(np.mean(times) * N_REPLICATES), 'threads': THREADS,
                     'planned_n_replicates_unchanged': N_REPLICATES, 'first_two_retained_in_formal_run': True})
            else:
                vm.require(plan['sources'] == sources(), 'Frozen sources changed during run')
                summarize(ctx)
    finally:
        lock.unlink(missing_ok=True)


def summarize(ctx=None):
    ctx = ctx or load_context()
    vm.require(read(OUT / 'design.json')['sources'] == sources(), 'Sources changed')
    paths = [OUT / 'replicates' / f'replicate_{r:03d}' for r in range(N_REPLICATES)]
    vm.require(all((p / 'completed.json').exists() for p in paths), 'Not all 200 fixed replicates complete')
    metrics = pd.concat([pd.read_csv(p / 'metrics.csv') for p in paths], ignore_index=True)
    metrics.to_csv(OUT / 'full_pipeline_replicate_metrics.csv', index=False)
    pairs = paired_metric_table(metrics, ['replicate', 'block', 'model'])
    pairs.to_csv(OUT / 'full_pipeline_paired_replicates.csv', index=False)
    original = paired_metric_table(point_metrics(ctx['main'], 'refit_vintages'), ['block', 'model'])
    summary = []
    for keys, cell in pairs.groupby(['block', 'model', 'metric'], sort=True):
        vals = cell.difference_B_minus_A.to_numpy(); good = np.isfinite(vals); v = vals[good]
        point = original[(original.block == keys[0]) & (original.model == keys[1]) & (original.metric == keys[2])].iloc[0]
        record = dict(zip(['block', 'model', 'metric'], keys)) | {
            'original_A': point.A, 'original_B': point.B, 'original_difference_B_minus_A': point.difference_B_minus_A,
            'planned_replicates': N_REPLICATES, 'valid_replicates': int(good.sum()),
            'invalid_or_missing_replicates': N_REPLICATES - int(good.sum()),
            'mean': float(np.mean(v)) if len(v) else np.nan, 'sd': float(np.std(v, ddof=1)) if len(v) > 1 else np.nan,
            'positive_fraction_valid': float(np.mean(v > SIGN_TOL)) if len(v) else np.nan,
            'negative_fraction_valid': float(np.mean(v < -SIGN_TOL)) if len(v) else np.nan,
            'tie_fraction_valid': float(np.mean(np.abs(v) <= SIGN_TOL)) if len(v) else np.nan,
            'distribution_label': 'Empirical full-pipeline design-weight perturbation; quantiles are not confidence limits'}
        for q in (.025, .05, .25, .5, .75, .95, .975):
            record['q' + str(q * 100).replace('.', '_')] = float(np.quantile(v, q)) if len(v) else np.nan
        summary.append(record)
    pd.DataFrame(summary).to_csv(OUT / 'full_pipeline_distribution_summary.csv', index=False)
    freq = metrics.groupby(['block', 'model', 'version', 'selected_candidate']).size().reset_index(name='replicates')
    freq['fraction_of_fixed_200'] = freq.replicates / N_REPLICATES
    freq.to_csv(OUT / 'candidate_selection_frequency.csv', index=False)
    switches = metrics.pivot(index=['replicate', 'block', 'model'], columns='version', values='selected_candidate').reset_index()
    switches['AB_candidate_differs'] = switches.A.ne(switches.B)
    switches.to_csv(OUT / 'candidate_pair_selections.csv', index=False)
    fail = []
    for p in paths:
        state = read(p / 'pipeline_state.json'); fail.extend(state['failures'])
    save(OUT / 'fit_failure_audit.json', {'n_replicates': N_REPLICATES, 'failed_cells': len(fail), 'failures': fail})
    score_propagation(ctx); deletion_diagnostics(ctx)
    findings(pd.DataFrame(summary))
    output_files = [p for p in OUT.rglob('*') if p.is_file() and p.name not in ('manifest.json', 'running.lock')]
    manifest = {'status': 'COMPLETE' if not fail else 'COMPLETE_WITH_FAILED_CELLS', 'finished_utc': now(),
        'n_replicates': N_REPLICATES, 'threads': THREADS, 'seed': SEED, 'script': source_record(__file__),
        'sources': sources(), 'original_sources_unchanged': True, 'design': source_record(OUT / 'design.json'),
        'versions': {p: importlib.metadata.version(p) for p in ['numpy', 'pandas', 'scikit-learn', 'lightgbm', 'threadpoolctl']},
        'outputs': [source_record(p) for p in sorted(output_files)], 'limitations': LIMITS}
    save(OUT / 'manifest.json', manifest)


def findings(summary):
    deletion = pd.read_csv(OUT / 'event_cluster_leave_one_out_summary.csv')
    groups = pd.read_csv(OUT / 'score_rank_group_summary.csv')
    lines = ['# Revision uncertainty and event influence findings', '',
        'These are revision-stage analyses on the frozen original cohort. No original conditional interval, model result, protocol or data file was overwritten.', '',
        '## Full-pipeline design-weight perturbation', '',
        'Exactly 200 prespecified paired replicates reestimate preprocessing, all four candidate fits, validation AP selection and final LR/LGBM parameters. All 1,000 sampled noncase clusters, including zero-domain clusters, enter each draw. Certainty clusters stay fixed. The same multiplier follows the complete cluster trajectory in every period, learner and version.', '',
        'The table reports percentage points for AP. The empirical 5th/95th percentiles describe these perturbations; they are not asserted to be confidence limits. Direction fractions are descriptive frequencies, not p-values or posterior probabilities.', '',
        '| Block | Learner | Original delta AP (pp) | Replicate median (pp) | 5th / 95th (pp) | Positive / negative / tie | Valid |',
        '|---|---|---:|---:|---:|---:|---:|']
    for _, r in summary[summary.metric.eq('average_precision')].iterrows():
        lines.append(f'| {r.block} | {r.model} | {100*r.original_difference_B_minus_A:.3f} | {100*r["q50_0"]:.3f} | {100*r["q5_0"]:.3f} / {100*r["q95_0"]:.3f} | {r.positive_fraction_valid:.3f} / {r.negative_fraction_valid:.3f} / {r.tie_fraction_valid:.3f} | {r.valid_replicates}/200 |')
    lines += ['', '## Fixed-fit test-event influence', '',
        'The primary summary deletes each sampling cluster with a positive test window in the corresponding block, removing all of that cluster\'s test trajectories and recomputing the weighted rank metrics. Other blocks also have deletion records for that cluster, including explicit zero-contribution deletions. Learned models and development data are unchanged. No full-pipeline event-delete fit was performed.', '',
        '| Block | Learner | Positive clusters | AP sign reversals | AP delta range (pp) | Largest AP influence cluster | Recall sign reversals |',
        '|---|---|---:|---:|---:|---|---:|']
    d = deletion[deletion.analysis_mode.eq('refit_vintages')]
    for _, r in d[d.metric.eq('average_precision')].iterrows():
        recall = d[(d.block == r.block) & (d.model == r.model) & d.metric.eq('retrospective_recall_at_5percent')].iloc[0]
        lines.append(f'| {r.block} | {r.model} | {r.positive_bearing_clusters_deleted} | {r.strict_sign_reversals} | {100*r.minimum_difference:.3f} / {100*r.maximum_difference:.3f} | {r.largest_absolute_influence_cluster} | {recall.strict_sign_reversals} |')
    lines += ['', '## Score and rank propagation', '',
        'Group summaries use the original design weights and distinguish raw row counts from weighted mass. Signed probability differences use B minus A; negative weighted-midrank differences mean movement toward the high-risk end. No subgroup AP summation or additive decomposition is calculated.', '',
        '| Block | Learner | Unchanged-input weighted share with changed refit score | Changed-input weighted share with unchanged frozen-A score |',
        '|---|---|---:|---:|']
    for (block, model), _ in groups.groupby(['block', 'model']):
        x = groups[(groups.block == block) & (groups.model == model) & groups.label_group.eq('all')]
        r = x[x.analysis_mode.eq('refit_vintages') & x.input_group.eq('inputs_unchanged')].iloc[0]
        f = x[x.analysis_mode.eq('frozen_A_inputs') & x.input_group.eq('inputs_changed')].iloc[0]
        lines.append(f'| {block} | {model} | {100*r.weighted_score_changed_fraction:.2f}% | {100*(1-f.weighted_score_changed_fraction):.2f}% |')
    lines += ['', '## Interpretation boundaries', ''] + ['- ' + s for s in LIMITS]
    lines += ['', '## Files', '',
        '- `design.json`: frozen design, resource budget and original source hashes.',
        '- `replicate_multipliers.npy` and `replicate_cluster_order.csv`: exact paired survey-weight draws.',
        '- `replicates/replicate_000` through `replicate_199`: predictions, metrics, all candidate outcomes and learned preprocessing.',
        '- `full_pipeline_paired_replicates.csv` and `full_pipeline_distribution_summary.csv`: all four metrics and distribution summaries.',
        '- `candidate_selection_frequency.csv` and `candidate_pair_selections.csv`: selection instability.',
        '- `event_cluster_leave_one_out.csv` and its summary: all deletion experiments and extreme clusters.',
        '- `score_rank_row_diagnostics.parquet` and `score_rank_group_summary.csv`: traceable score and rank propagation.',
        '- `manifest.json`: hashes, run versions and preservation audit.', '']
    (OUT / 'findings.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'self-test', 'timing', 'run', 'summarize', 'descriptive'])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == 'prepare': prepare(); print(OUT / 'design.json')
    elif args.mode == 'self-test': self_test(); print('Synthetic tests PASS')
    elif args.mode == 'timing': run(timing_only=True)
    elif args.mode == 'run': run()
    elif args.mode == 'summarize': summarize()
    else:
        prepare(); ctx = load_context(); score_propagation(ctx); deletion_diagnostics(ctx)
        print('Fixed-prediction event and score diagnostics complete')


if __name__ == '__main__':
    main()
