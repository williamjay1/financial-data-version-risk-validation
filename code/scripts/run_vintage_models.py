"""Gated, weighted A/B financial-vintage diagnostics. Read D caches only.

Default: schema/time preflight, no model fitting. --run also requires the
protocol's data_gate.training_allowed_now to be true. --self-test uses only
small synthetic arrays, including two synthetic model-interface smoke fits.
Training also binds the actual input hash to the passed gate or an explicitly
recorded sensitivity output descended from that exact gated main cohort.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import shutil
import sys
import time
import traceback
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import brentq, minimize
from scipy.special import expit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.exceptions import ConvergenceWarning
from lightgbm import LGBMClassifier
import joblib

ROOT = Path(__file__).resolve().parents[1]
FEATURES = [
    'log_assets', 'liabilities_to_assets', 'equity_to_assets', 'cash_to_assets',
    'net_income_to_assets', 'revenue_to_assets', 'operating_income_to_assets',
    'operating_cash_to_assets', 'retained_earnings_to_assets',
    'working_capital_to_assets',
]
COMMON_FEATURES = ['report_lag_days']
MODEL_FEATURES = FEATURES + COMMON_FEATURES
BLOCKS = [(2016, 2017), (2018, 2019), (2020, 2021)]
HORIZON_DAYS = 365
LABEL_GRACE_DAYS = 90
SEED = 20260921
META_COLUMNS = [
    'cik', 'cluster_id', 'accession', 'decision_date', 'filing_date', 'fiscal_end',
    'pre_first_registry_event', 'registry_event_365', 'first_registry_event',
    'report_lag_days', 'n_original_facts', 'sample_weight', 'sampling_stratum',
]
OPTIONAL_META = ['group_id', 'case_id', 'group_case_id', 'B_accession', 'b_accession']


def clean_json(obj):
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, np.ndarray)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj) if math.isfinite(float(obj)) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if obj is pd.NaT or obj is pd.NA:
        return None
    if isinstance(obj, Path):
        return str(obj)
    return obj


def write_json(path, obj):
    Path(path).write_text(json.dumps(clean_json(obj), indent=2,
                                    ensure_ascii=False, allow_nan=False), encoding='utf-8')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def require(condition, message):
    if not bool(condition):
        raise ValueError(message)


def require_d_path(path):
    p = Path(path).resolve()
    require(p.drive.lower() == 'd:', f'Only D: working paths are allowed: {p}')
    return p


def verify_training_binding(source, protocol_path, protocol):
    """Fail closed unless this exact file descends from the passed data gate."""
    source = require_d_path(source)
    protocol_path = require_d_path(protocol_path)
    project = protocol_path.parent
    gate = protocol.get('data_gate', {})
    require(gate.get('training_allowed_now') is True,
            'Training blocked: protocol.data_gate.training_allowed_now must be explicitly true')
    expected_hash = gate.get('cohort_sha256')
    require(isinstance(expected_hash, str) and len(expected_hash) == 64,
            'Training blocked: gate has no valid frozen cohort hash')
    main_path = require_d_path(project / 'datasets/model_cohort.parquet')
    require(main_path.is_file(), 'Training blocked: frozen main cohort is missing')
    require(sha256(main_path) == expected_hash,
            'Training blocked: current main cohort hash differs from the passed gate')
    audit_value = gate.get('audit')
    require(isinstance(audit_value, str) and bool(audit_value),
            'Training blocked: gate audit path is missing')
    audit_path = require_d_path(project / audit_value)
    require(audit_path.is_file(), 'Training blocked: gate audit file is missing')
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    require(audit.get('status') == 'PASS' and not audit.get('issues'),
            'Training blocked: latest gate audit did not pass')
    require(audit.get('cohort_sha256') == expected_hash,
            'Training blocked: protocol and audit cohort hashes disagree')
    input_hash = sha256(source)
    evidence = {'status': 'verified', 'main_cohort_path': str(main_path),
                'main_cohort_sha256': expected_hash, 'input_sha256': input_hash,
                'gate_audit_path': str(audit_path), 'gate_audit_sha256': sha256(audit_path)}
    if source == main_path:
        require(input_hash == expected_hash, 'Training blocked: input main cohort hash changed')
        evidence['input_kind'] = 'gated_main_cohort'
        return evidence
    design_path = require_d_path(project / 'results/sensitivity_design.json')
    require(design_path.is_file(), 'Training blocked: input is not the gated main cohort and has no sensitivity design')
    design = json.loads(design_path.read_text(encoding='utf-8'))
    require(design.get('status') == 'complete' and design.get('source_files_unchanged') is True,
            'Training blocked: sensitivity generation is not complete and source-verified')
    require(design.get('main_sha256') == expected_hash,
            'Training blocked: sensitivity was generated from a different main cohort')
    design_main = design.get('sources', {}).get('main', {})
    require(design_main.get('sha256') == expected_hash and
            require_d_path(design_main.get('path', '')) == main_path,
            'Training blocked: sensitivity main source identity disagrees with gate')
    facts = design.get('sources', {}).get('facts', {})
    fact_hash = design.get('facts_sha256')
    require(bool(fact_hash) and facts.get('sha256') == fact_hash and
            audit.get('fact_table_sha256') == fact_hash,
            'Training blocked: sensitivity fact source differs from the passed gate')
    fact_path = require_d_path(facts.get('path', ''))
    require(fact_path.is_file() and sha256(fact_path) == fact_hash,
            'Training blocked: sensitivity fact source changed or is missing')
    candidates = [(name, row) for name, row in design.get('outputs', {}).items()
                  if row.get('path') and require_d_path(row['path']) == source]
    require(len(candidates) == 1,
            'Training blocked: input path has no unique recorded sensitivity output')
    name, output = candidates[0]
    require(name in ('source_scale_corrected', 'no_transition'),
            'Training blocked: sensitivity is not one of the locked designs')
    require(output.get('sha256') == input_hash,
            'Training blocked: sensitivity output hash differs from generation record')
    equivalent = (design.get('S2', {}).get('skip_training') is True if name == 'no_transition'
                  else design.get('S1', {}).get('training_may_be_skipped_as_equivalent') is True)
    require(not equivalent,
            'Training blocked: sensitivity is equivalent to main; use existing main results, do not repeat fits')
    evidence.update(input_kind='recorded_sensitivity', sensitivity=name,
                    sensitivity_design_path=str(design_path),
                    sensitivity_design_sha256=sha256(design_path), fact_table_sha256=fact_hash)
    return evidence


def weighted_quantile(values, weights, q):
    """Inverted weighted empirical CDF; deterministic and tie invariant."""
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    require(x.shape == w.shape and x.ndim == 1, 'Quantile input shape mismatch')
    require(0 <= q <= 1, 'Quantile must be in [0,1]')
    use = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not use.any():
        return np.nan
    x, w = x[use], w[use]
    order = np.argsort(x, kind='stable')
    x, w = x[order], w[order]
    k = np.searchsorted(np.cumsum(w), q * w.sum(), side='left')
    return float(x[min(k, len(x)-1)])


class WeightedPreprocessor:
    """Training-only weighted winsorization, median imputation, missing flags.

    Scaling, when enabled, uses the weighted population mean/variance of the
    transformed training matrix (numeric columns and missingness indicators).
    All-missing training columns are set to a fixed zero, never fitted on later
    data. A test value in such a column is also mapped to zero.
    """
    def __init__(self, scale=False, lower_q=0.01, upper_q=0.99):
        self.scale = bool(scale)
        self.lower_q = float(lower_q)
        self.upper_q = float(upper_q)

    def fit(self, x, weights):
        x = np.asarray(x, dtype=float)
        w = np.asarray(weights, dtype=float)
        require(x.ndim == 2 and len(x) == len(w) and len(x) > 0,
                'Invalid preprocessing training arrays')
        require(np.all(np.isfinite(w) & (w > 0)), 'Invalid fit weights')
        require(not np.isinf(x).any(), 'Infinite feature in training data')
        self.n_features_in_ = x.shape[1]
        self.lower_ = np.array([weighted_quantile(x[:, j], w, self.lower_q)
                                for j in range(x.shape[1])])
        self.upper_ = np.array([weighted_quantile(x[:, j], w, self.upper_q)
                                for j in range(x.shape[1])])
        self.median_ = np.array([weighted_quantile(x[:, j], w, 0.5)
                                 for j in range(x.shape[1])])
        self.all_missing_ = np.isnan(self.median_)
        self.lower_[self.all_missing_] = 0.0
        self.upper_[self.all_missing_] = 0.0
        self.median_[self.all_missing_] = 0.0
        z = self._unscaled(x)
        self.mean_ = np.average(z, weights=w, axis=0)
        self.sd_ = np.sqrt(np.average((z-self.mean_)**2, weights=w, axis=0))
        self.sd_[self.sd_ < 1e-12] = 1.0
        return self

    def _unscaled(self, x):
        x = np.asarray(x, dtype=float)
        require(x.ndim == 2 and x.shape[1] == self.n_features_in_,
                'Preprocessing feature count mismatch')
        require(not np.isinf(x).any(), 'Infinite feature at transform')
        missing = np.isnan(x)
        z = np.clip(x, self.lower_, self.upper_)
        z = np.where(missing, self.median_, z)
        z[:, self.all_missing_] = 0.0
        z = np.concatenate([z, missing.astype(float)], axis=1)
        require(np.isfinite(z).all(), 'Nonfinite preprocessed feature')
        return z

    def transform(self, x):
        z = self._unscaled(x)
        return (z-self.mean_)/self.sd_ if self.scale else z

    def manifest(self):
        return {'scale': self.scale, 'lower_q': self.lower_q, 'upper_q': self.upper_q,
                'quantile_definition': 'inverted weighted empirical CDF',
                'lower': self.lower_, 'upper': self.upper_, 'median': self.median_,
                'all_missing_training_columns': self.all_missing_,
                'weighted_mean': self.mean_, 'weighted_sd': self.sd_,
                'output_order': MODEL_FEATURES + ['missing_'+f for f in MODEL_FEATURES]}

    @classmethod
    def from_manifest(cls, state):
        """Reconstruct without pickling a __main__ custom class."""
        obj=cls(scale=state['scale'],lower_q=state['lower_q'],upper_q=state['upper_q'])
        for source,target in [('lower','lower_'),('upper','upper_'),('median','median_'),
                              ('weighted_mean','mean_'),('weighted_sd','sd_')]:
            setattr(obj,target,np.asarray(state[source],dtype=float))
        obj.all_missing_=np.asarray(state['all_missing_training_columns'],dtype=bool)
        obj.n_features_in_=len(obj.median_)
        return obj


def normalized_weights(weights):
    w = np.asarray(weights, dtype=float)
    require(np.all(np.isfinite(w) & (w > 0)), 'Weights must be positive finite')
    return w / w.mean()


def recall_at_weighted_capacity(y, p, weights, capacity=0.05):
    """Retrospective weighted capacity; split boundary score ties uniformly.

    Fractional selection of the entire boundary tie group avoids dependence
    on input ordering and is an expected/randomized diagnostic, not a literal
    implementable list. Returns per-row fractional selection for audit/overlap.
    """
    y, p, w = map(lambda a: np.asarray(a, dtype=float), (y, p, weights))
    selection = np.zeros(len(y), dtype=float)
    total_positive = np.dot(w, y)
    budget = capacity * w.sum()
    order = np.argsort(-p, kind='stable')
    left = 0
    while left < len(order) and budget > 0:
        right = left + 1
        while right < len(order) and p[order[right]] == p[order[left]]:
            right += 1
        idx = order[left:right]
        mass = w[idx].sum()
        fraction = min(1.0, max(0.0, budget / mass))
        selection[idx] = fraction
        budget -= fraction * mass
        left = right
    recall = float(np.dot(w * y, selection) / total_positive) if total_positive > 0 else np.nan
    return recall, selection


def calibration_diagnostics(y, p, weights):
    """Test-only descriptive calibration; never alters stored predictions."""
    y, p, w = map(lambda a: np.asarray(a, dtype=float), (y, p, weights))
    out = {'calibration_intercept': np.nan, 'calibration_joint_intercept': np.nan,
           'calibration_slope': np.nan, 'calibration_status': 'undefined_single_class',
           'calibration_sparse_class': bool(min(np.sum(y == 0), np.sum(y == 1)) < 10)}
    if len(np.unique(y)) != 2:
        return out
    w = normalized_weights(w)
    z = np.log(np.clip(p, 1e-10, 1-1e-10) / (1-np.clip(p, 1e-10, 1-1e-10)))
    root = brentq(lambda a: np.dot(w, expit(a+z)-y), -80.0, 80.0)
    out['calibration_intercept'] = float(root)
    if np.ptp(z) < 1e-10:
        out['calibration_status'] = 'joint_slope_not_identified_constant_prediction'
        return out
    if np.min(z[y == 1]) >= np.max(z[y == 0]) or np.min(z[y == 0]) >= np.max(z[y == 1]):
        out['calibration_status'] = 'joint_mle_separation'
        return out
    design = np.column_stack([np.ones(len(y)), z])
    def loss(beta):
        eta = design @ beta
        return float(np.dot(w, np.logaddexp(0, eta)-y*eta) / w.sum())
    def grad(beta):
        return design.T @ (w*(expit(design @ beta)-y)) / w.sum()
    result = minimize(loss, np.array([0.0, 1.0]), jac=grad, method='BFGS',
                      options={'maxiter': 1000, 'gtol': 1e-8})
    prob = expit(design @ result.x)
    hessian = design.T @ ((w*prob*(1-prob))[:, None]*design) / w.sum()
    condition = float(np.linalg.cond(hessian))
    converged = bool(np.max(np.abs(grad(result.x))) < 1e-6)
    if converged and np.isfinite(condition) and condition < 1e12 and np.max(np.abs(result.x)) < 100:
        out.update(calibration_joint_intercept=float(result.x[0]),
                   calibration_slope=float(result.x[1]), calibration_status='estimated')
    else:
        out['calibration_status'] = 'joint_optimizer_or_identification_failure'
    out['calibration_hessian_condition'] = condition
    return out


def evaluate(y, p, weights, calibration=True):
    y, p, w = map(lambda a: np.asarray(a, dtype=float), (y, p, weights))
    require(len(y) == len(p) == len(w) and len(y) > 0, 'Invalid evaluation arrays')
    require(np.isfinite(p).all() and np.all((p >= 0) & (p <= 1)), 'Invalid probability')
    require(np.isfinite(w).all() and (w > 0).all(), 'Invalid evaluation weights')
    require(np.isin(y, [0, 1]).all(), 'Nonbinary evaluation outcome')
    both_classes = len(np.unique(y)) == 2
    recall, selected = recall_at_weighted_capacity(y, p, w)
    metrics = {
        'n': len(y), 'positive_windows': int(y.sum()), 'negative_windows': int((1-y).sum()),
        'weighted_n': float(w.sum()), 'weighted_positive_windows': float(np.dot(w, y)),
        'weighted_prevalence': float(np.dot(w, y)/w.sum()),
        'kish_weight_diagnostic': float(w.sum()**2/np.dot(w, w)),
        'average_precision': float(average_precision_score(y, p, sample_weight=w)) if both_classes else np.nan,
        'roc_auc': float(roc_auc_score(y, p, sample_weight=w)) if both_classes else np.nan,
        'brier': float(np.average((p-y)**2, weights=w)),
        'retrospective_recall_at_5percent': recall,
        'retrospective_selected_weight': float(np.dot(w, selected)),
        'classification_metrics_status': 'estimated' if both_classes else 'undefined_single_class',
    }
    if calibration:
        metrics.update(calibration_diagnostics(y, p, w))
    return metrics, selected


def parse_bool(series):
    if series.dtype == bool:
        return series.to_numpy()
    mapping = {'true': True, 'false': False, '1': True, '0': False, '1.0': True, '0.0': False}
    values = series.astype(str).str.lower().map(mapping)
    require(values.notna().all(), 'Unrecognized pre_first_registry_event values')
    return values.to_numpy(dtype=bool)


def validate_cohort(df):
    columns = META_COLUMNS + [v+'_'+f for v in ['A', 'B'] for f in FEATURES]
    missing = sorted(set(columns)-set(df.columns))
    require(not missing, f'Missing cohort columns: {missing}')
    require(len(df) > 0, 'Empty model cohort')
    df = df.copy()
    require(df.cik.notna().all() and df.accession.notna().all(), 'Missing row identity')
    df['cik'] = df.cik.astype(str)
    require(df.cluster_id.notna().all(), 'Missing sampling cluster_id')
    df['cluster_id'] = df.cluster_id.astype(str)
    df['accession'] = df.accession.astype(str)
    require(not df.duplicated(['cik', 'accession']).any(), 'Duplicate CIK/accession landmark')
    for col in ['decision_date', 'filing_date', 'fiscal_end', 'first_registry_event']:
        parsed = pd.to_datetime(df[col], errors='coerce', utc=True).dt.tz_localize(None).dt.normalize()
        if col != 'first_registry_event':
            require(parsed.notna().all(), f'Unparseable required date {col}')
        else:
            original_present = df[col].notna() & df[col].astype(str).str.strip().ne('')
            require((~original_present | parsed.notna()).all(), 'Unparseable nonempty first event date')
        df[col] = parsed
    require((df.decision_date == df.filing_date + pd.Timedelta(days=1)).all(),
            'Decision date must be filing date + 1 calendar day')
    require((df.fiscal_end <= df.filing_date).all(), 'Fiscal end after actual filing date')
    require((df.decision_date <= pd.Timestamp('2021-12-31')).all(),
            'Incomplete registry follow-up: origin later than 2021-12-31')
    require(parse_bool(df.pre_first_registry_event).all(), 'Post-first-event rows must be resolved by cohort builder')
    event_known = df.first_registry_event.notna()
    require((~event_known | (df.first_registry_event > df.decision_date)).all(),
            'Event on/before decision date is not an eligible first-event landmark')
    y = pd.to_numeric(df.registry_event_365, errors='coerce')
    require(y.notna().all() and y.isin([0, 1]).all(), 'Unknown/nonbinary outcome in model cohort')
    expected = event_known & df.first_registry_event.gt(df.decision_date) & df.first_registry_event.le(
        df.decision_date + pd.Timedelta(days=HORIZON_DAYS))
    require(np.array_equal(expected.astype(int), y.astype(int)),
            'Supplied registry_event_365 conflicts with fixed first-event date/window; labels not changed')
    df['registry_event_365'] = y.astype(np.int8)
    df['sample_weight'] = pd.to_numeric(df.sample_weight, errors='coerce')
    require(np.isfinite(df.sample_weight).all() and df.sample_weight.ge(1-1e-12).all(),
            'Design weights must be finite 1/pi >= 1, not mean-normalized cohort weights')
    require(set(df.sampling_stratum.unique()) <= {'certainty', 'noncase_srs'}, 'Unexpected sampling stratum')
    certainty = df.sampling_stratum.eq('certainty')
    require(np.allclose(df.loc[certainty, 'sample_weight'], 1.0, atol=1e-12),
            'Certainty-layer records must have weight 1, including their negative windows')
    require(df.groupby('cik').sample_weight.nunique().le(1).all(), 'Weight varies across same CIK')
    require(df.groupby('cik').sampling_stratum.nunique().le(1).all(), 'Stratum varies across same CIK')
    require(df.groupby('cik').cluster_id.nunique().le(1).all(), 'Same CIK assigned to multiple sampling clusters')
    require(df.groupby('cluster_id').sample_weight.nunique().le(1).all(), 'Weight varies within sampling cluster')
    require(df.groupby('cluster_id').sampling_stratum.nunique().le(1).all(), 'Stratum varies within sampling cluster')
    for col in COMMON_FEATURES:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        require(np.isfinite(df[col]).all(), f'Invalid common covariate {col}')
    require(df.report_lag_days.ge(0).all(), 'Negative report lag')
    for v in ['A', 'B']:
        for f in FEATURES:
            col = v+'_'+f
            original = df[col]
            converted = pd.to_numeric(original, errors='coerce')
            require((original.isna() | converted.notna()).all(), f'Nonnumeric feature {col}')
            df[col] = converted.astype(float)
        require(not np.isinf(df[[v+'_'+f for f in FEATURES]].to_numpy()).any(), f'Infinite {v} features')
    a = df[['A_'+f for f in FEATURES]].to_numpy()
    b = df[['B_'+f for f in FEATURES]].to_numpy()
    require(np.array_equal(np.isnan(a), np.isnan(b)), 'A/B missingness masks differ')
    df['mature_date'] = df.decision_date + pd.Timedelta(days=HORIZON_DAYS+LABEL_GRACE_DAYS)
    df = df.sort_values(['decision_date', 'cik', 'accession'], kind='stable').reset_index(drop=True)
    df['row_id'] = df.cik + '|' + df.accession
    require(df.row_id.is_unique, 'Nonunique row_id')
    return df


def subset_summary(df):
    if not len(df):
        return {'n': 0, 'positive_windows': 0, 'n_cik': 0}
    out = {'n': len(df), 'positive_windows': int(df.registry_event_365.sum()),
           'n_cik': int(df.cik.nunique()), 'min_decision': df.decision_date.min(),
           'n_sampling_clusters': int(df.cluster_id.nunique()),
           'positive_sampling_clusters': int(df.loc[df.registry_event_365.eq(1),'cluster_id'].nunique()),
           'max_decision': df.decision_date.max(), 'max_mature_date': df.mature_date.max(),
           'weighted_n': float(df.sample_weight.sum()),
           'weighted_positive_windows': float(np.dot(df.sample_weight, df.registry_event_365)),
           'positive_cik_event_pairs': int(df.loc[df.registry_event_365.eq(1),
                                                ['cik','first_registry_event']].drop_duplicates().shape[0]),
           'strata': df.groupby('sampling_stratum').agg(n=('cik','size'), n_cik=('cik','nunique'), n_sampling_clusters=('cluster_id','nunique'),
                    weighted_n=('sample_weight','sum')).reset_index().to_dict('records')}
    if 'group_id' in df:
        out['n_group_id_observed'] = int(df.group_id.nunique())
    out['independent_group_event_count_available'] = 'group_case_id' in df
    if 'group_case_id' in df:
        out['positive_group_cases'] = int(df.loc[df.registry_event_365.eq(1),'group_case_id'].nunique())
    return out


def make_splits(df):
    splits = []
    for start_year, end_year in BLOCKS:
        start = pd.Timestamp(start_year, 1, 1)
        end = pd.Timestamp(end_year+1, 1, 1)
        val_start = pd.Timestamp(start_year-3, 1, 1)
        val_end = pd.Timestamp(start_year-2, 1, 1)
        train = df.index[df.decision_date.lt(val_start) & df.mature_date.le(val_start)].to_numpy()
        val = df.index[df.decision_date.ge(val_start) & df.decision_date.lt(val_end)
                       & df.mature_date.le(start)].to_numpy()
        refit = df.index[df.decision_date.lt(start) & df.mature_date.le(start)].to_numpy()
        test = df.index[df.decision_date.ge(start) & df.decision_date.lt(end)].to_numpy()
        sets = [set(a) for a in [train, val, test]]
        require(not(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2]), 'Split overlap')
        require(set(train).issubset(set(refit)) and set(val).issubset(set(refit)), 'Refit excludes mature development rows')
        issues=[]; diagnostic_warnings=[]
        for name, idx in [('tuning_train', train), ('validation', val), ('refit', refit)]:
            if len(idx) == 0 or df.loc[idx, 'registry_event_365'].nunique() != 2:
                issues.append(f'{name} needs both classes for prespecified AP tuning/fit')
        if not len(test):
            issues.append('empty test block')
        for name, idx in [('tuning_train',train),('validation',val),('refit',refit),('test',test)]:
            positives = int(df.loc[idx,'registry_event_365'].sum())
            if 0 < positives < 10:
                diagnostic_warnings.append(f'{name}: only {positives} positive filing windows; count is not independent events, tuning/metrics can be unstable')
        splits.append({'block':f'{start_year}_{end_year}', 'test_start':start,
                       'validation_start':val_start, 'validation_year':start_year-3,
                       'indices': {'tuning_train':train, 'validation':val, 'refit':refit, 'test':test},
                       'counts':{name:subset_summary(df.loc[idx]) for name,idx in
                                 [('tuning_train',train),('validation',val),('refit',refit),('test',test)]},
                       'issues':issues,'diagnostic_warnings':diagnostic_warnings})
    return splits


def model_grid(name):
    if name == 'LR':
        return [{'C': c} for c in [0.01, 0.1, 1.0, 10.0]]
    return [{'num_leaves':n, 'min_child_samples':m} for n in [7, 15] for m in [30, 60]]


def fit_model(name, params, x, y, weights, threads):
    if name == 'LR':
        model = LogisticRegression(C=params['C'], solver='lbfgs', max_iter=3000,
                                   tol=1e-7, random_state=SEED)
    else:
        model = LGBMClassifier(objective='binary', n_estimators=300, learning_rate=0.05,
                               num_leaves=params['num_leaves'],
                               min_child_samples=params['min_child_samples'],
                               deterministic=True, force_col_wise=True, device_type='cpu',
                               n_jobs=threads, random_state=SEED, verbosity=-1,
                               subsample=1.0, colsample_bytree=1.0)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        model.fit(x, y, sample_weight=normalized_weights(weights))
    messages = [str(w.message) for w in caught]
    converged = not any(issubclass(w.category, ConvergenceWarning) for w in caught)
    return model, messages, converged


def prediction_frame(df, idx, p, selected, block, model, version, stage, candidate=None):
    cols = ['row_id'] + META_COLUMNS + ['mature_date'] + [c for c in OPTIONAL_META if c in df]
    out = df.loc[idx, cols].copy()
    out['block'] = block
    out['model'] = model
    out['version'] = version
    out['stage'] = stage
    out['candidate'] = candidate
    out['prediction'] = p
    out['pred'] = p
    out['label'] = out['registry_event_365']
    out['inclusion_probability'] = 1.0/out['sample_weight']
    out['certainty'] = out['sampling_stratum'].eq('certainty')
    out['retrospective_selection_fraction_at_5percent'] = selected
    return out


def run_models(df, splits, prefix, threads):
    logpath = Path(str(prefix)+'_tuning.jsonl')
    logpath.touch(exist_ok=False)
    prep_records=[]; test_predictions=[]; validation_predictions=[]; metric_records=[]
    frozen_predictions=[]; frozen_metrics=[]; frozen_differences=[]
    frozen_versioned={
        'predictions':Path(str(prefix)+'_frozen_a_predictions.parquet'),
        'metrics':Path(str(prefix)+'_frozen_a_metrics.csv'),
        'differences':Path(str(prefix)+'_frozen_a_paired_differences.csv'),
    }
    frozen_canonical={
        'predictions':prefix.parent/'models_frozen_a_predictions.parquet',
        'metrics':prefix.parent/'models_frozen_a_metrics.csv',
        'differences':prefix.parent/'models_frozen_a_paired_differences.csv',
    }
    def append_log(row):
        with logpath.open('a',encoding='utf-8') as f:
            f.write(json.dumps(clean_json(row),ensure_ascii=False,allow_nan=False)+'\n')
        print(json.dumps(clean_json({k:row.get(k) for k in ['stage','block','model','version','candidate','status']})), flush=True)
    for split in splits:
        block=split['block']; ids=split['indices']
        require(not split['issues'], f'Block {block} preflight issues: {split["issues"]}')
        tr, va, re, te = [ids[k] for k in ['tuning_train','validation','refit','test']]
        # Store the weighted mature-training prevalence baseline once per block.
        baseline=float(np.average(df.loc[re,'registry_event_365'], weights=df.loc[re,'sample_weight']))
        pb=np.full(len(te),baseline)
        mb,sb=evaluate(df.loc[te,'registry_event_365'],pb,df.loc[te,'sample_weight'])
        metric_records.append({'block':block,'model':'PREVALENCE','version':'shared',**mb})
        test_predictions.append(prediction_frame(df,te,pb,sb,block,'PREVALENCE','shared','test'))
        for version in ['A','B']:
            raw=df[[version+'_'+f for f in FEATURES]+COMMON_FEATURES].to_numpy(dtype=float)
            for name in ['LR','LGBM']:
                prep=WeightedPreprocessor(scale=name=='LR').fit(raw[tr],df.loc[tr,'sample_weight'])
                xtr,xva=prep.transform(raw[tr]),prep.transform(raw[va])
                prep_records.append({'block':block,'model':name,'version':version,'stage':'tuning',
                                     'training':subset_summary(df.loc[tr]),'parameters':prep.manifest()})
                write_json(str(prefix)+'_preprocessing.json',prep_records)
                candidates=[]
                for number,params in enumerate(model_grid(name)):
                    start_time=time.perf_counter()
                    row={'block':block,'model':name,'version':version,'stage':'tuning',
                         'candidate':number,'parameters':params,'fit_weight_normalization':'mean1',
                         'n_train':len(tr),'n_validation':len(va)}
                    try:
                        model,messages,converged=fit_model(name,params,xtr,df.loc[tr,'registry_event_365'],
                                                         df.loc[tr,'sample_weight'],threads)
                        pred=model.predict_proba(xva)[:,1]
                        metrics,selected=evaluate(df.loc[va,'registry_event_365'],pred,
                                                  df.loc[va,'sample_weight'],calibration=False)
                        row['warnings'] = messages
                        require(converged,'Convergence warning: candidate is not eligible for selection')
                        require(np.isfinite(metrics['average_precision']),'Undefined validation AP')
                        row.update(status='ok',warnings=messages,metrics=metrics)
                        candidates.append((metrics['average_precision'],number,params))
                        validation_predictions.append(prediction_frame(df,va,pred,selected,block,name,version,'validation',number))
                        pd.concat(validation_predictions,ignore_index=True).to_parquet(str(prefix)+'_validation_predictions.parquet',index=False)
                    except Exception as exc:
                        row.update(status='failed',error=repr(exc))
                    row['elapsed_seconds']=time.perf_counter()-start_time
                    append_log(row)
                require(len(candidates)==len(model_grid(name)),
                        f'Incomplete prespecified tuning grid for {block}/{version}/{name}; inspect log, do not silently choose among fewer fits')
                # Exact AP ties: choose the first entry in the prespecified grid.
                best=max(candidates,key=lambda t:(t[0],-t[1]))
                _,best_number,best_params=best
                prep_final=WeightedPreprocessor(scale=name=='LR').fit(raw[re],df.loc[re,'sample_weight'])
                xre,xte=prep_final.transform(raw[re]),prep_final.transform(raw[te])
                started=time.perf_counter()
                model,messages,converged=fit_model(name,best_params,xre,df.loc[re,'registry_event_365'],
                                                   df.loc[re,'sample_weight'],threads)
                require(converged,f'Final fit did not converge: {block}/{version}/{name}')
                pred=model.predict_proba(xte)[:,1]
                metrics,selected=evaluate(df.loc[te,'registry_event_365'],pred,df.loc[te,'sample_weight'])
                metric_records.append({'block':block,'model':name,'version':version,
                                       'selected_candidate':best_number,'selected_parameters':json.dumps(best_params),**metrics})
                test_predictions.append(prediction_frame(df,te,pred,selected,block,name,version,'test',best_number))
                if version=='A':
                    # Prespecified diagnostic: same A estimator AND A preprocessing.
                    # This is inference only, not another hyperparameter search or fit.
                    raw_b=df[['B_'+f for f in FEATURES]+COMMON_FEATURES].to_numpy(dtype=float)
                    pred_b_frozen=model.predict_proba(prep_final.transform(raw_b[te]))[:,1]
                    metrics_b_frozen,selected_b_frozen=evaluate(
                        df.loc[te,'registry_event_365'],pred_b_frozen,df.loc[te,'sample_weight'])
                    for scenario,input_version,prob,selection,measures in [
                        ('A_model_A_inputs','A',pred,selected,metrics),
                        ('A_model_B_inputs','B',pred_b_frozen,selected_b_frozen,metrics_b_frozen),
                    ]:
                        fr=prediction_frame(df,te,prob,selection,block,name,input_version,
                                            'frozen_a_input_diagnostic',best_number)
                        fr['scenario']=scenario;fr['run_id']=prefix.name
                        frozen_predictions.append(fr)
                        frozen_metrics.append({'run_id':prefix.name,'block':block,'model':name,
                                               'scenario':scenario,'version':input_version,
                                               'training_version':'A','preprocessing_version':'A',
                                               'selected_candidate':best_number,**measures})
                    wtest=df.loc[te,'sample_weight'].to_numpy()
                    difference={'run_id':prefix.name,'block':block,'model':name,
                                'contrast':'A_model_B_inputs_minus_A_model_A_inputs',
                                'selection_fraction_weighted_jaccard':float(
                                    np.dot(wtest,np.minimum(selected,selected_b_frozen))/
                                    np.dot(wtest,np.maximum(selected,selected_b_frozen)))}
                    for measure in ['average_precision','brier','roc_auc',
                                    'retrospective_recall_at_5percent','calibration_intercept','calibration_slope']:
                        difference[measure+'_difference']=metrics_b_frozen[measure]-metrics[measure]
                    frozen_differences.append(difference)
                    pd.concat(frozen_predictions,ignore_index=True).to_parquet(frozen_versioned['predictions'],index=False)
                    pd.DataFrame(frozen_metrics).to_csv(frozen_versioned['metrics'],index=False,encoding='utf-8-sig')
                    pd.DataFrame(frozen_differences).to_csv(frozen_versioned['differences'],index=False,encoding='utf-8-sig')
                    for key in frozen_versioned:
                        shutil.copyfile(frozen_versioned[key],frozen_canonical[key])
                    append_log({'block':block,'model':name,'version':'A',
                                'stage':'frozen_input_diagnostic','candidate':best_number,
                                'status':'ok','additional_training_fits':0,'n_test':len(te),
                                'preprocessing_version':'A','source_test_prediction_version':'B',
                                'metrics':metrics_b_frozen})
                prep_records.append({'block':block,'model':name,'version':version,'stage':'final',
                                     'training':subset_summary(df.loc[re]),'parameters':prep_final.manifest()})
                artifact=Path(str(prefix)+f'_{block}_{version}_{name}.joblib')
                joblib.dump({'model':model,'preprocessing':clean_json(prep_final.manifest()),'features':MODEL_FEATURES,
                             'parameters':best_params,'block':block,'version':version,
                             'preprocessing_loader':'WeightedPreprocessor.from_manifest(artifact["preprocessing"])',
                             'note':'Diagnostic only. B uses subsequent disclosures; not deployable.'},artifact)
                append_log({'block':block,'model':name,'version':version,'stage':'final',
                            'candidate':best_number,'parameters':best_params,'status':'ok',
                            'n_train':len(re),'n_test':len(te),'warnings':messages,
                            'elapsed_seconds':time.perf_counter()-started,'artifact':str(artifact),
                            'artifact_sha256':sha256(artifact)})
                # Checkpoint completed results after each final fit.
                pd.concat(test_predictions,ignore_index=True).to_parquet(str(prefix)+'_test_predictions.parquet',index=False)
                pd.concat(validation_predictions,ignore_index=True).to_parquet(str(prefix)+'_validation_predictions.parquet',index=False)
                pd.DataFrame(metric_records).to_csv(str(prefix)+'_metrics.csv',index=False,encoding='utf-8-sig')
                write_json(str(prefix)+'_preprocessing.json',prep_records)
    metrics_df=pd.DataFrame(metric_records)
    predictions=pd.concat(test_predictions,ignore_index=True)
    deltas=[]
    for split in splits:
        block=split['block']; block_ap={}
        for model in ['LR','LGBM']:
            ma=metrics_df.query('block == @block and model == @model and version == "A"').iloc[0]
            mb=metrics_df.query('block == @block and model == @model and version == "B"').iloc[0]
            pa=predictions.query('block == @block and model == @model and version == "A"').set_index('row_id')
            pb=predictions.query('block == @block and model == @model and version == "B"').set_index('row_id').loc[pa.index]
            require(pa.index.equals(pb.index),'A/B prediction row alignment failed')
            require(np.array_equal(pa.registry_event_365,pb.registry_event_365),'A/B labels changed')
            require(np.array_equal(pa.sample_weight,pb.sample_weight),'A/B evaluation weights changed')
            sa=pa.retrospective_selection_fraction_at_5percent.to_numpy()
            sb=pb.retrospective_selection_fraction_at_5percent.to_numpy()
            w=pa.sample_weight.to_numpy()
            overlap=float(np.dot(w,np.minimum(sa,sb))/np.dot(w,np.maximum(sa,sb)))
            row={'block':block,'model':model,'contrast':'B_minus_A',
                 'selection_fraction_weighted_jaccard':overlap}
            for metric in ['average_precision','brier','roc_auc','retrospective_recall_at_5percent',
                           'calibration_intercept','calibration_slope']:
                row[metric+'_difference']=float(mb[metric]-ma[metric])
            block_ap[model]=[ma.average_precision,mb.average_precision]
            deltas.append(row)
        deltas.append({'block':block,'model':'LGBM_minus_LR_interaction','contrast':'(LGBM-LR)_B-(LGBM-LR)_A',
                       'average_precision_difference':(block_ap['LGBM'][1]-block_ap['LR'][1])-(block_ap['LGBM'][0]-block_ap['LR'][0])})
    pd.DataFrame(deltas).to_csv(str(prefix)+'_paired_differences.csv',index=False,encoding='utf-8-sig')
    return {'main_fits_completed':12,'tuning_fits_completed':48,'prevalence_baselines':3,
            'test_prediction_rows':len(predictions),
            'frozen_a_diagnostic':{'additional_training_fits':0,
                                   'scenarios':['A_model_A_inputs','A_model_B_inputs'],
                                   'versioned_outputs':{k:{'path':str(p),'sha256':sha256(p)} for k,p in frozen_versioned.items()},
                                   'latest_alias_outputs':{k:str(p) for k,p in frozen_canonical.items()}},
            'confidence_intervals':'not implemented; separate design-aware stage'}


def hash_binding_self_test():
    """Synthetic byte-file fixtures only; never read the real cohort or gate."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    fixture = require_d_path(ROOT / 'results' / ('models_hash_binding_toy_' + stamp))
    (fixture / 'datasets').mkdir(parents=True, exist_ok=False)
    (fixture / 'results').mkdir()
    main_path = fixture / 'datasets/model_cohort.parquet'
    facts_path = fixture / 'datasets/vintage_facts.parquet'
    sensitivity_path = fixture / 'datasets/sensitivity_source_scale_corrected.parquet'
    transition_path = fixture / 'datasets/sensitivity_no_transition.parquet'
    protocol_path = fixture / 'phase2_protocol.json'
    audit_path = fixture / 'results/final_data_gate.json'
    design_path = fixture / 'results/sensitivity_design.json'
    # These files are conspicuously synthetic bytes, not disguised real data.
    main_bytes = b'SYNTHETIC HASH FIXTURE MAIN; NOT A PARQUET FILE'
    fact_bytes = b'SYNTHETIC HASH FIXTURE FACTS; NOT A PARQUET FILE'
    main_path.write_bytes(main_bytes); facts_path.write_bytes(fact_bytes)
    sensitivity_path.write_bytes(b'SYNTHETIC CORRECTED INPUT; NOT A PARQUET FILE')
    transition_path.write_bytes(b'SYNTHETIC TRANSITION INPUT; NOT A PARQUET FILE')
    main_hash, fact_hash = sha256(main_path), sha256(facts_path)
    protocol = {'data_gate': {'training_allowed_now': True, 'cohort_sha256': main_hash,
                              'audit': 'results/final_data_gate.json'}}
    audit = {'status': 'PASS', 'issues': [], 'cohort_sha256': main_hash,
             'fact_table_sha256': fact_hash}
    design = {'status': 'complete', 'source_files_unchanged': True,
              'main_sha256': main_hash, 'facts_sha256': fact_hash,
              'sources': {'main': {'path': str(main_path), 'sha256': main_hash},
                          'facts': {'path': str(facts_path), 'sha256': fact_hash}},
              'S1': {'training_may_be_skipped_as_equivalent': False},
              'S2': {'skip_training': False},
              'outputs': {'source_scale_corrected': {'path': str(sensitivity_path), 'sha256': sha256(sensitivity_path)},
                          'no_transition': {'path': str(transition_path), 'sha256': sha256(transition_path)}}}
    write_json(protocol_path, protocol); write_json(audit_path, audit); write_json(design_path, design)
    checks = []
    def rejected(source, expected_fragment, current_protocol=None):
        try:
            verify_training_binding(source, protocol_path, current_protocol or protocol)
        except ValueError as exc:
            require(expected_fragment in str(exc), f'Unexpected binding rejection: {exc}')
            checks.append(expected_fragment)
        else:
            raise AssertionError('Modified or unauthorized training input was accepted')
    require(verify_training_binding(main_path, protocol_path, protocol)['input_kind'] == 'gated_main_cohort',
            'Valid main gate was rejected')
    require(verify_training_binding(sensitivity_path, protocol_path, protocol)['sensitivity'] == 'source_scale_corrected',
            'Valid source correction was rejected')
    require(verify_training_binding(transition_path, protocol_path, protocol)['sensitivity'] == 'no_transition',
            'Valid transition sensitivity was rejected')
    bad_protocol = json.loads(json.dumps(protocol)); bad_protocol['data_gate']['training_allowed_now'] = False
    rejected(main_path, 'explicitly true', bad_protocol)
    main_path.write_bytes(b'SYNTHETIC ALTERED MAIN')
    rejected(main_path, 'current main cohort hash differs')
    rejected(sensitivity_path, 'current main cohort hash differs')
    main_path.write_bytes(main_bytes)
    audit['status'] = 'FAIL'; write_json(audit_path, audit)
    rejected(main_path, 'latest gate audit did not pass')
    audit['status'] = 'PASS'; audit['cohort_sha256'] = '0' * 64; write_json(audit_path, audit)
    rejected(main_path, 'protocol and audit cohort hashes disagree')
    audit['cohort_sha256'] = main_hash; write_json(audit_path, audit)
    design['status'] = 'incomplete'; write_json(design_path, design)
    rejected(sensitivity_path, 'generation is not complete')
    design['status'] = 'complete'; design['main_sha256'] = '0' * 64; write_json(design_path, design)
    rejected(sensitivity_path, 'generated from a different main cohort')
    design['main_sha256'] = main_hash
    original_output_hash = design['outputs']['source_scale_corrected']['sha256']
    design['outputs']['source_scale_corrected']['sha256'] = '0' * 64; write_json(design_path, design)
    rejected(sensitivity_path, 'output hash differs')
    design['outputs']['source_scale_corrected']['sha256'] = original_output_hash; write_json(design_path, design)
    facts_path.write_bytes(b'SYNTHETIC ALTERED FACTS')
    rejected(sensitivity_path, 'fact source changed')
    facts_path.write_bytes(fact_bytes)
    design['S2']['skip_training'] = True; write_json(design_path, design)
    rejected(transition_path, 'equivalent to main')
    design['S2']['skip_training'] = False; write_json(design_path, design)
    unknown = fixture / 'datasets/unrecorded.parquet'; unknown.write_bytes(main_bytes)
    rejected(unknown, 'no unique recorded sensitivity output')
    result = {'status': 'pass', 'valid_bindings_accepted': 3,
              'failure_paths_rejected': len(checks), 'rejected_conditions': checks,
              'fixture_directory': str(fixture), 'real_data_read': False, 'models_fitted': 0}
    write_json(fixture / 'binding_test_summary.json', result)
    return result


def self_test():
    # Weighted median differs from unweighted; unseen values cannot change fit.
    x=np.array([[0.,np.nan],[10.,np.nan],[100.,np.nan]])
    w=np.array([8.,1.,1.])
    pp=WeightedPreprocessor(scale=True).fit(x,w)
    require(pp.median_[0]==0,'Weighted median self-test failed')
    require(pp.all_missing_[1],'All-missing column self-test failed')
    before=pp.median_.copy()
    z=pp.transform(np.array([[1e9,99.],[np.nan,np.nan]]))
    require(np.isfinite(z).all() and np.array_equal(before,pp.median_), 'Transform altered fit')
    # Weighted metrics equal integer row replication; ties must be order-free.
    y=np.array([0,1,0,1]);p=np.array([.1,.2,.6,.6]);w=np.array([5.,1.,2.,2.])
    metrics,selection=evaluate(y,p,w,calibration=False)
    idx=np.repeat(np.arange(len(y)),w.astype(int))
    require(np.isclose(metrics['average_precision'],average_precision_score(y[idx],p[idx])), 'Weighted AP replication failed')
    require(np.isclose(metrics['brier'],np.mean((p[idx]-y[idx])**2)), 'Weighted Brier replication failed')
    permutation=np.array([3,1,2,0])
    recall,selected=recall_at_weighted_capacity(y[permutation],p[permutation],w[permutation])
    require(np.isclose(recall,metrics['retrospective_recall_at_5percent']), 'Tie-order dependence')
    require(np.allclose(selected[np.argsort(permutation)],selection),'Selection tie invariance failed')
    require(np.isclose(np.dot(w,selection),.05*w.sum()), 'Capacity not respected')
    # Maturity boundary is inclusive; a row maturing one day later is excluded.
    dates=pd.Series(pd.to_datetime(['2011-10-04','2011-10-05','2013-01-02','2014-10-03','2016-01-01']))
    mature=dates+pd.Timedelta(days=455)
    boundary=pd.Timestamp('2013-01-01')
    require(mature.iloc[0]==boundary and mature.iloc[1]>boundary,'Calendar maturity fixture is incorrect')
    # Constant-probability calibration slope is unidentifiable, not fabricated.
    cal=calibration_diagnostics(y,np.repeat(.2,4),w)
    require(np.isnan(cal['calibration_slope']),'Constant calibration slope should be undefined')
    # Schema and split checks include positive and negative windows in each year.
    rows=[]
    for year in range(2010,2022):
        for event in [0,1]:
            decision=pd.Timestamp(year,6,15)
            filing=decision-pd.Timedelta(days=1)
            fiscal=pd.Timestamp(year-1,12,31)
            row={'cik':f'{year}{event}','cluster_id':f'cluster_{year}_{event}',
                 'accession':f'synthetic_{year}_{event}','decision_date':decision,
                 'filing_date':filing,'fiscal_end':fiscal,'pre_first_registry_event':True,
                 'registry_event_365':event,
                 'first_registry_event':decision+pd.Timedelta(days=180) if event else pd.NaT,
                 'report_lag_days':(filing-fiscal).days,'n_original_facts':10,
                 'sample_weight':1.0 if event else 20.0,
                 'sampling_stratum':'certainty' if event else 'noncase_srs'}
            for j,f in enumerate(FEATURES):
                row['A_'+f]=float(j+event);row['B_'+f]=float(j+event)+0.1
            rows.append(row)
    toy=validate_cohort(pd.DataFrame(rows))
    splits=make_splits(toy)
    require(all(not s['issues'] for s in splits),'Synthetic folds unexpectedly unavailable')
    for s in splits:
        require(toy.loc[s['indices']['tuning_train'],'mature_date'].le(s['validation_start']).all(),
                'Validation training uses immature labels')
        require(toy.loc[s['indices']['refit'],'mature_date'].le(s['test_start']).all(),
                'Final training uses immature labels')
    corrupt=pd.DataFrame(rows);corrupt.loc[0,'registry_event_365']=1
    try:
        validate_cohort(corrupt)
    except ValueError as exc:
        require('conflicts' in str(exc),'Unexpected label corruption rejection')
    else:
        raise AssertionError('Corrupt supplied label was not rejected')
    # The real cohort is never loaded. Verify installed LR/LGBM fit interfaces.
    rng=np.random.default_rng(SEED)
    xx=rng.normal(size=(160,len(MODEL_FEATURES)))
    yy=(xx[:,0]+0.3*xx[:,1]>0).astype(int)
    ww=np.where(yy==1,1.0,7.0)
    synthetic_fit_notes=[]
    for name in ['LR','LGBM']:
        prep=WeightedPreprocessor(scale=name=='LR').fit(xx[:128],ww[:128])
        model,messages,converged=fit_model(name,model_grid(name)[0],prep.transform(xx[:128]),
                                          yy[:128],ww[:128],threads=1)
        prob=model.predict_proba(prep.transform(xx[128:]))[:,1]
        require(converged and len(prob)==32 and np.isfinite(prob).all(),f'{name} synthetic interface failed')
        restored=WeightedPreprocessor.from_manifest(clean_json(prep.manifest()))
        require(np.array_equal(prep.transform(xx[128:]),restored.transform(xx[128:])),
                'Serialized preprocessing reconstruction changed feature values')
        synthetic_fit_notes.append({'model':name,'n_train':128,'n_test':32,'warnings':messages})
    return {'status':'passed','real_data_models_fitted':0,'synthetic_model_interface_fits':synthetic_fit_notes,
            'hash_binding_self_test':hash_binding_self_test(),
            'checks':['weighted median','all-missing feature','transform immutability',
                      'weighted AP/Brier versus integer replication','score tie invariance',
                      'weighted capacity','inclusive 455-day maturity','calibration identifiability',
                      'cohort schema and first-event label consistency','validation and test label maturity',
                      'corrupt label rejected','installed LR and LGBM weighted-fit interfaces']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'datasets/model_cohort.parquet')
    parser.add_argument('--protocol',type=Path,default=ROOT/'phase2_protocol.json')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results')
    parser.add_argument('--threads',type=int,default=4)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--run',action='store_true',help='Fit only when protocol data gate explicitly permits')
    mode.add_argument('--dry-run',action='store_true',help='Preflight only (also the default)')
    mode.add_argument('--self-test',action='store_true',help='Synthetic checks including two model smoke fits; no real-data access')
    args=parser.parse_args()
    out=require_d_path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    require(1<=args.threads<=8,'Threads must be between 1 and 8')
    require(shutil.disk_usage(out).free>=1024**3,'D: has less than 1 GiB free')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    prefix=out/('models_'+stamp)
    manifest={'started_utc':datetime.now(timezone.utc).isoformat(),'mode':'run' if args.run else 'preflight',
              'source_script':str(Path(__file__).resolve()),'source_script_sha256':sha256(__file__),
              'python':sys.version,'platform':platform.platform(),
              'versions':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','scikit-learn','lightgbm','pyarrow','joblib']},
              'vintage_features':FEATURES,'common_features':COMMON_FEATURES,
              'features':MODEL_FEATURES,'n_missing_indicators':len(MODEL_FEATURES),'blocks':BLOCKS,
              'seed':SEED,'threads':args.threads,'horizon_days':HORIZON_DAYS,'label_grace_days':LABEL_GRACE_DAYS,
              'calibration_definition':'test diagnostic only; intercept with slope=1, joint intercept/slope reported separately',
              'weighted_capacity_definition':'retrospective 5% weighted mass; boundary score ties split uniformly',
              'frozen_a_diagnostic':'Fixed final A estimator and preprocessing applied to both test versions; zero additional training fits, separate outputs',
              'limitations':['No confidence intervals yet','Sampling cofiling clusters are not assumed to be legal corporate groups',
                             'B is a deliberate future-vintage diagnostic, never a deployment model',
                             'The module validates supplied labels and weights but does not establish registry coverage or sampling probabilities']}
    manifest_path=Path(str(prefix)+'_manifest.json')
    try:
        if args.self_test:
            manifest.update(mode='synthetic_self_test',**self_test())
        else:
            source=require_d_path(args.input);protocol_path=require_d_path(args.protocol)
            require(source.is_file(),f'Input cohort not ready: {source}')
            protocol=json.loads(protocol_path.read_text(encoding='utf-8'))
            manifest.update(input=str(source),input_sha256=sha256(source),
                            protocol=str(protocol_path),protocol_sha256=sha256(protocol_path),
                            data_gate_training_allowed=protocol.get('data_gate',{}).get('training_allowed_now') is True)
            if args.run:
                manifest['training_binding'] = verify_training_binding(source, protocol_path, protocol)
                require(manifest['training_binding']['input_sha256'] == manifest['input_sha256'],
                        'Training blocked: input changed before cohort loading')
            df=validate_cohort(pd.read_parquet(source))
            splits=make_splits(df)
            manifest['cohort']=subset_summary(df)
            manifest['split_manifest']=[{k:v for k,v in s.items() if k!='indices'} for s in splits]
            membership=[]
            for s in splits:
                for role,idx in s['indices'].items():
                    rows=df.loc[idx,['row_id','cik','cluster_id','accession','decision_date','mature_date','sampling_stratum','sample_weight']].copy()
                    rows['block']=s['block'];rows['role']=role;membership.append(rows)
            pd.concat(membership,ignore_index=True).to_parquet(str(prefix)+'_split_membership.parquet',index=False)
            if args.run:
                require(manifest['data_gate_training_allowed'],
                        'Training blocked: protocol.data_gate.training_allowed_now must be explicitly true')
                require(not any(s['issues'] for s in splits), 'Split preflight failed; inspect manifest')
                require(sha256(protocol_path) == manifest['protocol_sha256'],
                        'Training blocked: protocol changed during preflight')
                binding_now = verify_training_binding(source, protocol_path,
                                                       json.loads(protocol_path.read_text(encoding='utf-8')))
                require(binding_now == manifest['training_binding'],
                        'Training blocked: input or gate/design identity changed during preflight')
                manifest.update(status='running');write_json(manifest_path,manifest)
                manifest.update(run_models(df,splits,prefix,args.threads),status='completed')
            else:
                manifest.update(status='preflight_completed',prediction_models_fitted=0,
                                all_splits_fit_ready=not any(s['issues'] for s in splits))
    except Exception as exc:
        manifest.update(status='failed_or_blocked',error=repr(exc),traceback=traceback.format_exc())
        write_json(manifest_path,manifest)
        print(json.dumps(clean_json({'status':manifest['status'],'error':str(exc),'manifest':str(manifest_path)})),flush=True)
        return 1
    manifest['finished_utc']=datetime.now(timezone.utc).isoformat()
    write_json(manifest_path,manifest)
    print(json.dumps(clean_json({'status':manifest['status'],'manifest':str(manifest_path)})),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
