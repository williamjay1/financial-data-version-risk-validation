"""Read-only re-evaluation of frozen financial-vintage predictions and inputs.

No model fitting, network access or writes outside results/evaluation_diagnostics.
Run ``prepare`` before ``run``.  Metrics below are independently implemented.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

ROUND = Path(__file__).resolve().parents[1]
ROOT = ROUND.parent
OLD = ROOT / 'revision_20260922'
OUT = ROUND / 'results/evaluation_diagnostics'
RUNID = '20260921T093517075175Z'
FEATURES = ['log_assets','liabilities_to_assets','equity_to_assets','cash_to_assets',
            'net_income_to_assets','revenue_to_assets','operating_income_to_assets',
            'operating_cash_to_assets','retained_earnings_to_assets','working_capital_to_assets']
METRICS = ['average_precision','brier','roc_auc','retrospective_recall_at_5percent']
BLOCKS = ['2016_2017','2018_2019','2020_2021']


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.floating,)): return float(x) if np.isfinite(x) else None
    if isinstance(x,(np.bool_,)): return bool(x)
    if isinstance(x,Path): return str(x)
    if isinstance(x,float) and not np.isfinite(x): return None
    return x


def write_json(name,obj):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2),encoding='utf-8')


def write_csv(name,rows):
    d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    d.to_csv(OUT/name,index=False,float_format='%.17g')
    return d


def source_paths():
    paths=[ROOT/'datasets/model_cohort.parquet',ROOT/'datasets/vintage_facts.parquet',
           ROOT/'datasets/sampling_frame.parquet',ROOT/'datasets/universe_annual_filings_2010_2021.parquet',
           ROOT/f'results/models_{RUNID}_test_predictions.parquet',
           OLD/'results/models/predictions.parquet',OLD/'results/models/metrics.csv',
           OLD/'results/models/fit_preprocessing_audit.json',
           OLD/'results/version_caps/cap_fact_lineage.parquet',OLD/'results/version_caps/cap_lineage.parquet',
           OLD/'results/uncertainty/replicate_multipliers.npy',OLD/'results/uncertainty/replicate_cluster_order.csv',
           OLD/'results/uncertainty/full_pipeline_paired_replicates.csv',
           OLD/'results/uncertainty/full_pipeline_distribution_summary.csv',
           ROOT/'results/uncertainty_20260921T093555450801Z_summary.csv',
           ROOT/'results/uncertainty_20260921T093555450801Z_replicates.parquet']
    paths += [OLD/f'datasets/cap_{c}.parquet' for c in [90,365,730]]
    paths += [OLD/f'results/uncertainty/replicates/replicate_{b:03d}/predictions.parquet' for b in range(200)]
    for pattern in ['corporate_access_manifest_*.json','expanded_sec_manifest_*.jsonl','control_sec_manifest_*.jsonl']:
        paths += sorted((ROOT/'results').glob(pattern))
    return sorted(set(paths))


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'design.json'
    if target.exists():
        print('Existing frozen design retained.',flush=True)
        return
    design={
      'status':'FROZEN_BEFORE_NEW_DIAGNOSTIC_OUTPUTS','created_utc':datetime.now(timezone.utc).isoformat(),
      'route':'SCI applied ML evaluation methodology; post hoc explanatory diagnostic, not causal identification',
      'existing_results_already_known':True,'additional_model_fits':0,'network_requests':0,
      'replicates':200,'same_replica_identity_in_all_modes':True,
      'modes':{'development_only':'saved replicate AA/BB probabilities evaluated with original design weights',
               'evaluation_only':'original AA/BB probabilities evaluated with that same replicate evaluation weights',
               'joint':'saved replicate AA/BB probabilities evaluated with saved replicate weights'},
      'reporting':'AA, BB, B-minus-A for AP/Brier/ROC/5%-mass recall, all 200 points, quantiles .025/.05/.5/.95/.975 and positive/negative/tie fractions. No additive variance decomposition; no new confidence interval interpretation.',
      'independent_metrics':'Own score-tie grouping AP and ROC formula, weighted Brier, equal fractional capacity-boundary ties. No imported prior metric evaluator.',
      'table7_independent_check':'Reconstruct 1000 conditional draws at seed20260921 in lexicographically sorted selected noncase cluster order, including zero-domain clusters; re-evaluate original row probabilities and basic-centered intervals. Separately compare joint200 points to frozen previous output.',
      'exposure':'By full-cohort and each test block, label 0/1: no later bundle / later bundle and no raw numerical change / later bundle with raw change; within-label raw and weighted proportions. Do not condition primary performance estimates on future availability.',
      'continuity':'Original Forms10-K/10-KT in (origin,origin+365days] in existing official submissions metadata, restricted to source cutoff2026-09-21; this is subsequent annual-report presence, not survival. Any missing history file intersecting the observation interval makes absence unknown. An observed qualifying filing proves presence even with incomplete coverage. No new downloads.',
      'exposure_descriptors':'Original observed fact count and ten-model-input missing count; original log assets and assets; 365-day annual-report continuation with known/unknown denominators.',
      'adjacent_horizons':[90,365,730,'latest'],
      'adjacent_reporting':'Newly available, lost availability, later-to-later accession switch, unchanged selected accession, raw-component and model-feature changes; existing-bundle value changes separately; exact and relative-tolerance raw counts. Row-level output and cohort/block-label summaries.',
      'raw_change':'abs(B-A)>1e-12*max(1,abs(A),abs(B)) for scientific change and additionally exact inequality for lineage; preserve original masks.',
      'magnitude':'Retain abs(B-A)/max(1,absA,absB); same-sign nonzero log10(abs(B/A)) and abs log ratio, multiplicative scale; strict nonzero sign flip and zero transitions separately. Summaries among observed pairs and changed pairs keep denominators explicit.',
      'training_time':'Final refit partition has origin+455days <= Jan1 first test year, verified against original saved refit row IDs where available. Tabulate selected later source dates <,=,> fixed Jan1 fit cutoff; strict > is requested future-source count, equality separately because filed is date-only. Denominators all refit rows and later-available refit rows. No assertion of historical API authentication.',
      'interpretation_limits':['Certainty outcomes fixed, identical 1000 noncase PSU draws preserved.','No training re-estimation performed now: existing paired fitted probabilities reused.','Modes are dependent diagnostics; covariance/interactions prevent summing marginal variances.','No new macroperiod/event population/source-error uncertainty.','Observed annual report presence is a future availability description, not an input for prospective scoring.'],
      'sources':[{'path':str(p),'sha256':sha(p)} for p in source_paths()]}
    write_json('design.json',design)
    print('Frozen design with',len(design['sources']),'source files.',flush=True)


def verify_sources(design):
    for x in design['sources']:
        if sha(x['path']) != x['sha256']: raise AssertionError('Frozen source changed: '+x['path'])


class IndependentMetrics:
    """Group exact probability ties; recompute all weight-dependent quantities."""
    def __init__(self,y,p):
        y=np.asarray(y,dtype=float); p=np.asarray(p,dtype=float)
        assert len(y)==len(p) and np.isfinite(p).all() and np.isin(y,[0,1]).all()
        assert ((p>=0)&(p<=1)).all()
        self.y=y;self.p=p
        self.order=np.argsort(-p,kind='stable')
        ps=p[self.order]
        self.starts=np.r_[0,np.flatnonzero(ps[1:]!=ps[:-1])+1]

    def evaluate(self,w):
        w=np.asarray(w,dtype=float); assert np.isfinite(w).all() and (w>=0).all() and w.sum()>0
        s=self.order;ys=self.y[s];ws=w[s]
        masses=np.add.reduceat(ws,self.starts)
        positives=np.add.reduceat(ws*ys,self.starts)
        negatives=masses-positives
        total=masses.sum();p=positives.sum();n=negatives.sum()
        cp=np.cumsum(positives);cm=np.cumsum(masses)
        ap=np.sum(positives*np.divide(cp,cm,out=np.zeros_like(cp),where=cm>0))/p if p else np.nan
        # Each positive receives credit for all lower-scored negatives plus half tied negatives.
        below=n-np.cumsum(negatives)
        roc=np.sum(positives*(below+0.5*negatives))/(p*n) if p and n else np.nan
        prior=np.r_[0,np.cumsum(masses)[:-1]]
        selected=np.clip(np.divide(.05*total-prior,masses,out=np.zeros_like(masses),where=masses>0),0,1)
        recall=np.sum(selected*positives)/p if p else np.nan
        return dict(zip(METRICS,[ap,np.average((self.y-self.p)**2,weights=w),roc,recall]))


def self_test():
    # Hand-computable weighted tied-score example: first tied group has mass3, positive mass1.
    y=[1,0,1,0];p=[.8,.8,.2,.1];w=[1,2,3,4]
    m=IndependentMetrics(y,p).evaluate(w)
    expected={'average_precision':7/12,'roc_auc':2/3,'retrospective_recall_at_5percent':1/24,
              'brier':sum(a*(b-c)**2 for a,b,c in zip(w,y,p))/10}
    # Positive/negative weighted pairs: top positive beats 4 and ties2; lower positive beats4.
    expected['roc_auc']=17/24
    assert all(abs(m[k]-v)<1e-13 for k,v in expected.items()),(m,expected)
    assert abs(IndependentMetrics([0,1],[.5,.5]).evaluate([2,3])['retrospective_recall_at_5percent']-.05)<1e-15
    assert np.isnan(IndependentMetrics([0,0],[.1,.3]).evaluate([1,1])['average_precision'])
    return {'status':'PASS','hand_computable_ties':m,'expected':expected,'independent_from_training_metric_module':True}


def quantile(x,w,q):
    x=np.asarray(x,float);w=np.asarray(w,float);good=np.isfinite(x)&np.isfinite(w)&(w>0)
    if not good.any():return np.nan
    ix=np.argsort(x[good],kind='stable');v=x[good][ix];ww=w[good][ix]
    return float(v[min(np.searchsorted(np.cumsum(ww),q*ww.sum(),side='left'),len(v)-1)])


def changed(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float)
    assert np.array_equal(np.isnan(a),np.isnan(b))
    return np.isfinite(a)&(np.abs(a-b)>1e-12*np.maximum(1,np.maximum(np.abs(a),np.abs(b))))


def cohort():
    d=pd.read_parquet(ROOT/'datasets/model_cohort.parquet')
    d['row_id']=d.cik+'|'+d.accession
    d['decision_date']=pd.to_datetime(d.decision_date)
    d['block']=d.decision_date.dt.year.map({y:b for b in BLOCKS for y in [int(b[:4]),int(b[-4:])]})
    d['mature_date']=d.decision_date+pd.Timedelta(days=455)
    assert len(d)==5502 and d.row_id.is_unique and d.registry_event_365.sum()==188
    return d


def four_cells_and_conditional_check():
    df=pd.read_parquet(OLD/'results/models/predictions.parquet')
    df=df[df.experiment.eq('original_four_cell')]
    rows=[];decomp=[]
    saved=pd.read_csv(OLD/'results/models/metrics.csv')
    errors=[]
    for (block,model),cell in df.groupby(['block','model']):
        cells={}
        for (u,v),d in cell.groupby(['train_version','score_version']):
            d=d.sort_values('row_id');m=IndependentMetrics(d.label,d.pred).evaluate(d.sample_weight)
            cells[u+v]=m
            rows.append({'block':block,'model':model,'cell':u+v,'n':len(d),'positive_windows':int(d.label.sum()),**m})
            ref=saved[(saved.experiment=='original_four_cell')&(saved.block==block)&(saved.model==model)&(saved.train_version==u)&(saved.score_version==v)].iloc[0]
            errors.extend(abs(m[k]-ref[k]) for k in METRICS)
        for k in METRICS:
            aa,ab,ba,bb=[cells[z][k] for z in ['AA','AB','BA','BB']]
            i,f,j,t=ab-aa,ba-aa,bb-ba-ab+aa,bb-aa
            decomp.append({'block':block,'model':model,'metric':k,'AA':aa,'AB':ab,'BA':ba,'BB':bb,'input_AB_minus_AA':i,'fit_BA_minus_AA':f,'interaction':j,'total_BB_minus_AA':t,'identity_error':t-(i+f+j)})
    write_csv('independent_four_cell_metrics.csv',rows);write_csv('four_cell_decomposition_unrounded.csv',decomp)
    assert max(errors)<1e-12
    # Original conditional Table 7 is independently reconstructed from original predictions.
    frame=pd.read_parquet(ROOT/'datasets/sampling_frame.parquet').drop_duplicates('cluster_id').sort_values('cluster_id')
    pool=frame[frame.sampling_stratum.eq('noncase_srs')]
    chosen=pool[pool.selected];order={x:i for i,x in enumerate(chosen.cluster_id)}
    n,N=len(chosen),len(pool);assert(n,N)==(1000,14546)
    counts=np.random.default_rng(20260921).multinomial(n-1,np.full(n,1/n),size=1000)
    mult=1+np.sqrt(1-n/N)*(n*counts/(n-1)-1)
    original=pd.read_parquet(ROOT/f'results/models_{RUNID}_test_predictions.parquet')
    original=original[original.model.isin(['LR','LGBM'])]
    conditional=[];reps=[]
    for (block,model),cell in original.groupby(['block','model']):
        a=cell[cell.version.eq('A')].set_index('row_id').sort_index();b=cell[cell.version.eq('B')].set_index('row_id').sort_index()
        assert a.index.equals(b.index)
        ca=IndependentMetrics(a.label,a.pred);cb=IndependentMetrics(b.label,b.pred)
        w=a.sample_weight.to_numpy();mask=a.sampling_stratum.eq('noncase_srs').to_numpy()
        ix=np.array([order[x] for x in a.loc[mask,'cluster_id']]);pa,pb=ca.evaluate(w),cb.evaluate(w)
        vals={k:[] for k in METRICS}
        for rep in range(1000):
            wr=w.copy();wr[mask]*=mult[rep,ix];ma,mb=ca.evaluate(wr),cb.evaluate(wr)
            for k in METRICS:
                delta=mb[k]-ma[k];vals[k].append(delta)
                reps.append({'block':block,'model':model,'replicate':rep,'metric':k,'AA':ma[k],'BB':mb[k],'delta':delta})
        for k,v in vals.items():
            qlo,qhi=np.quantile(v,[.025,.975]);point=pb[k]-pa[k]
            conditional.append({'block':block,'model':model,'metric':k,'AA':pa[k],'BB':pb[k],'delta':point,'ci95_low':2*point-qhi,'ci95_high':2*point-qlo,'valid_replicates':int(np.isfinite(v).sum())})
    cs=write_csv('independent_conditional_1000_summary.csv',conditional)
    pd.DataFrame(reps).to_parquet(OUT/'independent_conditional_1000_replicates.parquet',index=False)
    old=pd.read_csv(ROOT/'results/uncertainty_20260921T093555450801Z_summary.csv')
    compare=cs.merge(old,on=['block','model','metric'],suffixes=('_new','_old'))
    cierr=max((compare.ci95_low_new-compare.ci95_low_old).abs().max(),(compare.ci95_high_new-compare.ci95_high_old).abs().max())
    assert len(compare)==24 and cierr<1e-12
    return {'four_cell_max_abs_metric_error':max(errors),'conditional_CI_max_abs_error':cierr,'four_cell_metric_rows':len(rows),'conditional_summary_rows':len(cs),'status':'PASS'}


def perturbation_modes():
    baseline=pd.read_parquet(ROOT/f'results/models_{RUNID}_test_predictions.parquet')
    baseline=baseline[baseline.model.isin(['LR','LGBM'])].set_index(['block','model','version','row_id']).sort_index()
    records=[];audit=[]
    for rep in range(200):
        path=OLD/f'results/uncertainty/replicates/replicate_{rep:03d}/predictions.parquet'
        d=pd.read_parquet(path)
        for (block,model),cell in d.groupby(['block','model']):
            a=cell[cell.version.eq('A')].set_index('row_id').sort_index();b=cell[cell.version.eq('B')].set_index('row_id').sort_index()
            assert a.index.equals(b.index)
            for col in ['sample_weight','replicate_weight','registry_event_365','cluster_id']:
                assert np.array_equal(a[col].to_numpy(),b[col].to_numpy())
            oa=baseline.loc[(block,model,'A')].loc[a.index];ob=baseline.loc[(block,model,'B')].loc[a.index]
            assert np.array_equal(oa.label,a.registry_event_365) and np.array_equal(oa.sample_weight,a.sample_weight)
            ca,cb=IndependentMetrics(a.registry_event_365,a.prediction),IndependentMetrics(b.registry_event_365,b.prediction)
            olda,oldb=IndependentMetrics(oa.label,oa.pred),IndependentMetrics(ob.label,ob.pred)
            for mode,aa,bb,w in [('development_only',ca,cb,a.sample_weight),('evaluation_only',olda,oldb,a.replicate_weight),('joint',ca,cb,a.replicate_weight)]:
                ma,mb=aa.evaluate(w),bb.evaluate(w)
                for k in METRICS:
                    records.append({'replicate':rep,'block':block,'model':model,'mode':mode,'metric':k,'AA':ma[k],'BB':mb[k],'delta':mb[k]-ma[k]})
        audit.append({'replicate':rep,'prediction_rows':len(d),'paired_cells':6,'prediction_sha256':sha(path)})
        if (rep+1)%25==0:print('Re-evaluated saved perturbations',rep+1,'/200',flush=True)
    result=pd.DataFrame(records);result.to_parquet(OUT/'perturbation_modes_all_replicates.parquet',index=False)
    write_csv('perturbation_modes_all_replicates.csv',result)
    summaries=[]
    for keys,d in result.groupby(['block','model','mode','metric']):
        for quantity in ['AA','BB','delta']:
            v=d[quantity].to_numpy();good=np.isfinite(v);vv=v[good]
            entry=dict(zip(['block','model','mode','metric'],keys));entry.update(quantity=quantity,n=200,valid_n=int(good.sum()),valid_fraction=float(good.mean()))
            entry.update(mean=float(vv.mean()),sd=float(vv.std(ddof=1)),positive_fraction=float(np.mean(vv>0)),negative_fraction=float(np.mean(vv<0)),exact_zero_fraction=float(np.mean(vv==0)))
            entry.update({f'q{q*100:g}':float(np.quantile(vv,q)) for q in [.025,.05,.25,.5,.75,.95,.975]})
            summaries.append(entry)
    write_csv('perturbation_modes_distribution_summary.csv',summaries)
    old=pd.read_csv(OLD/'results/uncertainty/full_pipeline_paired_replicates.csv')
    joint=result[result['mode'].eq('joint')].merge(old,on=['replicate','block','model','metric'])
    err=float((joint.delta-joint.difference_B_minus_A).abs().max())
    assert len(joint)==4800 and err<1e-12
    write_json('perturbation_reuse_audit.json',{'status':'PASS','formal_replicates':200,'new_fits':0,'max_joint_delta_difference_from_frozen_result':err,'paired_checks':audit,'interpretation':'Dependent empirical distributions, not additive variance components and not generalization confidence intervals.'})
    return result


def load_manifest_sources():
    rows=[]
    for p in sorted((ROOT/'results').glob('corporate_access_manifest_*.json')):
        rows.extend(json.loads(p.read_text(encoding='utf-8')))
    for pattern in ['expanded_sec_manifest_*.jsonl','control_sec_manifest_*.jsonl']:
        for p in sorted((ROOT/'results').glob(pattern)):
            rows.extend(json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip())
    return {r['url']:r for r in rows if r.get('status')==200 and r.get('raw_path')}


def continuation(d):
    sources=load_manifest_sources();rows=[];cacheaudit={};failures=[]
    cutoff=pd.Timestamp('2026-09-21')
    def cache(url):
        if url not in sources:return None
        src=sources[url];p=ROOT/'cache/sec'/(src['sha256']+'.json')
        if not p.exists():return None
        assert sha(p)==src['sha256']
        cacheaudit[url]={'path':str(p),'sha256':src['sha256']}
        return json.loads(p.read_text(encoding='utf-8'))
    for cik,group in d.groupby('cik'):
        sub=cache(f'https://data.sec.gov/submissions/CIK{cik}.json')
        if sub is None:
            failures.append({'cik':cik,'reason':'main_submission_cache_unavailable'})
            rows.extend({'row_id':r.row_id,'annual_report_next365':np.nan,'continuity_observation_status':'unknown_main_metadata','next_annual_filing_date':'','next_annual_accession':''} for r in group.itertuples())
            continue
        frames=[pd.DataFrame(sub['filings']['recent'])];missing=[]
        for f in sub['filings'].get('files',[]):
            obj=cache('https://data.sec.gov/submissions/'+f['name'])
            if obj is not None:frames.append(pd.DataFrame(obj))
            else:missing.append(f)
        listings=pd.concat(frames,ignore_index=True).drop_duplicates('accessionNumber')
        listings['filed']=pd.to_datetime(listings.filingDate,errors='coerce')
        annual=listings[listings.form.isin(['10-K','10-KT'])&listings.filed.le(cutoff)].sort_values(['filed','accessionNumber'])
        for r in group.itertuples():
            start=r.decision_date;end=start+pd.Timedelta(days=365)
            hit=annual[annual.filed.gt(start)&annual.filed.le(end)]
            missing_relevant=[]
            for f in missing:
                lo=pd.to_datetime(f.get('filingFrom'),errors='coerce');hi=pd.to_datetime(f.get('filingTo'),errors='coerce')
                if pd.isna(lo) or pd.isna(hi) or (lo<=end and hi>start):missing_relevant.append(f['name'])
            complete=end<=cutoff and not missing_relevant
            observed=1.0 if len(hit) else (0.0 if complete else np.nan)
            rows.append({'row_id':r.row_id,'annual_report_next365':observed,
                         'continuity_observation_status':'observed_presence' if len(hit) else ('covered_no_annual_filing' if complete else 'unknown_incomplete_interval'),
                         'next_annual_filing_date':str(hit.iloc[0].filed.date()) if len(hit) else '',
                         'next_annual_accession':hit.iloc[0].accessionNumber if len(hit) else '',
                         'continuity_start_exclusive':str(start.date()),'continuity_end_inclusive':str(end.date()),
                         'missing_history_intersecting_interval':'|'.join(missing_relevant)})
    result=pd.DataFrame(rows)
    result.to_parquet(OUT/'annual_filing_continuity_by_landmark.parquet',index=False)
    write_json('continuity_cache_audit.json',{'status':'AVAILABLE_WITH_EXPLICIT_KNOWABILITY','definition':'Retrospectively observed original 10-K/10-KT strictly after origin and no later than origin+365 days; not bankruptcy or survival status. Main and historical official submissions D-cache only. Missing history overlapping the interval forbids treating absence as zero.','loaded_cache_count':len(cacheaudit),'cache_files':cacheaudit,'main_failures':failures,'statuses':result.continuity_observation_status.value_counts().to_dict(),'finite_source_cutoff':'2026-09-21'})
    return result


def domains(d,all_labels=False):
    for domain in ['full_cohort']+BLOCKS:
        s=d if domain=='full_cohort' else d[d.block.eq(domain)]
        for label in (['all',0,1] if all_labels else [0,1]):
            yield domain,label,s if label=='all' else s[s.registry_event_365.eq(label)]


def exposure_and_magnitude(d):
    f=pd.read_parquet(ROOT/'datasets/vintage_facts.parquet')
    f['row_id']=f.cik+'|'+f.original_accession
    f=f[f.row_id.isin(d.row_id)].copy()
    assert not f.duplicated(['row_id','feature']).any()
    f['changed_tolerance']=changed(f.A,f.B);f['changed_exact']=f.A.ne(f.B)
    wmap=d.set_index('row_id').sample_weight
    f['sample_weight']=f.row_id.map(wmap)
    e=d.copy();e['later_available']=e.later_accession.fillna('').ne('')
    rawchange=f.groupby('row_id').changed_tolerance.any();e['raw_changed']=e.row_id.map(rawchange).fillna(False).astype(bool)
    assert not (e.raw_changed&~e.later_available).any()
    e['exposure_group']=np.where(~e.later_available,'no_later_bundle',np.where(e.raw_changed,'later_with_raw_change','later_without_raw_change'))
    e['A_missing_raw_components']=11-e.n_original_facts
    e['A_missing_model_inputs']=e[['A_'+x for x in FEATURES]].isna().sum(axis=1)
    e['A_assets']=np.exp(e.A_log_assets)
    e=e.merge(continuation(d),on='row_id',validate='one_to_one')
    erows=[]
    for domain,label,s in domains(e):
        den=float(s.sample_weight.sum())
        for group in ['no_later_bundle','later_without_raw_change','later_with_raw_change']:
            g=s[s.exposure_group.eq(group)];w=g.sample_weight.to_numpy();known=g.annual_report_next365.notna()
            rec={'domain':domain,'label':label,'exposure_group':group,'label_denominator_raw_n':len(s),'label_denominator_weighted_mass':den,'raw_n':len(g),'weighted_mass':float(w.sum()),'within_label_raw_fraction':len(g)/len(s) if len(s) else np.nan,'within_label_weighted_fraction':w.sum()/den if den else np.nan,'distinct_ciks':g.cik.nunique(),'distinct_sampling_clusters':g.cluster_id.nunique()}
            for col in ['A_missing_raw_components','A_missing_model_inputs','A_log_assets','A_assets']:
                rec[col+'_weighted_mean']=np.average(g[col],weights=w) if len(g) else np.nan
                rec[col+'_weighted_median']=quantile(g[col],w,.5)
            rec.update(continuity_known_raw_n=int(known.sum()),continuity_unknown_raw_n=int((~known).sum()),continuity_known_weighted_mass=float(g.loc[known,'sample_weight'].sum()),continuity_positive_raw_n=int(g.annual_report_next365.eq(1).sum()),continuity_within_known_weighted_fraction=np.average(g.loc[known,'annual_report_next365'],weights=g.loc[known,'sample_weight']) if known.any() else np.nan)
            erows.append(rec)
    write_csv('version_exposure_summary.csv',erows)
    e.to_parquet(OUT/'version_exposure_by_landmark.parquet',index=False)
    a=f.A.to_numpy(float);b=f.B.to_numpy(float)
    f['sign_category']=np.select([(a==0)&(b==0),(a==0)&(b!=0),(a!=0)&(b==0),(a*b<0)],['both_zero','zero_to_nonzero','nonzero_to_zero','sign_flip'],default='same_sign_nonzero')
    f['original_relative_amplitude']=np.abs(b-a)/np.maximum(1,np.maximum(np.abs(a),np.abs(b)))
    f['log10_absolute_ratio']=np.nan;mask=f.sign_category.eq('same_sign_nonzero')
    f.loc[mask,'log10_absolute_ratio']=np.log10(np.abs(f.loc[mask,'B']))-np.log10(np.abs(f.loc[mask,'A']))
    f['absolute_log10_ratio']=f.log10_absolute_ratio.abs()
    f['multiplicative_fold']=np.power(10.,f.absolute_log10_ratio)
    f.to_parquet(OUT/'raw_component_change_magnitudes.parquet',index=False)
    mrows=[];signrows=[]
    for feature,g in f.groupby('feature'):
        totalw=g.sample_weight.sum()
        for category in ['same_sign_nonzero','sign_flip','both_zero','zero_to_nonzero','nonzero_to_zero']:
            x=g[g.sign_category.eq(category)]
            signrows.append({'feature':feature,'sign_category':category,'observed_pair_raw_denominator':len(g),'observed_pair_weighted_denominator':totalw,'raw_n':len(x),'weighted_mass':x.sample_weight.sum(),'weighted_fraction_observed_pairs':x.sample_weight.sum()/totalw})
        subsets={'all_observed_pairs':g,'changed_pairs':g[g.changed_tolerance],'same_sign_nonzero':g[g.sign_category.eq('same_sign_nonzero')],'same_sign_nonzero_changed':g[g.sign_category.eq('same_sign_nonzero')&g.changed_tolerance]}
        for subset,x in subsets.items():
            for measure in ['original_relative_amplitude','log10_absolute_ratio','absolute_log10_ratio','multiplicative_fold']:
                good=x[measure].notna();xx=x[good]
                rec={'feature':feature,'subset':subset,'measure':measure,'raw_n':len(xx),'weighted_mass':xx.sample_weight.sum(),'observed_pair_raw_denominator':len(g),'observed_pair_weighted_denominator':totalw}
                rec.update({f'weighted_q{q*100:g}':quantile(xx[measure],xx.sample_weight,q) for q in [.05,.25,.5,.75,.95,.99]})
                rec['max']=float(xx[measure].max()) if len(xx) else np.nan;mrows.append(rec)
    write_csv('raw_component_magnitude_summary.csv',mrows);write_csv('raw_component_sign_categories.csv',signrows)
    return e,f


def adjacent_versions(d,f):
    caps={str(c):pd.read_parquet(OLD/f'datasets/cap_{c}.parquet') for c in [90,365,730]}
    caps['latest']=d.copy()
    for key,v in caps.items():
        v['row_id']=v.cik+'|'+v.accession;caps[key]=v.set_index('row_id').loc[d.row_id]
    raw=pd.read_parquet(OLD/'results/version_caps/cap_fact_lineage.parquet')
    raw['row_id']=raw.cik+'|'+raw.accession
    facts={str(c):x.set_index(['row_id','feature']).capped for c,x in raw.groupby('cap_days')}
    facts['latest']=f.set_index(['row_id','feature']).B
    out=[];component=[]
    for lo,hi in [('90','365'),('365','730'),('730','latest')]:
        a,b=caps[lo],caps[hi]
        av=a.later_accession.fillna('').ne('');bv=b.later_accession.fillna('').ne('')
        sa=a.later_accession.fillna('').where(av,a.accession);sb=b.later_accession.fillna('').where(bv,b.accession)
        ra,rb=facts[lo].align(facts[hi]);assert ra.notna().all() and rb.notna().all()
        cr=pd.DataFrame({'previous_raw':ra,'next_raw':rb});cr['exact_change']=cr.previous_raw.ne(cr.next_raw);cr['tolerance_change']=changed(cr.previous_raw,cr.next_raw)
        cr['transition']=lo+'_to_'+hi;component.append(cr.reset_index())
        counts=cr.groupby(level='row_id')[['exact_change','tolerance_change']].sum()
        ch=changed(a[['B_'+x for x in FEATURES]],b[['B_'+x for x in FEATURES]])
        for i,r in enumerate(d.itertuples()):
            rid=r.row_id;oldavailable=bool(av.loc[rid]);newavailable=bool(bv.loc[rid]);same=sa.loc[rid]==sb.loc[rid]
            out.append({'row_id':rid,'block':r.block,'label':r.registry_event_365,'sample_weight':r.sample_weight,'transition':lo+'_to_'+hi,'previous_source':sa.loc[rid],'next_source':sb.loc[rid],'previous_later_available':oldavailable,'next_later_available':newavailable,'newly_available':not oldavailable and newavailable,'lost_availability':oldavailable and not newavailable,'existing_bundle_accession_switch':oldavailable and newavailable and not same,'same_selected_source':same,'raw_components_changed_exact':int(counts.loc[rid,'exact_change']),'raw_components_changed_tolerance':int(counts.loc[rid,'tolerance_change']),'model_features_changed':int(ch[i].sum()),'same_source_raw_values_changed':same and bool(counts.loc[rid,'exact_change']),'existing_bundle_raw_changed':oldavailable and bool(counts.loc[rid,'tolerance_change']),'existing_bundle_model_changed':oldavailable and bool(ch[i].any())})
    x=pd.DataFrame(out);x.to_parquet(OUT/'adjacent_horizon_by_landmark.parquet',index=False)
    pd.concat(component,ignore_index=True).to_parquet(OUT/'adjacent_horizon_raw_component_changes.parquet',index=False)
    x['registry_event_365']=x.label
    summaries=[]
    bools=['newly_available','lost_availability','existing_bundle_accession_switch','same_selected_source','same_source_raw_values_changed','existing_bundle_raw_changed','existing_bundle_model_changed']
    for trans,t in x.groupby('transition'):
        for domain,label,g in domains(t,True):
            w=g.sample_weight;rec={'transition':trans,'domain':domain,'label':label,'raw_n':len(g),'weighted_denominator':w.sum()}
            for col in bools:
                rec[col+'_n']=int(g[col].sum());rec[col+'_weighted_fraction']=float(np.average(g[col],weights=w)) if len(g) else np.nan
            for col in ['raw_components_changed_exact','raw_components_changed_tolerance','model_features_changed']:
                rec[col+'_landmarks_n']=int(g[col].gt(0).sum());rec[col+'_cells_n']=int(g[col].sum());rec[col+'_landmark_weighted_fraction']=float(np.average(g[col].gt(0),weights=w)) if len(g) else np.nan
            summaries.append(rec)
    write_csv('adjacent_horizon_summary.csv',summaries)
    assert not x.lost_availability.any(),'Later-bundle availability must be monotone under nested caps'
    assert not x.same_source_raw_values_changed.any(),'Same accession unexpectedly supplies changing raw values'


def training_source_time(d):
    records=[];summary=[]
    membership_path=ROOT/f'results/models_{RUNID}_split_membership.parquet'
    membership=pd.read_parquet(membership_path)
    row_identity_checks=[]
    for block in BLOCKS:
        cutoff=pd.Timestamp(int(block[:4]),1,1)
        x=d[d.mature_date.le(cutoff)].copy()
        saved_ids=set(membership.loc[membership.block.eq(block)&membership.role.eq('refit'),'row_id'])
        assert set(x.row_id)==saved_ids,'Reconstructed final-refit membership differs from frozen fit'
        row_identity_checks.append({'block':block,'reconstructed_n':len(x),'saved_n':len(saved_ids),'exact_row_set_match':True})
        source=pd.to_datetime(x.later_filed,errors='coerce');available=x.later_accession.fillna('').ne('')
        assert source[available].notna().all()
        x['selected_B_source_time_category']=np.select([~available,source.lt(cutoff),source.eq(cutoff),source.gt(cutoff)],['A_fallback_no_later','later_before_fit','later_on_fit_date','later_after_fit'],default='ERROR')
        x['fit_block']=block;x['fit_cutoff']=cutoff.strftime('%Y-%m-%d');x['fit_stage']='final_refit'
        assert not x.selected_B_source_time_category.eq('ERROR').any()
        x['B_model_input_changed']=changed(x[['A_'+z for z in FEATURES]],x[['B_'+z for z in FEATURES]]).any(axis=1)
        records.append(x[['row_id','cik','cluster_id','fit_block','fit_stage','fit_cutoff','decision_date','mature_date','sample_weight','registry_event_365','later_accession','later_filed','n_coherent_changed','B_model_input_changed','selected_B_source_time_category']])
        for category in ['A_fallback_no_later','later_before_fit','later_on_fit_date','later_after_fit']:
            g=x[x.selected_B_source_time_category.eq(category)]
            summary.append({'block':block,'fit_stage':'final_refit','fit_cutoff':str(cutoff.date()),'category':category,'raw_n':len(g),'weighted_mass':g.sample_weight.sum(),'refit_raw_denominator':len(x),'refit_weighted_denominator':x.sample_weight.sum(),'later_available_raw_denominator':int(available.sum()),'later_available_weighted_denominator':x.loc[available,'sample_weight'].sum(),'fraction_all_refit_raw':len(g)/len(x),'fraction_all_refit_weighted':g.sample_weight.sum()/x.sample_weight.sum(),'fraction_available_refit_raw':len(g)/int(available.sum()) if category!='A_fallback_no_later' else np.nan,'fraction_available_refit_weighted':g.sample_weight.sum()/x.loc[available,'sample_weight'].sum() if category!='A_fallback_no_later' else np.nan,'raw_changed_landmarks':int(g.n_coherent_changed.gt(0).sum()),'model_input_changed_landmarks':int(g.B_model_input_changed.sum()),'model_changed_weighted_mass':g.loc[g.B_model_input_changed,'sample_weight'].sum()})
    full=pd.concat(records,ignore_index=True)
    full.to_parquet(OUT/'training_B_source_timing_by_landmark.parquet',index=False)
    write_csv('training_B_source_timing_summary.csv',summary)
    expected={'2016_2017':2024,'2018_2019':3167,'2020_2021':4161}
    assert full.groupby('fit_block').size().to_dict()==expected
    write_json('training_time_definition.json',{'status':'PASS_EXACT_SAVED_REFIT_MEMBERSHIP','cutoff':'Jan1 first test year; model final refit, not each original observation origin','maturity':'origin+365+90days <= cutoff','future_definition':'Selected later B source filed strictly after cutoff. Same-day source is separately reported because time-of-day is unavailable.','refit_counts':expected,'row_identity_checks':row_identity_checks,'validation_reference':{'path':str(membership_path),'sha256':sha(membership_path),'use':'Post-computation validation reference only; no definition change from frozen plan.'},'distinction':'Historical revisions after a training row origin but before the final fit date are not future relative to that fit cutoff. All versions remain current-API reconstructions.'})


def extra_validation(d):
    """Checks on existing computed outputs; no new estimator or fitted model."""
    e=pd.read_parquet(OUT/'version_exposure_by_landmark.parquet')
    assert e.raw_changed.eq(e.n_coherent_changed.gt(0)).all()
    assert e.groupby('registry_event_365').size().to_dict()=={0:5314,1:188}
    # A historical metadata frame is an independent coverage cross-check only where
    # its 2021 end fully contains the chosen 365-day observation interval.
    frame=pd.read_parquet(ROOT/'datasets/universe_annual_filings_2010_2021.parquet')
    frame['filed']=pd.to_datetime(frame.filing_date)
    byc={str(k):v for k,v in frame.groupby('cik')}
    comparisons=[]
    for row in e.itertuples():
        end=row.decision_date+pd.Timedelta(days=365)
        if end>pd.Timestamp('2021-12-31'):continue
        f=byc.get(row.cik)
        hit=bool(f is not None and (f.filed.gt(row.decision_date)&f.filed.le(end)).any())
        comparisons.append({'row_id':row.row_id,'official_submission_presence':row.annual_report_next365,'historical_frame_presence':int(hit),'agree':np.isfinite(row.annual_report_next365) and int(row.annual_report_next365)==int(hit)})
    comp=pd.DataFrame(comparisons);write_csv('continuity_historical_frame_crosscheck.csv',comp)
    # Validate saved replicate weights against every frozen PSU multiplier, including
    # the complete 1000-column draw inventory (not only PSUs appearing in test rows).
    clusters=pd.read_csv(OLD/'results/uncertainty/replicate_cluster_order.csv',dtype={'cluster_id':str})
    mult=np.load(OLD/'results/uncertainty/replicate_multipliers.npy')
    assert mult.shape==(200,1000) and len(clusters)==1000
    index=dict(zip(clusters.cluster_id,clusters.multiplier_column));maxerr=0.
    cohort_clusters=set(d.cluster_id)
    for b in range(200):
        x=pd.read_parquet(OLD/f'results/uncertainty/replicates/replicate_{b:03d}/predictions.parquet')
        multiplier=np.array([mult[b,index[c]] if c in index else 1. for c in x.cluster_id])
        err=np.max(np.abs(x.sample_weight.to_numpy()*multiplier-x.replicate_weight.to_numpy()))
        maxerr=max(maxerr,float(err));assert err<1e-12
    write_json('additional_validation.json',{'status':'PASS','source_change_classification_matches_frozen_exact_raw_count':True,'all_cohort_label_counts':{0:5314,1:188},'replicate_multiplier_shape':[200,1000],'max_saved_weight_multiplier_error':maxerr,'noncase_draw_units_without_any_cohort_row':int(sum(c not in cohort_clusters for c in clusters.cluster_id)),
          'continuity_independent_frame_check':{'eligible_full_intervals':len(comp),'agreements':int(comp.agree.sum()),'disagreements':int((~comp.agree).sum()),'interpretation':'Archived historical master index and current official submissions are different metadata routes. Discrepancies are disclosed, not silently recoded; official listings define the descriptive continuation variable.'},
          'implementation_note':'Initial self-test used exact floating equality for 5%-capacity tie recall and stopped before empirical output. Replaced only this assertion by absolute tolerance1e-15; no metric formula or frozen analysis definition changed. Final additional checks do not change estimates.'})


def findings():
    decomp=pd.read_csv(OUT/'four_cell_decomposition_unrounded.csv');s=pd.read_csv(OUT/'perturbation_modes_distribution_summary.csv')
    exp=pd.read_csv(OUT/'version_exposure_summary.csv');adj=pd.read_csv(OUT/'adjacent_horizon_summary.csv');tt=pd.read_csv(OUT/'training_B_source_timing_summary.csv')
    lines=['# Evaluation diagnostics round 2','',
           'All outputs use frozen empirical data and saved predictions. No model was refitted. All added analyses are post hoc explanatory diagnostics.','',
           '## Unrounded four-cell AP contrasts (percentage points)','',
           '| Block | Input AB-AA | Fit BA-AA | Interaction | Total BB-AA |','|---|---:|---:|---:|---:|']
    for r in decomp[(decomp.model=='LGBM')&(decomp.metric=='average_precision')].itertuples():
        lines.append(f'|{r.block}|{100*r.input_AB_minus_AA:.9f}|{100*r.fit_BA_minus_AA:.9f}|{100*r.interaction:.9f}|{100*r.total_BB_minus_AA:.9f}|')
    lines+=['','## Paired AP perturbation modes','', '| Block | Model | Mode | Median pp | 5th–95th pp | Positive fraction |','|---|---|---|---:|---:|---:|']
    for r in s[(s.metric=='average_precision')&(s.quantity=='delta')].to_dict('records'):
        lines.append(f"|{r['block']}|{r['model']}|{r['mode']}|{100*r['q50']:.6f}|[{100*r['q5']:.6f}, {100*r['q95']:.6f}]|{r['positive_fraction']:.3f}|")
    lines+=['','These are the same paired draws in three computational modes, not independent experiments or additive variance components. Empirical quantiles are not confidence limits. Evaluation-only uses the same 200 draws as joint and development-only; the older conditional table uses its separate frozen 1000-draw seed.','',
            '## Full-cohort version exposure','',exp[exp.domain=='full_cohort'][['label','exposure_group','raw_n','within_label_weighted_fraction','continuity_known_raw_n','continuity_unknown_raw_n','continuity_within_known_weighted_fraction']].to_csv(index=False),
            'The denominator is all landmarks with the specified label. Continuity is the presence of a subsequent original annual filing in a fixed 365-day interval. It is a retrospective reporting-process variable, not a deployment feature or proof of survival.','',
            '## Adjacent source horizons','',adj[(adj.domain=='full_cohort')&(adj.label.astype(str)=='all')][['transition','newly_available_n','existing_bundle_accession_switch_n','raw_components_changed_tolerance_landmarks_n','model_features_changed_landmarks_n','same_source_raw_values_changed_n']].to_csv(index=False),
            'Source switching among previously available bundles is distinct from newly obtaining a bundle. Identical selected source accessions must not change raw values in this frozen reconstruction.','',
            '## Selected B sources after final fit date','',tt[tt.category=='later_after_fit'][['block','fit_cutoff','raw_n','refit_raw_denominator','fraction_all_refit_weighted','model_input_changed_landmarks']].to_csv(index=False),
            'Use the separately reported same-day category if requiring strict availability before the start of the cutoff date. The table describes the final refit partition, not tuning/validation fits.','',
            '## File interface','',
            '- `perturbation_modes_all_replicates.parquet/csv`: replicate × block × model × mode × metric, AA/BB/delta in metric units.',
            '- `perturbation_modes_distribution_summary.csv`: each AA/BB/delta distribution, all raw probability-scale metrics (multiply AP by100 for percentage points).',
            '- `independent_four_cell_metrics.csv`, `four_cell_decomposition_unrounded.csv`, `independent_conditional_1000_summary.csv`: independent arithmetic and conditional interval reproduction.',
            '- `version_exposure_by_landmark.parquet`, `version_exposure_summary.csv`: exposure and future continuation with explicit denominators.',
            '- `adjacent_horizon_by_landmark.parquet`, `adjacent_horizon_summary.csv`, `adjacent_horizon_raw_component_changes.parquet`: accession and value changes between nested horizons.',
            '- `raw_component_change_magnitudes.parquet`, `raw_component_magnitude_summary.csv`, `raw_component_sign_categories.csv`: Figure2-ready source values and separate scale/sign summaries.',
            '- `training_B_source_timing_by_landmark.parquet`, `training_B_source_timing_summary.csv`: final-fitting information boundary.',
            '- `design.json`, `manifest.json`, and audit JSONs: source hashes, fixed definitions and validation.',
            '', 'No plot or manuscript file was created or changed.']
    (OUT/'findings.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def run():
    start=time.perf_counter();design=json.loads((OUT/'design.json').read_text(encoding='utf-8'));verify_sources(design)
    write_json('self_test.json',self_test())
    reproduction=four_cells_and_conditional_check();write_json('independent_metric_audit.json',reproduction)
    perturbation_modes()
    d=cohort();e,f=exposure_and_magnitude(d);adjacent_versions(d,f);training_source_time(d);extra_validation(d)
    findings();verify_sources(design)
    write_json('manifest.json',{'status':'COMPLETE','completed_utc':datetime.now(timezone.utc).isoformat(),'script_path':str(Path(__file__).resolve()),'script_sha256':sha(__file__),'design_sha256':sha(OUT/'design.json'),'new_model_fits':0,'network_requests':0,'seconds':time.perf_counter()-start,'frozen_sources_unchanged':True,'outputs':[{'path':str(p),'sha256':sha(p)} for p in sorted(OUT.glob('*')) if p.is_file() and p.name!='manifest.json']})
    print('COMPLETE',time.perf_counter()-start,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','run']);args=parser.parse_args()
    if args.mode=='prepare':prepare()
    else:run()
