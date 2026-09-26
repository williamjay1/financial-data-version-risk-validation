"""Post hoc revision analyses; original data/code/results remain read-only.

CLI: python revision_models.py --plan | --self-test | --run
Import API: fit_pipeline, score_pipeline, run_fixed_cohort, base, load_base.
All fitted preprocessing is training-only; two CPU threads; no test selection.
"""
from __future__ import annotations
import os
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
os.environ.setdefault('MKL_NUM_THREADS', '2')
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import argparse, hashlib, importlib.util, json, time, warnings, traceback
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import SplineTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
REVISION = ROOT / 'revision_20260922'
OUT = REVISION / 'results/models'
EXPECTED_HASH = '724122d3ca7a0a123de244112aa604d6da7a008497cc6ce526f8f07327916e21'
ORIGINAL_PREFIX = ROOT / 'results/models_20260921T093517075175Z'
NO_TRANSITION_PREFIX = ROOT / 'results/sensitivity_no_transition/models_20260921T093617432022Z'
_spec = importlib.util.spec_from_file_location('vintage_base_readonly', ROOT/'scripts/run_vintage_models.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
SEED, THREADS = base.SEED, 2
FIXED = {'LR': {'C': 1.0}, 'LGBM': {'num_leaves': 7, 'min_child_samples': 30},
         'SPLINE_LR': {'C': 1.0, 'degree': 3, 'knot_quantiles': [.05,.35,.65,.95]},
         'RF': {'n_estimators': 400, 'max_depth': 6, 'min_samples_leaf': 20,
                'max_features': 'sqrt', 'bootstrap': True}}


def load_base():
    source = ROOT/'datasets/model_cohort.parquet'
    protocol_path = ROOT/'phase2_protocol.json'
    binding = base.verify_training_binding(source, protocol_path, json.loads(protocol_path.read_text(encoding='utf-8')))
    base.require(binding['input_sha256'] == EXPECTED_HASH, 'Revision frozen main hash mismatch')
    return base.validate_cohort(pd.read_parquet(source)), binding


def matrix(df, idx, version, feature_set='full'):
    z = df.loc[idx, [version+'_'+f for f in base.FEATURES]].to_numpy(dtype=float)
    lag = df.loc[idx, ['report_lag_days']].to_numpy(dtype=float)
    if feature_set == 'full': return np.column_stack([z, lag])
    if feature_set == 'size': return z[:, [0]]
    if feature_set == 'missing': return np.isnan(z).astype(float)
    if feature_set == 'size_missing_lag': return np.column_stack([z[:,0], lag[:,0], np.isnan(z).astype(float)])
    raise ValueError(feature_set)


def input_names(feature_set):
    if feature_set == 'full': return base.MODEL_FEATURES
    if feature_set == 'size': return ['log_assets']
    if feature_set == 'missing': return ['missing_'+f for f in base.FEATURES]
    return ['log_assets','report_lag_days'] + ['missing_'+f for f in base.FEATURES]


def _prep_fit(x, w, learner, feature_set):
    if feature_set == 'missing':
        return x.copy(), {'kind': 'identity', 'input_names': input_names(feature_set)}
    # Missingness indicators in diagnostic designs remain binary and are not winsorized.
    n_numeric = 2 if feature_set == 'size_missing_lag' else x.shape[1]
    pp = base.WeightedPreprocessor(scale=learner == 'LR').fit(x[:,:n_numeric], w)
    state = base.clean_json(pp.manifest())
    names = input_names(feature_set)[:n_numeric]
    state['output_order'] = names + ['missing_'+f for f in names]
    z = pp.transform(x[:,:n_numeric])
    kind = 'full'
    if feature_set in ('size', 'size_missing_lag'):
        z = z[:,:n_numeric]
        if feature_set == 'size_missing_lag': z = np.column_stack([z, x[:,n_numeric:]])
        kind = 'numeric_then_explicit_flags'
    prep = {'kind': kind, 'base': state, 'n_numeric': n_numeric, 'input_names': input_names(feature_set)}
    if learner != 'SPLINE_LR': return z, prep
    base.require(feature_set == 'full', 'Spline diagnostic requires full feature set')
    transforms, blocks, output_names = [], [], []
    for j, name in enumerate(base.MODEL_FEATURES):
        knots = np.unique([base.weighted_quantile(z[:,j], w, q) for q in FIXED['SPLINE_LR']['knot_quantiles']])
        if len(knots) < 2:
            transforms.append(None); blocks.append(z[:,[j]]); output_names.append(name+'__linear_constant')
        else:
            transform = SplineTransformer(knots=knots.reshape(-1,1), degree=3,
                                           include_bias=False, extrapolation='linear')
            b = transform.fit_transform(z[:,[j]])
            transforms.append(transform); blocks.append(b)
            output_names += [name+'__basis_'+str(k) for k in range(b.shape[1])]
    blocks.append(z[:,len(base.MODEL_FEATURES):])
    output_names += ['missing_'+f for f in base.MODEL_FEATURES]
    expanded = np.column_stack(blocks)
    mean = np.average(expanded, axis=0, weights=w)
    sd = np.sqrt(np.average((expanded-mean)**2, axis=0, weights=w)); sd[sd<1e-12]=1
    prep.update(kind='spline', transforms=transforms, spline_mean=mean, spline_sd=sd,
                output_names=output_names,
                knot_values=[None if t is None else t.bsplines_[0].t[3:-3].tolist() for t in transforms])
    return (expanded-mean)/sd, prep


def _prep_transform(x, prep):
    if prep['kind'] == 'identity': return x.copy()
    pp = base.WeightedPreprocessor.from_manifest(prep['base'])
    z = pp.transform(x[:,:prep['n_numeric']])
    if prep['kind'] == 'numeric_then_explicit_flags':
        z = z[:,:prep['n_numeric']]
        if x.shape[1] > prep['n_numeric']: z = np.column_stack([z, x[:,prep['n_numeric']:]])
    if prep['kind'] != 'spline': return z
    blocks = [z[:,[j]] if t is None else t.transform(z[:,[j]]) for j,t in enumerate(prep['transforms'])]
    blocks.append(z[:,len(base.MODEL_FEATURES):])
    return (np.column_stack(blocks)-prep['spline_mean'])/prep['spline_sd']


def fit_pipeline(df, train_ids, version, learner, params=None, feature_set='full'):
    """Fit on explicit row indices. Caller must enforce temporal split and provenance.

    Returns a plain-dict serializable bundle; no reference to this module class.
    """
    idx = np.asarray(train_ids)
    base.require(len(idx)>0 and df.loc[idx,'registry_event_365'].nunique()==2, 'Training needs two outcome classes')
    params = dict(FIXED[learner] if params is None else params)
    x, y, w = matrix(df,idx,version,feature_set), df.loc[idx,'registry_event_365'].to_numpy(), df.loc[idx,'sample_weight'].to_numpy()
    start = time.perf_counter()
    z, prep = _prep_fit(x,w,learner,feature_set)
    with threadpool_limits(limits=THREADS):
        if learner in ('LR','LGBM'):
            model, messages, converged = base.fit_model(learner,params,z,y,w,THREADS)
        else:
            if learner == 'SPLINE_LR':
                model = LogisticRegression(C=params['C'],solver='lbfgs',max_iter=5000,tol=1e-7,random_state=SEED)
            elif learner == 'RF':
                model = RandomForestClassifier(**params,criterion='gini',n_jobs=THREADS,random_state=SEED,class_weight=None)
            else: raise ValueError(learner)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always'); model.fit(z,y,sample_weight=base.normalized_weights(w))
            messages=[str(warning.message) for warning in caught]
            converged=not any(issubclass(warning.category,ConvergenceWarning) for warning in caught)
    digest=hashlib.sha256(pd.util.hash_pandas_object(df.loc[idx,['row_id','registry_event_365','sample_weight']],index=False).values.tobytes()+x.tobytes()).hexdigest()
    return {'model':model,'preprocessing':prep,'learner':learner,'parameters':params,
            'feature_set':feature_set,'train_version':version,'train_row_ids':df.loc[idx,'row_id'].tolist(),
            'train_rows_features_labels_weights_sha256':digest,'train_summary':base.clean_json(base.subset_summary(df.loc[idx])),
            'warnings':messages,'converged':converged,'fit_elapsed_seconds':time.perf_counter()-start,
            'threads':THREADS,'frozen_main_sha256':EXPECTED_HASH}


def score_pipeline(bundle, df, score_ids, score_version):
    x = matrix(df,score_ids,score_version,bundle.get('feature_set','full'))
    if bundle.get('bundle_kind') == 'original_artifact':
        z = base.WeightedPreprocessor.from_manifest(bundle['preprocessing']).transform(x)
    else: z = _prep_transform(x,bundle['preprocessing'])
    with threadpool_limits(limits=THREADS), warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='X does not have valid feature names')
        return bundle['model'].predict_proba(z)[:,1]


def read_original(prefix, block, version, learner, expected_input):
    manifest_path=Path(str(prefix)+'_manifest.json')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    base.require(manifest.get('input_sha256') == expected_input, 'Original artifact cohort binding mismatch')
    path=Path(str(prefix)+f'_{block}_{version}_{learner}.joblib')
    logs=[json.loads(line) for line in Path(str(prefix)+'_tuning.jsonl').read_text(encoding='utf-8').splitlines()]
    log=[r for r in logs if r.get('stage')=='final' and r.get('block')==block and r.get('version')==version and r.get('model')==learner]
    base.require(len(log)==1, 'No unique original final fit hash record')
    base.require(base.sha256(path)==log[0]['artifact_sha256'], 'Original artifact hash mismatch')
    obj=joblib.load(path)
    obj.update(bundle_kind='original_artifact',feature_set='full',learner=learner,train_version=version,
               original_path=str(path),original_sha256=base.sha256(path),original_manifest_sha256=base.sha256(manifest_path))
    return obj


class Recorder:
    def __init__(self, output_dir):
        self.path=Path(output_dir); self.path.mkdir(parents=True,exist_ok=True)
        (self.path/'artifacts').mkdir(exist_ok=True)
        self.metrics=[]; self.predictions=[]; self.selection=[]; self.fits=[]; self.splits=[]; self.validation=[]

    def save_fit(self,bundle,experiment,block,version,learner,stage='final'):
        name=f'{experiment}__{block}__{version}__{learner}'
        path=self.path/'artifacts'/f'{name}.joblib'
        base.require(not path.exists(), f'Refusing to overwrite artifact {path}')
        joblib.dump(bundle,path)
        prep=bundle.get('preprocessing',{})
        serial_prep={k:v for k,v in prep.items() if k!='transforms'}
        self.fits.append({'experiment':experiment,'block':block,'version':version,'model':learner,'stage':stage,
                          'artifact':str(path),'sha256':base.sha256(path),'parameters':bundle.get('parameters'),
                          'train_summary':bundle.get('train_summary'),'training_input_digest':bundle.get('train_rows_features_labels_weights_sha256'),
                          'warnings':bundle.get('warnings',[]),'converged':bundle.get('converged',True),
                          'preprocessing':serial_prep,'elapsed_seconds':bundle.get('fit_elapsed_seconds'),
                          'original_artifact':bundle.get('original_path')})
        if learner=='SPLINE_LR':
            pd.DataFrame({'basis':prep['output_names'],'coefficient_standardized_basis':bundle['model'].coef_[0],
                          'basis_center':prep['spline_mean'],'basis_sd':prep['spline_sd']}).to_csv(self.path/'artifacts'/f'{name}_coefficients.csv',index=False)

    def score(self,bundle,df,idx,experiment,block,train_version,score_version,model):
        p=score_pipeline(bundle,df,idx,score_version)
        metrics, selected=base.evaluate(df.loc[idx,'registry_event_365'],p,df.loc[idx,'sample_weight'])
        keys={'experiment':experiment,'block':block,'model':model,'train_version':train_version,
              'score_version':score_version,'scenario':f'{train_version}_model_{score_version}_inputs',
              'feature_set':bundle.get('feature_set','full'),'analysis_status':'post_hoc_revision'}
        self.metrics.append({**keys,**metrics})
        pred=base.prediction_frame(df,idx,p,selected,block,model,score_version,'test')
        for key,value in keys.items(): pred[key]=value
        self.predictions.append(pred)
        return p

    def split(self,df,idx,experiment,block,stage,cutoff=None,validation_year=None):
        row={'experiment':experiment,'block':block,'stage':stage,'validation_year':validation_year,
             **base.subset_summary(df.loc[idx]),'fit_or_selection_cutoff':cutoff}
        if cutoff is not None:
            base.require(df.loc[idx,'mature_date'].le(cutoff).all(), f'Maturity violation {experiment}/{block}/{stage}')
            row['maturity_guard_pass']=True
        row['row_ids']=df.loc[idx,'row_id'].tolist()
        self.splits.append(row)

    def flush(self):
        metrics=pd.DataFrame(self.metrics); metrics.to_csv(self.path/'metrics.csv',index=False)
        if self.predictions: pd.concat(self.predictions,ignore_index=True).to_parquet(self.path/'predictions.parquet',index=False)
        if self.validation: pd.concat(self.validation,ignore_index=True).to_parquet(self.path/'validation_predictions.parquet',index=False)
        base.write_json(self.path/'selection.json',self.selection)
        base.write_json(self.path/'fit_preprocessing_audit.json',self.fits)
        base.write_json(self.path/'split_audit.json',self.splits)
        if len(metrics): four_cell_differences(metrics).to_csv(self.path/'four_cell_differences.csv',index=False)


def four_cell_differences(metrics):
    rows=[]
    names=['average_precision','brier','roc_auc','retrospective_recall_at_5percent']
    for keys,g in metrics.groupby(['experiment','block','model'],sort=False):
        cells={(r.train_version,r.score_version):r for _,r in g.iterrows()}
        if not all(k in cells for k in [('A','A'),('A','B'),('B','A'),('B','B')]): continue
        for name in names:
            aa,ab,ba,bb=[float(cells[k][name]) for k in [('A','A'),('A','B'),('B','A'),('B','B')]]
            rows.append(dict(zip(['experiment','block','model'],keys),metric=name,AA=aa,AB=ab,BA=ba,BB=bb,
                             input_substitution_A_fit=ab-aa,fit_difference_A_inputs=ba-aa,
                             procedural_interaction=bb-ba-ab+aa,total_refit_difference=bb-aa,
                             fit_difference_B_inputs=bb-ab))
    return pd.DataFrame(rows)


def run_fixed_cohort(df, output_dir, experiment, anchor_bundles=None, learners=('LR','LGBM'),
                     feature_set='full',development_filter=None,test_filter=None,recorder=None):
    """Fixed-config 2x2; accepts validated caller data, optionally immutable A anchors.

    Returns {(block, learner): A_bundle}. Caller owns capped-data provenance.
    If anchors are supplied, exact refit row IDs and A feature+label+weight digest
    must match; this prevents accidental reuse for different domains/weights.
    """
    rec=recorder or Recorder(output_dir); anchors={}
    for split in base.make_splits(df):
        block=split['block']; train=split['indices']['refit']; test=split['indices']['test']
        if development_filter is not None: train=train[np.asarray(development_filter)[train]]
        if test_filter is not None: test=test[np.asarray(test_filter)[test]]
        rec.split(df,train,experiment,block,'refit',split['test_start'])
        rec.split(df,test,experiment,block,'test')
        if not len(test) or df.loc[train,'registry_event_365'].nunique()!=2:
            rec.selection.append({'experiment':experiment,'block':block,'status':'not_estimable','reason':'Empty test or single-class refit'}); continue
        for learner in learners:
            versions=['A'] if feature_set!='full' else ['A','B']
            for version in versions:
                if version=='A' and anchor_bundles is not None:
                    bundle=anchor_bundles[(block,learner)]
                    x=matrix(df,train,'A',feature_set)
                    digest=hashlib.sha256(pd.util.hash_pandas_object(df.loc[train,['row_id','registry_event_365','sample_weight']],index=False).values.tobytes()+x.tobytes()).hexdigest()
                    base.require(bundle['train_rows_features_labels_weights_sha256']==digest,'A anchor input mismatch')
                    base.require(bundle['train_row_ids']==df.loc[train,'row_id'].tolist(),'A anchor training rows mismatch')
                else: bundle=fit_pipeline(df,train,version,learner,feature_set=feature_set)
                rec.save_fit(bundle,experiment,block,version,learner)
                if version=='A': anchors[(block,learner)]=bundle
                for score_version in versions: rec.score(bundle,df,test,experiment,block,version,score_version,learner)
    if recorder is None: rec.flush()
    return anchors


def validation_folds(df,split,rolling=False,development_filter=None):
    test_start=split['test_start']; year=test_start.year
    years=list(range(year-5,year-2)) if rolling else [year-3]
    folds=[]
    for val_year in years:
        start=pd.Timestamp(val_year,1,1); end=pd.Timestamp(val_year+1,1,1)
        tr=df.index[df.decision_date.lt(start)&df.mature_date.le(start)].to_numpy()
        va=df.index[df.decision_date.ge(start)&df.decision_date.lt(end)&df.mature_date.le(test_start)].to_numpy()
        if development_filter is not None:
            tr=tr[np.asarray(development_filter)[tr]]; va=va[np.asarray(development_filter)[va]]
        reason=[]
        for stage,ids in [('train',tr),('validation',va)]:
            if len(ids)==0: reason.append(stage+'_empty')
            elif df.loc[ids,'registry_event_365'].nunique()!=2: reason.append(stage+'_single_class')
        folds.append({'year':val_year,'start':start,'train':tr,'validation':va,'eligible':not reason,'reason':reason})
    return folds


def run_tuned(df,rec,experiment,rolling=False,development_filter=None):
    for split in base.make_splits(df):
        block=split['block']; folds=validation_folds(df,split,rolling,development_filter)
        for fold in folds:
            rec.split(df,fold['train'],experiment,block,'tuning_train',fold['start'],fold['year'])
            rec.split(df,fold['validation'],experiment,block,'validation',split['test_start'],fold['year'])
            rec.selection.append({'experiment':experiment,'block':block,'stage':'validation_year_eligibility',
                                  'year':fold['year'],'eligible':fold['eligible'],'reason':fold['reason']})
        eligible=[f for f in folds if f['eligible']]
        # A three-year design requires all three years: do not relabel one year as rolling evidence.
        if len(eligible)!=len(folds):
            rec.selection.append({'experiment':experiment,'block':block,'status':'not_estimable',
                                  'reason':'Not every prespecified validation year has two-class training and evaluation',
                                  'available_years':[f['year'] for f in eligible], 'required_years':[f['year'] for f in folds]})
            continue
        train=split['indices']['refit']; test=split['indices']['test']
        if development_filter is not None: train=train[np.asarray(development_filter)[train]]
        rec.split(df,train,experiment,block,'refit',split['test_start']); rec.split(df,test,experiment,block,'test')
        for learner in ['LR','LGBM']:
            for version in ['A','B']:
                candidates=[]
                for candidate,params in enumerate(base.model_grid(learner)):
                    scores=[]; failure=[]
                    for fold in eligible:
                        try:
                            bundle=fit_pipeline(df,fold['train'],version,learner,params)
                            p=score_pipeline(bundle,df,fold['validation'],version)
                            m,selection=base.evaluate(df.loc[fold['validation'],'registry_event_365'],p,
                                                      df.loc[fold['validation'],'sample_weight'],calibration=False)
                            ok=bundle['converged'] and np.isfinite(m['average_precision'])
                            if ok: scores.append(m['average_precision'])
                            else: failure.append('nonconvergence_or_undefined_AP')
                            record={'experiment':experiment,'block':block,'model':learner,'version':version,
                                    'candidate':candidate,'parameters':params,'year':fold['year'],
                                    'status':'ok' if ok else 'failed','metrics':m,'warnings':bundle['warnings'],
                                    'preprocessing':bundle['preprocessing'],
                                    'training_input_digest':bundle['train_rows_features_labels_weights_sha256']}
                            vp=base.prediction_frame(df,fold['validation'],p,selection,block,learner,version,'validation',candidate)
                            vp['experiment']=experiment; vp['validation_year']=fold['year']; rec.validation.append(vp)
                        except Exception as exc:
                            failure.append(str(exc)); record={'experiment':experiment,'block':block,'model':learner,
                                     'version':version,'candidate':candidate,'parameters':params,'year':fold['year'],
                                     'status':'failed','error':repr(exc)}
                        rec.selection.append(record)
                    candidates.append({'candidate':candidate,'parameters':params,'mean_yearly_AP':float(np.mean(scores)) if not failure and len(scores)==len(eligible) else None,
                                       'yearly_AP':scores,'failures':failure})
                valid=[c for c in candidates if c['mean_yearly_AP'] is not None]
                if not valid:
                    rec.selection.append({'experiment':experiment,'block':block,'model':learner,'version':version,
                                          'status':'not_estimable','reason':'All candidates failed; no test fallback'}); continue
                chosen=max(valid,key=lambda c:(c['mean_yearly_AP'],-c['candidate']))
                rec.selection.append({'experiment':experiment,'block':block,'model':learner,'version':version,'stage':'selection',
                                      'status':'selected','criterion':'equal-weight arithmetic mean of annual weighted AP',
                                      'chosen':chosen,'candidates':candidates,'tie_rule':'first candidate in original grid'})
                bundle=fit_pipeline(df,train,version,learner,chosen['parameters'])
                rec.save_fit(bundle,experiment,block,version,learner)
                for score_version in ['A','B']: rec.score(bundle,df,test,experiment,block,version,score_version,learner)


def run_saved(df,rec,experiment,prefix,expected_hash,test_filter=None):
    for split in base.make_splits(df):
        block=split['block']; idx=split['indices']['test']
        if test_filter is not None: idx=idx[np.asarray(test_filter)[idx]]
        rec.split(df,idx,experiment,block,'test')
        for learner in ['LR','LGBM']:
            for version in ['A','B']:
                bundle=read_original(prefix,block,version,learner,expected_hash)
                rec.save_fit(bundle,experiment,block,version,learner,stage='reused_original_fit')
                for score_version in ['A','B']: rec.score(bundle,df,idx,experiment,block,version,score_version,learner)


def transition_records(df):
    trans=df[df.form.eq('10-KT')].copy(); rows=[]
    for split in base.make_splits(df):
        for idx,row in trans.iterrows():
            entry=row.to_dict(); entry['block']=split['block']
            for stage,ids in split['indices'].items(): entry['in_original_'+stage]=bool(idx in set(ids))
            entry['removed_in_test_only']=entry['in_original_test']
            entry['removed_in_development_only']=any(entry['in_original_'+stage] for stage in ['tuning_train','validation','refit'])
            entry['missing_features']=';'.join(f for f in base.FEATURES if pd.isna(row['A_'+f]))
            entry['changed_A_B_features']=';'.join(f for f in base.FEATURES if pd.notna(row['A_'+f]) and row['A_'+f]!=row['B_'+f])
            entry['n_changed_A_B']=sum(pd.notna(row['A_'+f]) and row['A_'+f]!=row['B_'+f] for f in base.FEATURES)
            rows.append(entry)
    return pd.DataFrame(rows)


def design_document(df,binding):
    rolling=[]
    for split in base.make_splits(df):
        for f in validation_folds(df,split,True):
            rolling.append({'block':split['block'],'year':f['year'],'eligible':f['eligible'],'reason':f['reason'],
                            'training':base.subset_summary(df.loc[f['train']]),'validation':base.subset_summary(df.loc[f['validation']])})
    return {'created_utc':datetime.now(timezone.utc).isoformat(),'status':'locked_before_new_revision_scores',
            'analysis_status':'post_hoc_revision_original_scores_known','binding':binding,'seed':SEED,'threads':THREADS,
            'fixed_parameters':FIXED,'full_features':base.MODEL_FEATURES,'outcomes_and_weights':'unchanged from frozen cohort',
            'four_cells':['A_model_A_inputs','A_model_B_inputs','B_model_A_inputs','B_model_B_inputs'],
            'primary_metric':'design-weighted average precision; original weights in evaluation',
            'secondary_metrics':['Brier','ROC AUC','tie-aware retrospective weighted 5% capacity recall','calibration diagnostics'],
            'fit_weights':'original weights normalized to mean one; preprocessing weighted by original weights',
            'diagnostics':'A-only: log_assets; 10 raw missing flags; log_assets + 10 flags + report_lag_days; fixed LGBM',
            'size_domain':'A_log_assets >= ln(100000000) at each origin; same A/B development and test domain; nominal dollars, not exact registry inclusion eligibility',
            'transition':'Reuse original fits and exclude test only; drop development only with independent original-grid tuning; drop development only with fixed parameters; reuse old both-excluded fitted models',
            'rolling_validation':{'years':'test_start.year - 5 through -3 inclusive: last three fully matured calendar years',
                                  'maturity':'training decision+455 days <= each validation start; validation mature <= test_start; refit mature <= test_start',
                                  'score':'equal-weight mean of the three annual weighted AP values','candidate_grid':'original four candidates per learner',
                                  'missing_year_policy':'require all three years to have two-class training and validation; otherwise block is not estimable, no fallback',
                                  'preflight':rolling},
            'spline':'Additive cubic B-splines separately for 11 winsorized/imputed numerical columns; train-only weighted knots .05,.35,.65,.95 deduplicated; constant columns linear; 11 missing flags; train-weighted basis scaling; C1; linear extrapolation; no interactions',
            'random_forest':'400 trees; max_depth6; leaf20; sqrt features; bootstrap; no class weighting; normalized design weights; original full preprocessing',
            'failure_policy':'Record failed fits and undefined tuning explicitly; no test-guided parameter changes',
            'source_script_sha256':base.sha256(__file__),'base_script_sha256':base.sha256(ROOT/'scripts/run_vintage_models.py')}


def ensure_design(df,binding):
    OUT.mkdir(parents=True,exist_ok=True); path=OUT/'design.json'
    if path.exists():
        current=json.loads(path.read_text(encoding='utf-8'))
        base.require(current['source_script_sha256']==base.sha256(__file__), 'Design script hash changed: create a transparent amendment before rerun')
        return current
    design=design_document(df,binding); base.write_json(path,design); return design


def self_test():
    # Meaningful invariance guards: score B never refits A; tie capacity exact;
    # diagnostics cannot accidentally include a ratio; weighted clipping train-only.
    rng=np.random.default_rng(3); n=80
    data={'registry_event_365':np.tile([0,1],40),'sample_weight':np.tile([1.,3.],40),'row_id':[str(i) for i in range(n)],
          'report_lag_days':np.arange(n)+1.,'cik':[str(i) for i in range(n)],'cluster_id':[str(i) for i in range(n)],
          'decision_date':pd.date_range('2010-01-01',periods=n),'mature_date':pd.date_range('2011-04-01',periods=n),
          'sampling_stratum':['certainty']*n,'first_registry_event':[pd.NaT]*n}
    for f in base.FEATURES:
        a=rng.normal(size=n); a[::7]=np.nan; data['A_'+f]=a; data['B_'+f]=a.copy()
    df=pd.DataFrame(data); train=np.arange(60); test=np.arange(60,n)
    checks=[]
    for learner in ['LR','LGBM','SPLINE_LR','RF']:
        b=fit_pipeline(df,train,'A',learner)
        a=score_pipeline(b,df,test,'A'); bb=score_pipeline(b,df,test,'B')
        checks.append({'check':learner+'_equal_inputs_equal_predictions','pass':bool(np.array_equal(a,bb))})
    for fs,width in [('size',1),('missing',10),('size_missing_lag',12)]:
        b=fit_pipeline(df,train,'A','LGBM',feature_set=fs)
        checks.append({'check':fs+'_exact_feature_count','pass':matrix(df,test,'A',fs).shape[1]==width})
        checks.append({'check':fs+'_finite_predictions','pass':bool(np.isfinite(score_pipeline(b,df,test,'A')).all())})
    rc,sel=base.recall_at_weighted_capacity([1,0,0],[.5,.5,.1],[1,3,16])
    checks.append({'check':'tied_boundary_equal_fraction_exact_mass','pass':bool(sel[0]==sel[1] and np.isclose(np.dot(sel,[1,3,16]),1))})
    b=fit_pipeline(df,train,'A','LR'); before=b['preprocessing']['base']['upper'].copy()
    df.loc[test,'B_log_assets']=1e15; score_pipeline(b,df,test,'B')
    checks.append({'check':'test_input_cannot_change_fitted_quantiles','pass':before==b['preprocessing']['base']['upper']})
    base.require(all(r['pass'] for r in checks),'Revision self test failed')
    OUT.mkdir(parents=True,exist_ok=True); base.write_json(OUT/'self_test.json',checks)
    print(json.dumps({'self_test':'PASS','checks':len(checks)}),flush=True)


def findings(rec,df):
    metrics=pd.DataFrame(rec.metrics); dif=four_cell_differences(metrics)
    ap=dif[dif.metric.eq('average_precision')].copy()
    summary=ap[['experiment','block','model','AA','AB','BA','BB','total_refit_difference','procedural_interaction']].copy()
    summary.to_csv(OUT/'ap_summary.csv',index=False)
    text=['# Revision model findings','',
          'All analyses below are post hoc revision analyses; original test results were already known. No revised test metric was used to choose the declared parameters.',
          '', 'The frozen cohort has 5,502 filing windows and 188 registered event windows. The added domain uses A assets at the filing origin and is not exact BRD event-time eligibility.',
          '', 'The earliest three-year rolling-validation block is not estimable if any prescribed historical year lacks two-class training; absent results are not filled with an alternative test-selected model.',
          '', '## Paired weighted AP (percentage points)', '', '| Experiment | Block | Model | A fit / A score | B fit / B score | BB minus AA | Interaction |',
          '|---|---|---|---:|---:|---:|---:|']
    for r in ap.itertuples(): text.append(f'| {r.experiment} | {r.block} | {r.model} | {100*r.AA:.3f} | {100*r.BB:.3f} | {100*r.total_refit_difference:+.3f} | {100*r.procedural_interaction:+.3f} |')
    text += ['', '## Registry coverage diagnostics', '', '| Input | Block | AP | Prevalence | Brier |', '|---|---|---:|---:|---:|']
    for r in metrics[metrics.experiment.str.startswith('diagnostic_')].itertuples():
        text.append(f'| {r.experiment} | {r.block} | {r.average_precision:.6f} | {r.weighted_prevalence:.6f} | {r.brier:.6f} |')
    text += ['', '## Boundaries', '',
             '- Algebraic four-cell differences isolate controlled computational changes; they are not causal effects of financial restatement.',
             '- Original and fixed models still target directly linked registry events conditional on current-data accessibility. Size and missingness associations do not prove why registry membership occurs.',
             '- Three-year tuning uses unweighted averaging across annual weighted AP; it does not pool yearly predictions. Each inner training set obeys the 455-day maturity guard.',
             '- All clipping, imputation, spline knots and scaling use the relevant training data and sample weights only.',
             '- Full resampling uncertainty and source audit are separate revision modules. This file does not substitute fixed-fit point estimates for those analyses.',
             '- Report every transition record and its original split memberships from transition_records.csv; repeated rows across blocks are the same 12 underlying filing records.',
             '', 'Complete row predictions, metrics, candidate selection records, preprocessing states and split identities accompany this report.']
    (OUT/'findings.md').write_text('\n'.join(text)+'\n',encoding='utf-8')


def run_all():
    df,binding=load_base(); design=ensure_design(df,binding)
    base.require(not (OUT/'run_manifest.json').exists(),'A revision run already exists; refusing silent overwrite')
    base.require(not list((OUT/'artifacts').glob('*.joblib')) if (OUT/'artifacts').exists() else True,'Partial artifacts exist; inspect rather than silently overwrite')
    rec=Recorder(OUT); started=datetime.now(timezone.utc).isoformat()
    transition_records(df).to_csv(OUT/'transition_records.csv',index=False)
    base.require(df.form.eq('10-KT').sum()==12,'Expected twelve original transition records')
    operations=[
      ('original_four_cell',lambda:run_saved(df,rec,'original_four_cell',ORIGINAL_PREFIX,EXPECTED_HASH)),
      ('fixed_full',lambda:run_fixed_cohort(df,OUT,'fixed_full',recorder=rec)),
      ('diagnostic_size',lambda:run_fixed_cohort(df,OUT,'diagnostic_size',learners=('LGBM',),feature_set='size',recorder=rec)),
      ('diagnostic_missing',lambda:run_fixed_cohort(df,OUT,'diagnostic_missing',learners=('LGBM',),feature_set='missing',recorder=rec)),
      ('diagnostic_size_missing_lag',lambda:run_fixed_cohort(df,OUT,'diagnostic_size_missing_lag',learners=('LGBM',),feature_set='size_missing_lag',recorder=rec)),
      ('size100m_fixed',lambda:run_fixed_cohort(df,OUT,'size100m_fixed',development_filter=df.A_log_assets.ge(np.log(1e8)).to_numpy(),test_filter=df.A_log_assets.ge(np.log(1e8)).to_numpy(),recorder=rec)),
      ('transition_test_only',lambda:run_saved(df,rec,'transition_test_only',ORIGINAL_PREFIX,EXPECTED_HASH,test_filter=df.form.ne('10-KT').to_numpy())),
      ('transition_development_tuned',lambda:run_tuned(df,rec,'transition_development_tuned',development_filter=df.form.ne('10-KT').to_numpy())),
      ('transition_development_fixed',lambda:run_fixed_cohort(df,OUT,'transition_development_fixed',development_filter=df.form.ne('10-KT').to_numpy(),recorder=rec)),
      ('transition_both_saved',lambda:run_saved(df,rec,'transition_both_saved',NO_TRANSITION_PREFIX,'9d52c4ca618920a2a878b35d2eb07efaf608fd445f6d2489a720a68470ced9a6',test_filter=df.form.ne('10-KT').to_numpy())),
      ('rolling_three_year',lambda:run_tuned(df,rec,'rolling_three_year',rolling=True)),
      ('fixed_spline_rf',lambda:run_fixed_cohort(df,OUT,'fixed_spline_rf',learners=('SPLINE_LR','RF'),recorder=rec)),
    ]
    for name,operation in operations:
        print('START '+name,flush=True); start=time.perf_counter(); operation(); rec.flush()
        print('COMPLETE '+name+' seconds='+str(round(time.perf_counter()-start,2)),flush=True)
    findings(rec,df)
    # Independent-source equality check on unchanged diagonal predictions.
    old=pd.read_parquet(str(ORIGINAL_PREFIX)+'_test_predictions.parquet')
    new=pd.concat(rec.predictions,ignore_index=True)
    diag=new[new.experiment.eq('original_four_cell') & new.train_version.eq(new.score_version)]
    joined=diag.merge(old[old.model.isin(['LR','LGBM'])],on=['row_id','block','model','version'],suffixes=('_new','_old'),validate='one_to_one')
    maxdiff=float(np.abs(joined.pred_new-joined.pred_old).max())
    base.require(len(joined)==len(diag) and maxdiff<1e-12,'Original diagonal prediction reconstruction mismatch')
    base.require(base.sha256(ROOT/'datasets/model_cohort.parquet')==EXPECTED_HASH,'Frozen input changed during revision')
    outputs={str(p.relative_to(OUT)):{'sha256':base.sha256(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file()}
    base.write_json(OUT/'run_manifest.json',{'status':'complete','started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
                    'design_sha256':base.sha256(OUT/'design.json'),'script_sha256':base.sha256(__file__),'input_binding':binding,
                    'threads':THREADS,'fitted_or_reused_artifacts':len(rec.fits),'metric_rows':len(rec.metrics),
                    'prediction_rows':len(new),'original_diagonal_max_abs_difference':maxdiff,'outputs':outputs,
                    'software':{name:__import__('importlib.metadata',fromlist=['version']).version(name) for name in ['numpy','pandas','scipy','scikit-learn','lightgbm','joblib']}})
    print('ALL COMPLETE',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--plan',action='store_true'); group.add_argument('--self-test',action='store_true'); group.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.self_test: self_test()
    elif args.plan:
        df,binding=load_base(); design=ensure_design(df,binding)
        print(json.dumps(base.clean_json({'design':str(OUT/'design.json'),'rolling_preflight':design['rolling_validation']['preflight']})),flush=True)
    else: run_all()
