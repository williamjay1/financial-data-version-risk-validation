"""Build audited publication figures from a completed, frozen vintage analysis.

No model fitting, imputation, or inferred completeness.  Formal execution requires
explicit input paths, an open protocol gate, and FINAL_COHORT_FROZEN.  Without
--run this module validates all inputs and prints a preflight summary only.
--self-test checks pure numerical helpers and never renders a figure.

All generated artifacts are restricted to results/figures and results/descriptive_*.
The current SEC API reconstructs accession-specific records; these figures must
not be described as comparisons of authenticated historical API snapshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'
FEATURES = [
    'log_assets', 'liabilities_to_assets', 'equity_to_assets', 'cash_to_assets',
    'net_income_to_assets', 'revenue_to_assets', 'operating_income_to_assets',
    'operating_cash_to_assets', 'retained_earnings_to_assets',
    'working_capital_to_assets',
]
LABELS = [
    'Log assets', 'Liabilities / assets', 'Equity / assets', 'Cash / assets',
    'Net income / assets', 'Revenue / assets', 'Operating income / assets',
    'Operating cash flow / assets', 'Retained earnings / assets',
    'Working capital / assets',
]
RAW_FEATURES = [
    'assets', 'liabilities', 'equity', 'cash', 'current_assets',
    'current_liabilities', 'net_income', 'revenue', 'operating_income',
    'operating_cash', 'retained_earnings',
]
BLOCKS = ['2016_2017', '2018_2019', '2020_2021']
MODELS = ['LR', 'LGBM']
CHANGE_TOLERANCE = 1e-12
CI_METHOD = 'basic_centered_Rao_Wu_Yue_SRS_FPC'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1 << 20), b''):
            digest.update(part)
    return digest.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(clean_json(value), indent=2,
                                    ensure_ascii=False, allow_nan=False), encoding='utf-8')


def changed(a, b):
    """Finite paired numerical changes; initial missing values never enter numerator."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    scale = np.maximum(1., np.maximum(np.abs(a), np.abs(b)))
    return np.isfinite(a) & np.isfinite(b) & (np.abs(a - b) > CHANGE_TOLERANCE * scale)


def same_numbers(a, b, tolerance=1e-10):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return np.all(np.isclose(a, b, rtol=tolerance, atol=tolerance, equal_nan=True))


def annual_descriptives(cohort):
    x = cohort.assign(year=pd.to_datetime(cohort.decision_date).dt.year)
    records = []
    for year in range(2010, 2022):
        q = x.loc[x.year.eq(year)]
        w = q.sample_weight.to_numpy(float)
        positive = q.registry_event_365.eq(1).to_numpy()
        records.append({
            'year': year, 'raw_landmarks': len(q), 'raw_distinct_ciks': q.cik.nunique(),
            'raw_sampling_clusters': q.cluster_id.nunique(),
            'raw_positive_filing_windows': int(positive.sum()),
            'raw_distinct_positive_ciks': q.loc[positive, 'cik'].nunique(),
            'raw_distinct_positive_sampling_clusters': q.loc[positive, 'cluster_id'].nunique(),
            'weighted_landmarks': w.sum(), 'weighted_positive_filing_windows': w[positive].sum(),
            'weighted_event_prevalence': w[positive].sum() / w.sum() if w.sum() else np.nan,
            'landmark_kish_weight_diagnostic': w.sum() ** 2 / np.square(w).sum() if len(w) else np.nan,
        })
    return pd.DataFrame(records)


def feature_descriptives(cohort, include_c=False):
    records = []
    w = cohort.sample_weight.to_numpy(float)
    for feature, label in zip(FEATURES, LABELS):
        a = cohort['A_' + feature].to_numpy(float)
        observed = np.isfinite(a)
        for version in ['B'] + (['C'] if include_c else []):
            b = cohort[version + '_' + feature].to_numpy(float)
            require(np.array_equal(observed, np.isfinite(b)),
                    f'A/{version} missingness mismatch: {feature}; do not remove rows to repair it')
            change = changed(a, b)
            denominator = w[observed].sum()
            records.append({
                'feature': feature, 'label': label, 'comparison': version + '_minus_A',
                'raw_cohort_landmarks': len(cohort), 'weighted_cohort_landmarks': w.sum(),
                'raw_A_observed': int(observed.sum()), 'weighted_A_observed': denominator,
                'raw_A_missing': int((~observed).sum()), 'weighted_A_missing': w[~observed].sum(),
                'raw_changed': int(change.sum()), 'weighted_changed': w[change].sum(),
                'raw_change_proportion_A_observed': change.sum() / observed.sum() if observed.any() else np.nan,
                'weighted_change_proportion_A_observed': w[change].sum() / denominator if denominator else np.nan,
                'weighted_change_proportion_all_landmarks': w[change].sum() / w.sum(),
                'change_tolerance': CHANGE_TOLERANCE,
                'change_definition': 'abs(A-B) > tolerance * max(1, abs(A), abs(B)); finite pairs only',
            })
    return pd.DataFrame(records)


def audit_facts(cohort, facts, include_c=False):
    """Reconstruct displayed model inputs independently from original fact rows."""
    required = {'cik', 'original_accession', 'feature', 'accn', 'A', 'B', 'B_accession'}
    require(required <= set(facts), f'Fact columns missing: {required - set(facts)}')
    if include_c:
        require({'C', 'C_accession'} <= set(facts), 'C diagnostic requires C facts')
    keys = cohort[['cik', 'accession']].rename(columns={'accession': 'original_accession'})
    selected = facts.merge(keys, on=['cik', 'original_accession'], how='inner', validate='many_to_one')
    require(not selected.duplicated(['cik', 'original_accession', 'feature']).any(),
            'Duplicate fact feature within a cohort landmark')
    require(set(selected.feature) <= set(RAW_FEATURES), 'Unexpected raw fact feature')
    require(selected.accn.eq(selected.original_accession).all(), 'A fact accession differs from original')
    require(selected.groupby(['cik', 'original_accession']).B_accession.nunique(dropna=False).le(1).all(),
            'B contains a mixture of source accessions within a landmark')
    index = pd.MultiIndex.from_frame(keys)
    audit = {'input_fact_rows': len(facts), 'cohort_fact_rows': len(selected),
             'cohort_landmarks_with_facts': len(selected[['cik', 'original_accession']].drop_duplicates()),
             'raw_features': RAW_FEATURES, 'versions_reconstructed': [],
             'initial_missingness_preserved': True, 'coherent_B_accession_check': 'PASS'}
    require(audit['cohort_landmarks_with_facts'] == len(cohort), 'Some cohort landmarks have no fact records')
    for version in ['A', 'B'] + (['C'] if include_c else []):
        raw = selected.pivot(index=['cik', 'original_accession'], columns='feature', values=version)
        raw = raw.reindex(index=index, columns=RAW_FEATURES)
        assets = raw.assets.to_numpy(float)
        valid_assets = np.isfinite(assets) & (assets > 0)
        denominator = np.where(valid_assets, assets, np.nan)
        with np.errstate(divide='ignore', invalid='ignore'):
            derived = {'log_assets': np.log(denominator)}
            for feature in RAW_FEATURES:
                if feature in ['assets', 'current_assets', 'current_liabilities']:
                    continue
                derived[feature + '_to_assets'] = raw[feature].to_numpy(float) / denominator
            derived['working_capital_to_assets'] = (
                raw.current_assets.to_numpy(float) - raw.current_liabilities.to_numpy(float)) / denominator
        for feature in FEATURES:
            require(same_numbers(derived[feature], cohort[version + '_' + feature]),
                    f'Fact-to-model-input reconstruction mismatch: {version}_{feature}')
        audit['versions_reconstructed'].append(version)
    audit['numeric_check'] = 'PASS; relative and absolute tolerance 1e-10'
    return audit


def check_metrics(frame, name):
    require({'block', 'model', 'version', 'average_precision'} <= set(frame), name + ': missing metric columns')
    x = frame.loc[frame.model.isin(MODELS) & frame.version.isin(['A', 'B'])].copy()
    expected = {(b, m, v) for b in BLOCKS for m in MODELS for v in ['A', 'B']}
    require(not x.duplicated(['block', 'model', 'version']).any(), name + ': duplicated metric cell')
    require(set(x[['block', 'model', 'version']].itertuples(index=False, name=None)) == expected,
            name + ': expected exactly 12 A/B metric rows')
    require(x.average_precision.dropna().between(0, 1).all(), name + ': AP outside [0,1]')
    return x


def uncertainty_for_forest(summary, metrics, mode):
    required = {'analysis_mode', 'block', 'model', 'metric', 'A', 'B', 'difference_B_minus_A',
                'ci95_low', 'ci95_high', 'n_boot', 'valid_boot', 'valid_boot_fraction', 'ci_method', 'status'}
    require(required <= set(summary), 'Missing uncertainty columns: ' + str(required - set(summary)))
    require(summary.analysis_mode.eq(mode).all(), 'Uncertainty analysis mode mismatch')
    x = summary.loc[summary.metric.eq('average_precision') & summary.model.isin(MODELS)].copy()
    require(not x.duplicated(['block', 'model']).any(), 'Duplicate AP confidence interval')
    expected = {(b, m) for b in BLOCKS for m in MODELS}
    require(set(x[['block', 'model']].itertuples(index=False, name=None)) == expected,
            'Expected six AP paired intervals')
    require(x.ci_method.eq(CI_METHOD).all(), 'Unexpected confidence interval method')
    require(x.n_boot.ge(500).all(), 'Fewer than 500 bootstrap replicates')
    require(x.valid_boot.between(0, x.n_boot).all(), 'Invalid bootstrap count')
    require(same_numbers(x.valid_boot / x.n_boot, x.valid_boot_fraction), 'Bootstrap valid fraction mismatch')
    rows = []
    for block in BLOCKS:
        for model in MODELS:
            u = x.loc[x.block.eq(block) & x.model.eq(model)].iloc[0].to_dict()
            ab = metrics.loc[metrics.block.eq(block) & metrics.model.eq(model)].set_index('version')
            a, b = ab.loc['A', 'average_precision'], ab.loc['B', 'average_precision']
            require(same_numbers([u['A'], u['B'], u['difference_B_minus_A']], [a, b, b - a]),
                    f'AP differs between metrics and uncertainty: {mode}/{block}/{model}')
            has_low, has_high = np.isfinite(u['ci95_low']), np.isfinite(u['ci95_high'])
            require(has_low == has_high, 'Only one finite confidence bound')
            if has_low:
                require(u['ci95_low'] <= u['ci95_high'], 'Reversed confidence interval')
                require(np.isfinite(u['difference_B_minus_A']), 'CI exists without point estimate')
                require(str(u['status']).startswith('estimated'), 'CI exists without estimated status')
                require(u['valid_boot_fraction'] == 1., 'Formal figure requires all bootstrap replicates valid')
            for column in ['A', 'B', 'difference_B_minus_A', 'ci95_low', 'ci95_high']:
                u[column + '_percentage_points'] = 100 * u[column]
            u['display_order'] = len(rows)
            rows.append(u)
    return pd.DataFrame(rows)


def validate_uncertainty_file(summary_path, manifest_path, prediction_path, protocol_path, mode):
    manifest = load_json(manifest_path)
    require(manifest.get('analysis_mode') == mode, 'Uncertainty manifest mode mismatch')
    require(manifest.get('outputs', {}).get(Path(summary_path).name) == sha(summary_path),
            'Uncertainty summary is not the hashed manifest output')
    require(manifest.get('protocol_sha256') == sha(protocol_path), 'Uncertainty protocol hash mismatch')
    sources = manifest.get('prediction_inputs', [])
    # These figures use one complete run-id prediction file, not mixtures of runs.
    require(len(sources) == 1, 'Figure requires one complete run-id uncertainty prediction input')
    require(sources[0].get('sha256') == sha(prediction_path), 'Uncertainty used different predictions')
    require(manifest.get('minimum_valid_fraction') == 1., 'Uncertainty valid fraction policy differs from figure policy')
    require(manifest.get('noncase_sample_clusters') == 1000, 'Expected all 1000 sampled noncase clusters')
    require(manifest.get('zero_domain_clusters_retained') is True, 'Zero-domain clusters were not retained')
    require(manifest.get('same_replicate_draws_across_all_blocks_models_and_versions') is True,
            'Pairing of bootstrap weights was not retained')
    require(isinstance(manifest.get('sampling_frame_sha256'), str) and
            len(manifest['sampling_frame_sha256']) == 64, 'Sampling frame hash missing')
    return manifest


def validate_inputs(args):
    paths = {name: Path(getattr(args, name)).resolve() for name in [
        'model_cohort', 'vintage_facts', 'cohort_summary', 'protocol', 'model_manifest',
        'main_metrics', 'main_uncertainty_summary', 'main_uncertainty_manifest',
        'frozen_metrics', 'frozen_uncertainty_summary', 'frozen_uncertainty_manifest']}
    for name, path in paths.items():
        require(path.is_file(), f'Missing {name}: {path}')
        require(path.drive.upper() == 'D:', f'{name} must be a D: working artifact')
    protocol = load_json(paths['protocol'])
    require(protocol.get('data_gate', {}).get('training_allowed_now') is True, 'Protocol data gate is not open')
    summary = load_json(paths['cohort_summary'])
    require(summary.get('status') == 'FINAL_COHORT_FROZEN', 'Cohort is not explicitly final and frozen')
    require(summary.get('source_collection_complete') is True, 'Source collection is not declared complete')
    require(summary.get('cohort_sha256') == sha(paths['model_cohort']), 'Frozen cohort hash mismatch')
    require(summary.get('fact_table_sha256') == sha(paths['vintage_facts']), 'Frozen fact table hash mismatch')
    model = load_json(paths['model_manifest'])
    require(model.get('mode') == 'run' and model.get('status') == 'completed', 'Model run is not completed formal analysis')
    require(model.get('main_fits_completed') == 12, 'Expected 12 completed main fits')
    require(model.get('data_gate_training_allowed') is True, 'Model was run without its recorded open gate')
    require(model.get('input_sha256') == sha(paths['model_cohort']), 'Models used a different cohort')
    require(model.get('protocol_sha256') == sha(paths['protocol']), 'Model protocol hash mismatch')
    name = paths['model_manifest'].name
    require(name.startswith('models_') and name.endswith('_manifest.json'), 'Use a run-id model manifest')
    prefix = name[:-len('_manifest.json')]
    require(prefix not in ['models', 'models_self_test'], 'Use a formal run-id manifest')
    expected_main = paths['model_manifest'].with_name(prefix + '_metrics.csv')
    require(paths['main_metrics'] == expected_main, 'Main metrics must belong to the explicit run-id manifest')
    main_predictions = paths['model_manifest'].with_name(prefix + '_test_predictions.parquet')
    require(main_predictions.is_file(), 'Main run-id predictions missing')
    frozen_outputs = model.get('frozen_a_diagnostic', {}).get('versioned_outputs', {})
    require(model.get('frozen_a_diagnostic', {}).get('additional_training_fits') == 0,
            'Frozen-A diagnostic reports additional fitting')
    require(frozen_outputs.get('metrics', {}).get('sha256') == sha(paths['frozen_metrics']),
            'Frozen metrics do not match model manifest')
    require(paths['frozen_metrics'].name == prefix + '_frozen_a_metrics.csv', 'Use frozen run-id metrics, not latest alias')
    frozen_predictions = Path(frozen_outputs.get('predictions', {}).get('path', ''))
    require(frozen_predictions.is_file(), 'Frozen prediction file missing')
    require(frozen_outputs['predictions']['sha256'] == sha(frozen_predictions), 'Frozen prediction hash mismatch')
    manifests = {}
    for panel, mode, prediction in [('main', 'refit_vintages', main_predictions),
                                    ('frozen', 'frozen_A_inputs', frozen_predictions)]:
        manifests[panel] = validate_uncertainty_file(
            paths[panel + '_uncertainty_summary'], paths[panel + '_uncertainty_manifest'],
            prediction, paths['protocol'], mode)
    for field in ['sampling_frame_sha256', 'sampling_summary_sha256', 'seed', 'n_boot',
                  'noncase_population_clusters', 'noncase_sample_clusters', 'certainty_clusters']:
        require(manifests['main'].get(field) == manifests['frozen'].get(field),
                'Main/frozen uncertainty design mismatch: ' + field)
    cohort = pd.read_parquet(paths['model_cohort'])
    required = {'cik', 'accession', 'cluster_id', 'decision_date', 'registry_event_365', 'sample_weight'}
    required |= {v + '_' + f for v in ['A', 'B'] + (['C'] if args.include_c else []) for f in FEATURES}
    require(required <= set(cohort), 'Missing cohort columns: ' + str(required - set(cohort)))
    require(not cohort.duplicated(['cik', 'accession']).any(), 'Duplicate cohort landmark')
    require(len(cohort) > 0 and np.isfinite(cohort.sample_weight).all() and cohort.sample_weight.gt(0).all(), 'Invalid weights')
    require(cohort.registry_event_365.isin([0, 1]).all(), 'Invalid event labels')
    require(not np.isinf(cohort[[v + '_' + f for v in ['A', 'B'] +
                (['C'] if args.include_c else []) for f in FEATURES]].to_numpy(float)).any(),
            'Infinite model input cannot be treated as an initial missing value')
    require(cohort.groupby('cluster_id').sample_weight.nunique().le(1).all(),
            'Inconsistent inclusion weights within a sampling cluster')
    dates = pd.to_datetime(cohort.decision_date, errors='raise')
    require(dates.between('2010-01-01', '2021-12-31').all(), 'Cohort dates outside frozen range')
    for field, actual in [('rows', len(cohort)), ('ciks', cohort.cik.nunique()),
                          ('clusters', cohort.cluster_id.nunique()),
                          ('positive_windows', int(cohort.registry_event_365.sum()))]:
        require(summary.get(field) == actual, 'Cohort summary count mismatch: ' + field)
    fact_audit = audit_facts(cohort, pd.read_parquet(paths['vintage_facts']), args.include_c)
    main = check_metrics(pd.read_csv(paths['main_metrics']), 'Main')
    frozen = check_metrics(pd.read_csv(paths['frozen_metrics']), 'Frozen')
    require({'scenario', 'training_version', 'preprocessing_version'} <= set(frozen), 'Frozen diagnostic metadata missing')
    require(frozen.training_version.eq('A').all() and frozen.preprocessing_version.eq('A').all(),
            'Frozen estimator or preprocessing version differs from A')
    require(frozen.scenario.eq(frozen.version.map({'A': 'A_model_A_inputs', 'B': 'A_model_B_inputs'})).all(),
            'Frozen scenario/version mapping mismatch')
    for block in BLOCKS:
        for learner in MODELS:
            year_low, year_high = map(int, block.split('_'))
            block_cohort = cohort.loc[dates.dt.year.between(year_low, year_high)]
            for table, table_name in [(main, 'Main'), (frozen, 'Frozen')]:
                for count_field, expected_count in [
                    ('n', len(block_cohort)),
                    ('positive_windows', int(block_cohort.registry_event_365.sum())),
                    ('weighted_n', block_cohort.sample_weight.sum()),
                    ('weighted_positive_windows', float(np.dot(block_cohort.sample_weight,
                                                               block_cohort.registry_event_365)))]:
                    require(count_field in table, table_name + ' missing denominator: ' + count_field)
                    observed_counts = table.loc[table.block.eq(block) & table.model.eq(learner), count_field]
                    require(same_numbers(observed_counts, expected_count),
                            f'{table_name} denominator differs from full cohort: {block}/{learner}/{count_field}')
            ma = main.loc[main.block.eq(block) & main.model.eq(learner) & main.version.eq('A'), 'average_precision']
            fa = frozen.loc[frozen.block.eq(block) & frozen.model.eq(learner) & frozen.version.eq('A'), 'average_precision']
            require(same_numbers(ma, fa), 'Frozen-A reference does not equal main A result')
    forest = pd.concat([
        uncertainty_for_forest(pd.read_csv(paths['main_uncertainty_summary']), main, 'refit_vintages'),
        uncertainty_for_forest(pd.read_csv(paths['frozen_uncertainty_summary']), frozen, 'frozen_A_inputs'),
    ], ignore_index=True)
    paths['main_predictions'] = main_predictions
    paths['frozen_predictions'] = frozen_predictions
    return {'paths': paths, 'cohort': cohort, 'fact_audit': fact_audit,
            'model_manifest': model, 'model_run_id': prefix, 'uncertainty_manifests': manifests,
            'annual': annual_descriptives(cohort), 'changes': feature_descriptives(cohort, args.include_c),
            'forest': forest}


def plot_artifacts(data, out, dpi):
    # Prevent font-cache writes to the user's C: profile.
    config = RESULTS / 'figures' / '.mplconfig'
    config.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(config)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager, ticker
    families = {entry.name for entry in font_manager.fontManager.ttflist}
    font = next((name for name in ['Arial', 'Times New Roman', 'DejaVu Sans'] if name in families), 'DejaVu Sans')
    plt.rcParams.update({'font.family': font, 'font.size': 10, 'axes.titlesize': 11,
                         'axes.labelsize': 10, 'legend.fontsize': 9, 'xtick.labelsize': 9,
                         'ytick.labelsize': 9, 'pdf.fonttype': 42, 'ps.fonttype': 42,
                         'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.linewidth': .7, 'savefig.facecolor': 'white'})
    outputs = []

    def save(fig, stem):
        for extension in ['pdf', 'svg', 'png']:
            path = out / (stem + '.' + extension)
            fig.savefig(path, dpi=dpi, bbox_inches='tight', pad_inches=.08)
            outputs.append(path)
        plt.close(fig)

    annual = data['annual']
    years = annual.year.to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(10.1, 4.0), layout='constrained')
    axes[0].bar(years, annual.weighted_landmarks, width=.72, color='0.25', edgecolor='black', linewidth=.5)
    axes[0].set(title='A  Eligible filing landmarks', xlabel='Decision year', ylabel='Weighted landmark count')
    axes[0].yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
    axes[1].bar(years - .19, annual.raw_positive_filing_windows, width=.36, color='0.25',
                edgecolor='black', linewidth=.5, label='Positive filing windows')
    axes[1].bar(years + .19, annual.raw_distinct_positive_ciks, width=.36, facecolor='white',
                edgecolor='black', hatch='///', linewidth=.7, label='Distinct positive CIKs')
    axes[1].set(title='B  Observed registry-linked positives', xlabel='Decision year', ylabel='Unweighted count')
    axes[1].yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    axes[1].legend(loc='upper left', bbox_to_anchor=(0, 1.0), frameon=False)
    axes[1].set_ylim(0, max(1, annual.raw_positive_filing_windows.max()) * 1.30)
    for ax in axes:
        ax.set_xticks(years)
        ax.set_xticklabels(years, rotation=45, ha='right')
        ax.set_axisbelow(True)
        ax.grid(axis='y', color='.88', linewidth=.5)
    save(fig, 'figure1_annual_sample')

    changes = data['changes']
    has_c = changes.comparison.eq('C_minus_A').any()
    fig, ax = plt.subplots(figsize=(8.5, 5.8), layout='constrained')
    y = np.arange(len(FEATURES))
    finite_percentages = (100 * changes.weighted_change_proportion_A_observed).dropna()
    maximum = float(finite_percentages.max()) if len(finite_percentages) else 0.
    axis_limit = min(100., max(5., np.ceil(maximum * 1.22 / 5.) * 5.))
    for version, offset, style in ([('B', -.17, {'color': '.25', 'edgecolor': 'black'}),
                                    ('C', .17, {'color': 'white', 'edgecolor': 'black', 'hatch': '///'})]
                                   if has_c else [('B', 0, {'color': '.25', 'edgecolor': 'black'})]):
        q = changes.loc[changes.comparison.eq(version + '_minus_A')].set_index('feature').loc[FEATURES]
        values = 100 * q.weighted_change_proportion_A_observed.to_numpy()
        ax.barh(y + offset, np.nan_to_num(values), height=.3 if has_c else .6, linewidth=.65,
                label='B: coherent later accession' if version == 'B' else 'C: per-tag hybrid diagnostic', **style)
        for position, value in zip(y + offset, values):
            if not np.isfinite(value):
                ax.text(1, position, 'No observed values', va='center', fontsize=8)
            else:
                outside = value < axis_limit * .92
                ax.text(value + axis_limit * .015 if outside else value - axis_limit * .02,
                        position, f'{value:.1f}%', va='center', ha='left' if outside else 'right',
                        fontsize=8, color='black' if outside or version == 'C' else 'white')
    ax.set_yticks(y, LABELS)
    ax.invert_yaxis()
    ax.set(xlabel='Numerically changed among initially observed inputs (%)', xlim=(0, axis_limit))
    ax.xaxis.set_major_locator(ticker.MultipleLocator(5 if axis_limit <= 30 else 20))
    ax.grid(axis='x', color='.88', linewidth=.5)
    ax.set_axisbelow(True)
    ax.legend(loc='lower left', bbox_to_anchor=(0, 1.01), frameon=False)
    save(fig, 'figure2_input_changes')

    forest = data['forest']
    extent_values = forest[['difference_B_minus_A_percentage_points', 'ci95_low_percentage_points',
                             'ci95_high_percentage_points']].to_numpy(float)
    finite = extent_values[np.isfinite(extent_values)]
    extent = max(.05, float(np.max(np.abs(finite))) * 1.18) if len(finite) else 1.
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.5), sharex=True, sharey=True, layout='constrained')
    labels = [b.replace('_', '–') + '  ' + m for b in BLOCKS for m in MODELS]
    for ax, mode, title in zip(axes, ['refit_vintages', 'frozen_A_inputs'],
                               ['A  Refit by input vintage', 'B  Fixed A model and preprocessing']):
        q = forest.loc[forest.analysis_mode.eq(mode)].sort_values('display_order')
        ax.axvline(0, color='.45', linestyle='--', linewidth=.8)
        for position, row in enumerate(q.itertuples()):
            point = row.difference_B_minus_A_percentage_points
            lower, upper = row.ci95_low_percentage_points, row.ci95_high_percentage_points
            marker = 'o' if row.model == 'LR' else 's'
            if np.isfinite(lower) and np.isfinite(upper):
                ax.hlines(position, lower, upper, color='black', linewidth=1.15)
                ax.vlines([lower, upper], position - .08, position + .08, color='black', linewidth=.8)
            if np.isfinite(point):
                ax.plot(point, position, marker=marker, markersize=5.5, color='black',
                        markerfacecolor='white' if row.model == 'LR' else 'black')
                if not np.isfinite(lower):
                    ax.text(.98, position, 'CI unavailable', transform=ax.get_yaxis_transform(),
                            ha='right', va='center', fontsize=8)
            else:
                ax.text(.5, position, 'Not estimable', transform=ax.get_yaxis_transform(),
                        ha='center', va='center', fontsize=8)
        ax.set_yticks(range(6), labels)
        ax.set(title=title, xlabel='B − A average precision (percentage points)',
               xlim=(-extent, extent), ylim=(5.6, -.6))
        ax.grid(axis='x', color='.9', linewidth=.5)
        ax.set_axisbelow(True)
    axes[1].tick_params(axis='y', labelleft=False)
    save(fig, 'figure3_paired_average_precision')
    return outputs, {'matplotlib': matplotlib.__version__, 'font': font, 'png_dpi': dpi,
                     'vector_formats': ['PDF', 'SVG'], 'visual_qa': 'Not yet independently inspected after rendering'}


def captions(data, include_c):
    u = data['uncertainty_manifests']['main']
    return f'''# Figure titles and captions

Figure 1. Annual analysis sample.
(A) The sum of inverse cluster inclusion probabilities over eligible filing landmarks,
by decision year. This estimates landmark counts in the restricted historical filing
domain; it is not a count of independent companies. (B) Unweighted registry-linked
positive 365-day filing windows and distinct directly linked CIKs contributing at
least one such window in that decision year. A CIK can contribute in more than one
year. Neither series is a count of independent bankruptcy episodes or complete
market bankruptcies. The two panels have separate count scales. Reporting eligibility
and the original-accession positive-assets condition apply to the full frozen cohort.

Figure 2. Changes in financial model inputs.
For each of ten inputs, bars show the inverse-probability-weighted proportion of
initially observed values that change between original-accession version A and
coherent later-accession version B. A numerical change satisfies
abs(A−B) > 10⁻¹² × max(1, abs(A), abs(B)). Initial missing values remain missing and
are excluded from the feature-specific primary denominator; all-cohort denominators,
raw counts and weighted counts are exported separately. These are changes in model
inputs, including ratios, rather than counts of altered raw financial facts.
{'Hatched C bars describe a per-tag synthetic hybrid and are not a coherent filing or a separately trained primary model.' if include_c else 'The figure contains only the coherent A/B comparison.'}
Reporting lag, a common model covariate, is not one of the ten vintage-varying inputs.
These are accession-specific records reconstructed from the retrieved SEC API;
neither version is claimed to be an authenticated historical API snapshot.

Figure 3. Paired changes in weighted average precision.
(A) B-trained/B-input predictions minus A-trained/A-input predictions, separately
for logistic regression (LR) and LightGBM (LGBM) in each test block. (B) The same
input contrast with the final A estimator and A preprocessing held fixed, requiring
no additional training. Points and intervals are in percentage points (100 times
the difference on the average-precision probability scale); positive values indicate
higher retrospective average precision for B. Lines are basic centered 95% design
bootstrap intervals from {u['n_boot']} Rao–Wu–Yue rescaled SRS replicates, with
finite population correction. All {u['noncase_sample_clusters']} sampled noncase
clusters, including clusters with no eligible test landmarks, enter the resampling
design; {u['certainty_clusters']} certainty clusters remain fixed. The same cluster
replicate weights preserve pairing across versions, learners and test blocks.
The intervals condition on the fitted models, observed registry outcomes, certainty
clusters and the finite sampling frame. They do not include model training or
selection variability, registry undercoverage, uncertainty in the case population,
or future macroeconomic variation. The three blocks are not independent economic
experiments. No multiple-comparison or simultaneous-coverage claim is made. Invalid
replicate rates and point-estimate denominators are retained in the exported data;
an unavailable interval is never replaced with zero. B uses later information and
is a diagnostic comparison, not a deployable forecasting procedure.
'''


def self_test():
    """Pure helper checks only: no files, no fake research results or rendered figures."""
    require(np.array_equal(changed([1., np.nan, 2., 0.], [1. + 1e-13, 7., 2.1, 2e-12]),
                           [False, False, True, True]), 'Numerical change tolerance test failed')
    base = pd.DataFrame({'sample_weight': [9., 1., 5.], 'cik': ['a', 'b', 'c'],
                         'accession': ['x', 'y', 'z'], 'cluster_id': ['a', 'b', 'c'],
                         'decision_date': ['2016-01-01'] * 3, 'registry_event_365': [0, 1, 1]})
    for feature in FEATURES:
        base['A_' + feature] = [2., 4., np.nan]
        base['B_' + feature] = [2., 5., np.nan]
    changes = feature_descriptives(base)
    require(same_numbers(changes.weighted_change_proportion_A_observed, .1), 'Observed denominator test failed')
    require(same_numbers(changes.weighted_change_proportion_all_landmarks, 1 / 15), 'All-cohort denominator test failed')
    annual = annual_descriptives(base).set_index('year').loc[2016]
    require(annual.weighted_landmarks == 15 and annual.raw_positive_filing_windows == 2,
            'Weighted and raw annual counts conflated')
    bad = base.copy(); bad.loc[2, 'B_log_assets'] = 3.
    try:
        feature_descriptives(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('Missingness mismatch was accepted')
    print('PASS: synthetic helper checks only; no figures or research statistics generated.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Generate artifacts after all gates pass')
    parser.add_argument('--self-test', action='store_true', help='Pure helper checks without rendering or file outputs')
    defaults = {'model-cohort': ROOT / 'datasets/model_cohort.parquet',
                'vintage-facts': ROOT / 'datasets/vintage_facts.parquet',
                'cohort-summary': RESULTS / 'cohort_summary.json',
                'protocol': ROOT / 'phase2_protocol.json'}
    for option, default in defaults.items():
        parser.add_argument('--' + option, type=Path, default=default)
    for option in ['model-manifest', 'main-metrics', 'main-uncertainty-summary',
                   'main-uncertainty-manifest', 'frozen-metrics',
                   'frozen-uncertainty-summary', 'frozen-uncertainty-manifest']:
        parser.add_argument('--' + option, type=Path)
    parser.add_argument('--include-c', action='store_true', help='Add explicitly synthetic per-tag C diagnostic to Figure 2')
    parser.add_argument('--dpi', type=int, default=900)
    args = parser.parse_args()
    if args.self_test:
        require(not args.run, '--self-test and --run are mutually exclusive')
        self_test()
        return
    require(ROOT.drive.upper() == 'D:', 'Script and generated artifacts must live on D:')
    require(args.dpi >= 900, 'PNG export must be at least 900 dpi')
    for option in ['model_manifest', 'main_metrics', 'main_uncertainty_summary',
                   'main_uncertainty_manifest', 'frozen_metrics',
                   'frozen_uncertainty_summary', 'frozen_uncertainty_manifest']:
        require(getattr(args, option) is not None, 'Required argument: --' + option.replace('_', '-'))
    data = validate_inputs(args)
    if not args.run:
        print(json.dumps({'status': 'PREFLIGHT_PASS_NO_ARTIFACTS_WRITTEN',
                          'model_run_id': data['model_run_id'], 'cohort_rows': len(data['cohort']),
                          'fact_audit': data['fact_audit']}, indent=2))
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run_id = data['model_run_id'] + '_figures_' + stamp
    out = RESULTS / 'figures' / run_id
    out.mkdir(parents=True, exist_ok=False)
    prefix = RESULTS / ('descriptive_' + run_id)
    output_paths = []
    for key, suffix in [('annual', 'annual_counts'), ('changes', 'feature_changes'), ('forest', 'forest_data')]:
        path = Path(str(prefix) + '_' + suffix + '.csv')
        data[key].to_csv(path, index=False, encoding='utf-8-sig')
        output_paths.append(path)
    metadata = {
        'cohort_rows_raw': len(data['cohort']), 'cohort_weighted_landmarks': data['cohort'].sample_weight.sum(),
        'fact_reconstruction_audit': data['fact_audit'],
        'feature_primary_denominator': 'sum of inclusion weights among initially finite A values of that feature',
        'feature_secondary_denominator': 'sum of inclusion weights over all eligible landmarks',
        'annual_positive_units': 'raw filing windows and distinct CIKs contributing a positive window within year',
        'not_independent_events': True, 'missingness_policy': 'A mask retained in B, and C when shown',
        'change_tolerance': CHANGE_TOLERANCE, 'forest_display_scale': 'percentage points = probability-scale difference times 100',
        'forest_inference': 'conditional fixed-model design uncertainty; pointwise, not simultaneous',
        'source_vintage_limit': 'accession reconstruction from currently retrieved API, not historical API snapshots',
    }
    denominator_path = Path(str(prefix) + '_denominators.json')
    write_json(denominator_path, metadata)
    output_paths.append(denominator_path)
    rendered, rendering = plot_artifacts(data, out, args.dpi)
    output_paths += rendered
    caption_path = out / 'captions.md'
    caption_path.write_text(captions(data, args.include_c), encoding='utf-8')
    output_paths.append(caption_path)
    manifest = {
        'status': 'GENERATED_REQUIRES_VISUAL_INSPECTION', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'model_run_id': data['model_run_id'], 'figure_run_id': run_id,
        'source_script': str(Path(__file__).resolve()), 'source_script_sha256': sha(__file__),
        'inputs': {key: {'path': str(path), 'sha256': sha(path)} for key, path in data['paths'].items()},
        'outputs': {str(path): sha(path) for path in output_paths},
        'rendering': rendering, 'include_per_tag_C': args.include_c,
        'n_primary_model_pairs': 6, 'n_frozen_A_pairs': 6, 'facts_reconstructed': data['fact_audit'],
        'no_models_fitted_here': True,
    }
    manifest_path = Path(str(prefix) + '_manifest.json')
    write_json(manifest_path, manifest)
    print(str(manifest_path))


if __name__ == '__main__':
    main()
