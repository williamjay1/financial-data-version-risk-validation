"""Paired A/B uncertainty for the locked certainty + SRS cluster sample.

No model fitting. Default CLI performs no analysis; --self-test uses synthetic
finite populations only. --run requires an explicit open phase2 data gate.

The Rao-Wu-Yue weight rescaling uses m=n-1 replacement draws from all n sampled
noncase PSUs and multiplier 1+sqrt(1-n/N)*(n*M/(n-1)-1). Certainty PSUs keep
weight one. Every sampled zero-domain PSU remains in the multinomial draw.
The same draws are used in A/B and across blocks/models. Estimates concern
weighted filing-window outcomes, not unique events or a calendar-time policy.

Sources:
https://cran.r-project.org/web/packages/surveysd/vignettes/raowu.html
https://www150.statcan.gc.ca/n1/pub/12-001-x/2009002/article/11044-eng.pdf
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
METRICS=('average_precision','brier','roc_auc','retrospective_recall_at_5percent')
SEED=20260921
LIMITS=[
    'Approximate pointwise design-based intervals for fixed predictions in the eligible observed domain.',
    'Do not include model fitting/tuning/calibration uncertainty or repeated-sample model retraining.',
    'Certainty clusters and observed registry outcomes are fixed; no registry undercapture, mapping-error, or event-population uncertainty.',
    'Do not cover future economic regimes or crises. Three time blocks are not independent macroeconomic experiments.',
    'Recall counts positive filing windows, not unique company-case episodes; ranking is retrospective within each time block.',
    'No nonresponse adjustment for inaccessible XBRL; zero-domain sampled clusters remain in the SRS draw.',
    'AP and weighted top-budget recall are nonlinear; finite-sample 95% coverage is not guaranteed by the bootstrap.',
]

def require(test, message):
    if not bool(test):raise ValueError(message)

def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(np.bool_,)):return bool(value)
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    if isinstance(value,Path):return str(value)
    return value

def write_json(path,value):
    Path(path).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()

def bool_values(series, name):
    if pd.api.types.is_bool_dtype(series):
        require(series.notna().all(),f'Missing {name}')
        return series.to_numpy(dtype=bool)
    mapped=series.astype(str).str.lower().map({'true':True,'false':False,'1':True,'0':False})
    require(mapped.notna().all(),f'Invalid boolean {name}')
    return mapped.to_numpy(dtype=bool)

@dataclass
class SamplingDesign:
    frame: pd.DataFrame
    clusters: pd.DataFrame
    sampled_noncase: tuple
    certainty: tuple
    population_noncase: int

    @classmethod
    def from_frame(cls, frame):
        needed={'cik','cluster_id','sampling_stratum','selected','inclusion_probability','sample_weight'}
        require(needed<=set(frame),f'Sampling frame missing {needed-set(frame)}')
        x=frame.copy()
        for col in ['cik','cluster_id']:
            require(x[col].notna().all(),f'Missing frame {col}')
            x[col]=x[col].astype(str)
        require(not x.cik.duplicated().any(),'CIK duplicated in sampling frame')
        x['selected']=bool_values(x.selected,'selected')
        require(x.sampling_stratum.isin(['certainty','noncase_srs']).all(),'Unexpected sampling stratum')
        for col in ['inclusion_probability','sample_weight']:
            x[col]=pd.to_numeric(x[col],errors='raise')
            require(np.isfinite(x[col]).all() and x[col].gt(0).all(),f'Invalid {col}')
        require(x.inclusion_probability.le(1).all(),'Inclusion probability >1')
        require(np.allclose(x.sample_weight,1/x.inclusion_probability,rtol=1e-10,atol=1e-12),'Weight not inverse pi')
        for col in ['sampling_stratum','selected','inclusion_probability','sample_weight']:
            require(x.groupby('cluster_id')[col].nunique(dropna=False).eq(1).all(),f'Cluster members disagree on {col}')
        cs=x.drop_duplicates('cluster_id').set_index('cluster_id').sort_index()
        certain=cs[cs.sampling_stratum.eq('certainty')]
        noncase=cs[cs.sampling_stratum.eq('noncase_srs')]
        require(certain.selected.all() and certain.inclusion_probability.eq(1).all(),'Certainty stratum must be fully selected with pi=1')
        N=len(noncase); n=int(noncase.selected.sum())
        require(N>0 and 0<n<=N,'Empty or invalid noncase sample')
        require(n>=2 or n==N,'Rao-Wu requires >=2 sampled PSUs unless census')
        require(np.allclose(noncase.inclusion_probability,n/N,rtol=1e-10,atol=1e-12),'Noncase pi disagrees with full population frame n/N')
        return cls(x,cs,tuple(noncase[noncase.selected].index),tuple(certain.index),N)

    def manifest(self):
        n=len(self.sampled_noncase);N=self.population_noncase
        return {'noncase_population_clusters':N,'noncase_sample_clusters':n,'certainty_clusters':len(self.certainty),
                'noncase_sampling_fraction':n/N,'noncase_base_weight':N/n,'bootstrap_draws_per_replicate':n-1 if n<N else 0,
                'rescale_lambda':math.sqrt(1-n/N),'certainty_multiplier':1.0,
                'formula':'w_i* = w_i [1 + sqrt(1-n/N) (n M_i/(n-1) - 1)], M ~ Multinomial(n-1;1/n,...,1/n)',
                'zero_domain_clusters_retained':True,'same_replicate_draws_across_all_blocks_models_and_versions':True}

def rescaled_multipliers(n, N, n_boot=1000, seed=SEED):
    require(1<=n<=N and n_boot>=2,'Invalid bootstrap dimensions')
    if n==N:return np.ones((n_boot,n),dtype=float)
    require(n>=2,'Need at least two sampled noncase clusters')
    rng=np.random.default_rng(seed)
    counts=rng.multinomial(n-1,np.full(n,1/n),size=n_boot)
    multipliers=1+math.sqrt(1-n/N)*(n*counts/(n-1)-1)
    require(np.all(multipliers>=0),'Negative replicate weights')
    require(np.allclose(multipliers.sum(axis=1),n,rtol=1e-12,atol=1e-9),'Replicate cluster mass is not preserved')
    return multipliers

class MetricCache:
    """Fixed scores and exact-score tie groups; only survey weights change."""
    def __init__(self,y,p):
        self.y=np.asarray(y,dtype=float);self.p=np.asarray(p,dtype=float)
        require(self.y.ndim==self.p.ndim==1 and len(self.y)==len(self.p)>0,'Invalid metric arrays')
        require(np.isin(self.y,[0,1]).all(),'Nonbinary or missing outcome')
        require(np.isfinite(self.p).all() and ((self.p>=0)&(self.p<=1)).all(),'Invalid probability')
        _,inverse=np.unique(-self.p,return_inverse=True)
        self.group=inverse;self.ngroup=int(inverse.max())+1
        self.loss=(self.p-self.y)**2

    def evaluate(self,weights,budget=0.05):
        w=np.asarray(weights,dtype=float)
        require(w.shape==self.y.shape and np.isfinite(w).all() and (w>=0).all(),'Invalid metric weights')
        require(0<budget<=1,'Invalid review budget')
        mass=float(w.sum())
        if mass<=0:return {m:np.nan for m in METRICS}
        group_mass=np.bincount(self.group,weights=w,minlength=self.ngroup)
        group_pos=np.bincount(self.group,weights=w*self.y,minlength=self.ngroup)
        use=group_mass>0;group_mass=group_mass[use];group_pos=group_pos[use]
        cumulative=np.cumsum(group_mass);tp=np.cumsum(group_pos)
        positive=float(np.dot(w,self.y));negative=float(np.dot(w,1-self.y))
        ap=auc=recall=np.nan
        if positive>0 and negative>0:
            ap=float(np.dot(group_pos, tp/cumulative)/positive)
            fp=np.cumsum(group_mass-group_pos)
            auc=float(np.trapezoid(np.r_[0,tp/positive],np.r_[0,fp/negative]))
        if positive>0:
            before=cumulative-group_mass
            fraction=np.clip((budget*mass-before)/group_mass,0,1)
            recall=float(np.dot(fraction,group_pos)/positive)
            require(np.isclose(np.dot(fraction,group_mass),budget*mass,rtol=1e-10,atol=1e-10),'Budget capacity mismatch')
        return dict(zip(METRICS,[ap,float(np.dot(w,self.loss)/mass),auc,recall]))

def normalize_predictions(predictions, design):
    x=predictions.copy()
    aliases={'label':'registry_event_365','pred':'prediction'}
    for name,alias in aliases.items():
        if name not in x and alias in x:x[name]=x[alias]
        elif name in x and alias in x:
            require(np.allclose(x[name],x[alias],rtol=0,atol=1e-12,equal_nan=True),f'Prediction aliases disagree: {name}/{alias}')
    needed={'row_id','cluster_id','cik','block','model','version','label','pred'}
    require(needed<=set(x),f'Prediction table missing {needed-set(x)}')
    require(len(x)>0,'No predictions')
    for col in ['row_id','cluster_id','cik','block','model','version']:
        require(x[col].notna().all(),f'Missing prediction {col}')
        x[col]=x[col].astype(str)
    require(not x.duplicated(['block','model','version','row_id']).any(),'Duplicate prediction identity')
    for col in ['block','cik','cluster_id','label']:
        require(x.groupby('row_id')[col].nunique(dropna=False).eq(1).all(),f'Row identity disagrees across models/versions on {col}')
    require(np.isin(x.label,[0,1]).all(),'Prediction labels must be complete binary values')
    require(np.isfinite(x.pred).all() and x.pred.between(0,1).all(),'Invalid stored prediction')
    membership=design.frame.set_index('cik')
    require(x.cik.isin(membership.index).all(),'Prediction CIK missing from locked frame')
    lookup=membership.loc[x.cik].reset_index(drop=True)
    require(np.array_equal(x.cluster_id.to_numpy(),lookup.cluster_id.to_numpy()),'Prediction CIK/cluster mapping conflicts with locked frame')
    require(lookup.selected.all(),'Predictions include unsampled cluster')
    for col in ['sample_weight','inclusion_probability']:
        if col in x:require(np.allclose(x[col],lookup[col],rtol=1e-10,atol=1e-12),f'Stored {col} conflicts with locked frame')
        x[col]=lookup[col].to_numpy()
    if 'sampling_stratum' in x:require(np.array_equal(x.sampling_stratum.to_numpy(),lookup.sampling_stratum.to_numpy()),'Stratum mismatch')
    x['sampling_stratum']=lookup.sampling_stratum.to_numpy()
    if 'certainty' in x:require(np.array_equal(bool_values(x.certainty,'certainty'),x.sampling_stratum.eq('certainty').to_numpy()),'Certainty indicator mismatch')
    return x

def paired_uncertainty(predictions, sampling_frame, n_boot=1000, seed=SEED,
                       models=('LR','LGBM'), minimum_valid_fraction=1.0,
                       analysis_mode='refit_vintages'):
    """Return summary/replicate DataFrames and design manifest, without I/O.

    A/B rows must match exactly in each block/model. The full locked population
    sampling_frame, including unsampled and zero-domain clusters, is mandatory.
    Intervals are basic (centered) 95% bootstrap intervals, not exact intervals.
    Invalid replicates are counted. If valid fraction < threshold, CI is NaN.
    """
    require(n_boot>=2,'Need at least two replicates')
    require(0<minimum_valid_fraction<=1,'Invalid minimum valid fraction')
    require(analysis_mode in ['refit_vintages','frozen_A_inputs'],'Unknown analysis mode')
    design=SamplingDesign.from_frame(sampling_frame)
    x=normalize_predictions(predictions,design)
    ignore=x.loc[~x.model.isin(models)|~x.version.isin(['A','B'])]
    x=x[x.model.isin(models)&x.version.isin(['A','B'])].copy()
    require(len(x)>0,'No requested A/B predictions')
    require(set(models)<=set(x.model),'A requested model has no predictions')
    expected_cells={(block,model) for block in x.block.unique() for model in models}
    require(set(x[['block','model']].itertuples(index=False,name=None))==expected_cells,'Missing model/block prediction cell')
    if analysis_mode=='frozen_A_inputs':
        require('scenario' in x,'Frozen-A input analysis requires explicit scenario column')
        expected=x.version.map({'A':'A_model_A_inputs','B':'A_model_B_inputs'})
        require(np.array_equal(x.scenario.to_numpy(),expected.to_numpy()),'Frozen-A scenarios do not match A/B input versions')
    elif 'scenario' in x:
        require(not x.scenario.isin(['A_model_A_inputs','A_model_B_inputs']).any(),'Frozen-A predictions cannot be analyzed as refit-vintage comparison')
    multipliers=rescaled_multipliers(len(design.sampled_noncase),design.population_noncase,n_boot,seed)
    cluster_number={c:i for i,c in enumerate(design.sampled_noncase)}
    summary=[];replicate_rows=[];cell_audits=[]
    for (block,model),cell in x.groupby(['block','model'],sort=True):
        require(set(cell.version)=={'A','B'},f'Incomplete A/B pair: {block}/{model}')
        a=cell[cell.version.eq('A')].set_index('row_id').sort_index()
        b=cell[cell.version.eq('B')].set_index('row_id').sort_index()
        require(a.index.equals(b.index),f'A/B row sets differ in {block}/{model}')
        for col in ['cik','cluster_id','label','sample_weight','sampling_stratum']:
            require(np.array_equal(a[col].to_numpy(),b[col].to_numpy()),f'A/B {col} differs in {block}/{model}')
        y=a.label.to_numpy(dtype=float);weights=a.sample_weight.to_numpy(dtype=float)
        cache_a=MetricCache(y,a.pred.to_numpy());cache_b=MetricCache(y,b.pred.to_numpy())
        point_a=cache_a.evaluate(weights);point_b=cache_b.evaluate(weights)
        local_noncase=a.sampling_stratum.eq('noncase_srs').to_numpy()
        indexes=np.array([cluster_number[c] for c in a.loc[local_noncase,'cluster_id']],dtype=int)
        reps={m:np.full(n_boot,np.nan) for m in METRICS}
        for rep in range(n_boot):
            rw=weights.copy();rw[local_noncase]*=multipliers[rep,indexes]
            ma=cache_a.evaluate(rw);mb=cache_b.evaluate(rw)
            for metric in METRICS:
                difference=mb[metric]-ma[metric];reps[metric][rep]=difference
                replicate_rows.append({'analysis_mode':analysis_mode,'block':block,'model':model,'replicate':rep,'metric':metric,'A':ma[metric],'B':mb[metric],'difference_B_minus_A':difference,'valid':bool(np.isfinite(difference))})
        active=a.loc[local_noncase,'cluster_id'].nunique()
        active_certain=a.loc[~local_noncase,'cluster_id'].nunique()
        cell_audits.append({'analysis_mode':analysis_mode,'block':block,'model':model,'rows':len(a),'positive_filing_windows':int(y.sum()),'distinct_positive_ciks':a.loc[a.label.eq(1),'cik'].nunique(),'distinct_positive_sampling_clusters':a.loc[a.label.eq(1),'cluster_id'].nunique(),'active_noncase_clusters':active,'zero_domain_sampled_noncase_clusters':len(design.sampled_noncase)-active,'active_certainty_clusters':active_certain,'zero_domain_certainty_clusters':len(design.certainty)-active_certain})
        for metric in METRICS:
            values=reps[metric];valid=np.isfinite(values);rate=float(valid.mean())
            point=point_b[metric]-point_a[metric];lower=upper=se=bias=np.nan
            status='point_metric_undefined'
            if np.isfinite(point):
                status='insufficient_valid_replicates'
                if valid.sum()>=2 and rate>=minimum_valid_fraction:
                    qlo,qhi=np.quantile(values[valid],[0.025,0.975])
                    lower=2*point-qhi;upper=2*point-qlo
                    se=float(np.std(values[valid],ddof=1));bias=float(values[valid].mean()-point)
                    status='estimated' if valid.all() else 'estimated_with_invalid_replicates_disclosed'
            summary.append({'analysis_mode':analysis_mode,'block':block,'model':model,'metric':metric,'A':point_a[metric],'B':point_b[metric],
                'difference_B_minus_A':point,'ci95_low':lower,'ci95_high':upper,'bootstrap_se':se,'bootstrap_bias_diagnostic':bias,
                'n_boot':n_boot,'valid_boot':int(valid.sum()),'invalid_boot':int((~valid).sum()),'valid_boot_fraction':rate,
                'status':status,'ci_method':'basic_centered_Rao_Wu_Yue_SRS_FPC','seed':seed,
                'better_direction_for_B_minus_A':'negative' if metric=='brier' else 'positive'})
    return {'summary':pd.DataFrame(summary),'replicates':pd.DataFrame(replicate_rows),
        'design':{**design.manifest(),'analysis_mode':analysis_mode,'n_boot':n_boot,'seed':seed,'minimum_valid_fraction':minimum_valid_fraction,
                  'excluded_non_AB_or_unrequested_rows':len(ignore),'limitations':LIMITS},
        'cell_audits':pd.DataFrame(cell_audits)}

def self_test():
    """Known finite-population tests. These are never research findings."""
    from sklearn.metrics import average_precision_score,roc_auc_score
    y=np.array([0,1,0,1,0,1]);p=np.array([.7,.7,.4,.2,.2,.1]);w=np.array([2.,1,3,2,4,1])
    metric=MetricCache(y,p).evaluate(w)
    assert np.isclose(metric['average_precision'],average_precision_score(y,p,sample_weight=w))
    assert np.isclose(metric['roc_auc'],roc_auc_score(y,p,sample_weight=w))
    assert np.isclose(metric['brier'],np.average((p-y)**2,weights=w))
    idx=np.repeat(np.arange(len(y)),w.astype(int)); expanded=MetricCache(y[idx],p[idx]).evaluate(np.ones(len(idx)))
    for name in METRICS:assert np.isclose(metric[name],expanded[name])
    perm=np.array([4,2,1,5,0,3]);permuted=MetricCache(y[perm],p[perm]).evaluate(w[perm])
    for name in METRICS:assert np.isclose(metric[name],permuted[name])
    assert np.isclose(MetricCache(y,np.ones(len(y))*.3).evaluate(w)['retrospective_recall_at_5percent'],.05)
    assert np.isnan(MetricCache(np.zeros(3),np.array([.1,.2,.3])).evaluate(np.ones(3))['average_precision'])
    assert np.isnan(MetricCache(np.ones(3),np.array([.1,.2,.3])).evaluate(np.array([.1,.2,.7]))['average_precision'])
    # Exactly enumerate all 70 SRS samples from a known N=8 population, including
    # zero-contribution PSUs, and all 4^(4-1)=64 Rao-Wu draws within each sample.
    population=np.array([0.,0.,1.,2.,4.,7.,11.,13.]);N=8;n=4
    all_counts=np.array([np.bincount(draw,minlength=n) for draw in itertools.product(range(n),repeat=n-1)])
    factors=1+math.sqrt(1-n/N)*(n*all_counts/(n-1)-1)
    totals=[];variance_estimates=[];variance_errors=[]
    for sample in itertools.combinations(range(N),n):
        z=population[list(sample)];estimate=N/n*z.sum();totals.append(estimate)
        rw=N/n*(factors@z)
        exact_sample_variance=N*N*(1-n/N)*np.var(z,ddof=1)/n
        bootstrap_variance=float(np.var(rw,ddof=0))
        variance_errors.append(abs(bootstrap_variance-exact_sample_variance))
        variance_estimates.append(bootstrap_variance)
    design_variance=N*N*(1-n/N)*np.var(population,ddof=1)/n
    assert np.isclose(np.mean(totals),population.sum())
    assert np.isclose(np.var(totals,ddof=0),design_variance)
    assert np.isclose(np.mean(variance_estimates),design_variance)
    assert max(variance_errors)<1e-10
    # Known toy population has 4 certainty and 12 noncase clusters; sample 6.
    # n0 is selected but has no eligible row. nc1 contains two CIK members.
    frame=[]
    for i in range(4):frame.append({'cik':f'case{i}','cluster_id':f'case{i}','sampling_stratum':'certainty','selected':True,'inclusion_probability':1.,'sample_weight':1.})
    for i in range(12):
        for member in range(2 if i==1 else 1):frame.append({'cik':f'nc{i}_m{member}','cluster_id':f'nc{i}','sampling_stratum':'noncase_srs','selected':i<6,'inclusion_probability':.5,'sample_weight':2.})
    frame=pd.DataFrame(frame);predictions=[];population_predictions=[]
    for i,row in frame.iterrows():
        if row.cluster_id=='nc0':continue
        label=int(row.sampling_stratum=='certainty')
        for t in [0,1]:
            score=.08+.035*((i*3+t)%13)
            for version,pr in [('A',score),('B',min(.95,score+.12*label-.025*(1-label)))]:
                record={'row_id':f'{row.cik}|{t}','cluster_id':row.cluster_id,'cik':row.cik,'block':f'toy_{t}',
                        'model':'LR','version':version,'label':label,'pred':pr,'sample_weight':row.sample_weight,'sampling_stratum':row.sampling_stratum}
                population_predictions.append(record)
                if row.selected:predictions.append(record)
    predictions=pd.DataFrame(predictions)
    result=paired_uncertainty(predictions,frame,n_boot=200,models=('LR',))
    assert result['cell_audits'].zero_domain_sampled_noncase_clusters.eq(1).all()
    identical=predictions.copy();lookup=identical[identical.version.eq('A')].set_index('row_id').pred
    identical['pred']=identical.row_id.map(lookup)
    null=paired_uncertainty(identical,frame,n_boot=200,models=('LR',))
    assert np.allclose(null['summary'][['difference_B_minus_A','ci95_low','ci95_high']],0)
    reverse=predictions.copy();reverse['version']=reverse.version.map({'A':'B','B':'A'})
    reversed_result=paired_uncertainty(reverse,frame,n_boot=200,models=('LR',))
    assert np.allclose(result['replicates'].difference_B_minus_A,-reversed_result['replicates'].difference_B_minus_A)
    assert np.allclose(result['summary'].ci95_low,-reversed_result['summary'].ci95_high)
    # Explicit census has zero design variance; all-zero-event metrics remain
    # undefined with valid_boot=0, never silently treated as regular intervals.
    census=frame.copy();census['selected']=True;census['sample_weight']=1.;census['inclusion_probability']=1.
    full=pd.DataFrame(population_predictions);full['sample_weight']=1.
    census_result=paired_uncertainty(full,census,n_boot=50,models=('LR',))
    assert np.allclose(census_result['summary'].bootstrap_se,0,atol=1e-14)
    assert np.allclose(census_result['summary'].ci95_low,census_result['summary'].difference_B_minus_A)
    no_event=predictions.copy();no_event['label']=0
    missing=paired_uncertainty(no_event,frame,n_boot=50,models=('LR',))['summary']
    assert missing.loc[missing.metric.ne('brier'),'valid_boot'].eq(0).all()
    assert missing.loc[missing.metric.ne('brier'),'ci95_low'].isna().all()
    rejects=[]
    bad=predictions.copy();bad.loc[bad.version.eq('B'),'label']=0
    for test_frame,test_pred,name in [(frame,bad,'A/B labels differ'),(frame.assign(sample_weight=1),predictions,'incorrect inverse probability'),(frame[frame.cluster_id.ne('nc0')],predictions,'zero-domain PSU improperly deleted')]:
        try:paired_uncertainty(test_pred,test_frame,n_boot=10,models=('LR',))
        except ValueError:rejects.append(name)
    assert len(rejects)==3
    frozen=predictions.copy();frozen['scenario']=frozen.version.map({'A':'A_model_A_inputs','B':'A_model_B_inputs'})
    frozen_result=paired_uncertainty(frozen,frame,n_boot=50,models=('LR',),analysis_mode='frozen_A_inputs')
    assert frozen_result['summary'].analysis_mode.eq('frozen_A_inputs').all()
    try:paired_uncertainty(frozen,frame,n_boot=10,models=('LR',))
    except ValueError:rejects.append('frozen-A input diagnostic mixed into main refit comparison')
    assert len(rejects)==4
    return {'status':'PASS','data_kind':'SYNTHETIC_TEST_ONLY_NOT_RESEARCH_RESULTS','tests':[
        'Weighted AP/ROC/Brier versus sklearn and integer expansion','Exact-score tie and permutation invariance',
        'Exactly enumerated finite-population SRS HT unbiasedness and variance','Exact Rao-Wu conditional variance equals SRS variance estimator',
        'Average exact variance estimator equals known finite-population sampling variance','Zero-domain PSU kept and multi-member cluster allowed',
        'Identical A/B gives exactly zero paired interval','Swapping A/B reverses every paired replicate and interval',
        'Census FPC yields zero design variance','Single-class AP/ROC and no-event recall explicitly invalid','Malformed weights/pairs/deleted zero-domain PSU rejected',
        'Frozen-A inputs require distinct mode; accidental main-comparison use rejected'],
        'known_population':{'N':N,'n':n,'values':population.tolist(),'total':float(population.sum()),'enumerated_srs_samples':len(totals),'rw_replicates_per_sample':len(factors),'exact_design_variance_HT_total':design_variance,'mean_HT_estimate':np.mean(totals),'mean_RW_variance_estimate':np.mean(variance_estimates),'maximum_conditional_variance_error':max(variance_errors)},
        'paired_toy_metrics_full_population':census_result['summary'][['block','metric','A','B','difference_B_minus_A']].to_dict('records'),
        'paired_toy_metrics_sample_only':result['summary'].to_dict('records'),'rejected_bad_inputs':rejects,
        'note':'These checks validate implementation identities, not nominal 95% coverage for sparse nonlinear metrics.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--self-test',action='store_true');mode.add_argument('--run',action='store_true')
    parser.add_argument('--predictions',type=Path,nargs='+')
    parser.add_argument('--sampling-frame',type=Path,default=ROOT/'datasets/sampling_frame.parquet')
    parser.add_argument('--protocol',type=Path,default=ROOT/'phase2_protocol.json')
    parser.add_argument('--sampling-summary',type=Path,default=ROOT/'results/sampling_frame_summary.json')
    parser.add_argument('--analysis-mode',choices=['refit_vintages','frozen_A_inputs'],default='refit_vintages')
    parser.add_argument('--n-boot',type=int,default=1000);parser.add_argument('--seed',type=int,default=SEED)
    args=parser.parse_args();out=ROOT/'results';out.mkdir(exist_ok=True)
    if args.self_test:
        result=self_test();result['script_sha256']=sha(__file__)
        write_json(out/'uncertainty_self_test.json',result)
        print(json.dumps({'status':result['status'],'tests':len(result['tests']),'output':str(out/'uncertainty_self_test.json')}));return
    if not args.run:parser.print_help();return
    require(args.predictions,'--run requires --predictions')
    require(500<=args.n_boot<=10000,'Formal run needs at least 500 and at most 10000 bootstrap replicates')
    require(args.seed==SEED,'Formal seed is locked at 20260921')
    for path in [args.sampling_frame,args.protocol,args.sampling_summary,*args.predictions]:require(path.resolve().drive.lower()=='d:',f'Analysis inputs must be D: caches: {path}')
    protocol=json.loads(args.protocol.read_text(encoding='utf-8'))
    require(protocol.get('data_gate',{}).get('training_allowed_now') is True,'Data gate remains closed; formal uncertainty not allowed')
    sampling_summary=json.loads(args.sampling_summary.read_text(encoding='utf-8'))
    require(sha(args.sampling_frame)==sampling_summary['frame_sha256'],'Locked sampling-frame hash mismatch')
    started=time.monotonic();table=pd.concat([pd.read_parquet(p) for p in args.predictions],ignore_index=True)
    expected_blocks={f'{int(start[:4])}_{int(end[:4])}' for start,end in protocol['time_blocks']}
    require(set(table.block.astype(str))==expected_blocks,'Formal predictions do not cover exactly the protocol test blocks')
    result=paired_uncertainty(table,pd.read_parquet(args.sampling_frame),args.n_boot,args.seed,analysis_mode=args.analysis_mode)
    for key in ['noncase_population_clusters','noncase_sample_clusters','certainty_clusters']:
        require(result['design'][key]==sampling_summary[key],f'Sampling-summary disagreement on {key}')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');prefix=out/f'uncertainty_{stamp}'
    result['summary'].to_csv(str(prefix)+'_summary.csv',index=False)
    result['replicates'].to_parquet(str(prefix)+'_replicates.parquet',index=False)
    result['cell_audits'].to_csv(str(prefix)+'_cell_audits.csv',index=False)
    manifest={**result['design'],'created_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.monotonic()-started,
              'sampling_frame':str(args.sampling_frame),'sampling_frame_sha256':sha(args.sampling_frame),
              'sampling_summary':str(args.sampling_summary),'sampling_summary_sha256':sha(args.sampling_summary),
              'protocol':str(args.protocol),'protocol_sha256':sha(args.protocol),'script_sha256':sha(__file__),
              'prediction_inputs':[{'path':str(p),'sha256':sha(p)} for p in args.predictions],
              'outputs':{p.name:sha(p) for p in out.glob(prefix.name+'*')}}
    write_json(str(prefix)+'_manifest.json',manifest)
    print(result['summary'].to_string(index=False));print(str(prefix)+'_manifest.json')

if __name__=='__main__':main()
