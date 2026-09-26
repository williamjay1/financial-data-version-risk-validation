"""Final-fit information cutoff diagnostic from immutable D: source caches."""
from pathlib import Path
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='2'
import sys
sys.dont_write_bytecode=True
import json
from datetime import datetime, timezone
import shutil
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import average_precision_score, roc_auc_score

REV=Path(__file__).resolve().parents[1]
ROOT=REV.parent
OLD=ROOT/'revision_20260922'
sys.path.insert(0,str(OLD/'scripts'))
import revision_models as rm
import version_caps as vc
vp=vc.vp
OUT=REV/'results/fit_date'
DATA=REV/'datasets'

def run():
    assert shutil.disk_usage(REV).free>2*1024**3
    OUT.mkdir(parents=True,exist_ok=True)
    DATA.mkdir(exist_ok=True)
    assert not (OUT/'manifest.json').exists(),'Use a new run directory for repeated execution'
    df,binding=rm.load_base()
    splits=rm.base.make_splits(df)
    plan={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'frozen_before_execution',
          'cohort_sha256':binding['input_sha256'],'script_sha256':rm.base.sha256(__file__),
          'cutoff':'strictly before final fit date (test-block 1 January); filing dates have no intraday ordering',
          'training':'original final refit rows and weights; original fixed parameters; no candidate selection',
          'scoring':'original accession-associated A at each test origin; complete original test population',
          'models':{k:rm.FIXED[k] for k in ['LR','LGBM']},
          'interpretation':'Current-API filing-date reconstruction, not a historical API snapshot',
          'safety':'Stop on reconstruction, positive denominator or mask discrepancy; never silently drop rows'}
    rm.base.write_json(OUT/'plan.json',plan)
    frames={s['block']:df.copy() for s in splits}
    trains={s['block']:set(s['indices']['refit']) for s in splits}
    for frame in frames.values():
        for f in rm.base.FEATURES:frame['B_'+f]=frame['A_'+f]
    sources=vp.sources()
    lineage=[];facts=[];check_count=0
    for number,(cik,rows) in enumerate(df.groupby('cik'),1):
        sub=vc.cache(sources[f'https://data.sec.gov/submissions/CIK{cik}.json'])
        files=[pd.DataFrame(sub['filings']['recent'])]
        for older in sub['filings'].get('files',[]):
            url='https://data.sec.gov/submissions/'+older['name']
            if url in sources:files.append(pd.DataFrame(vc.cache(sources[url])))
        filings=pd.concat(files,ignore_index=True).drop_duplicates('accessionNumber')
        fmap={r['accessionNumber']:r for r in filings.to_dict('records')}
        lookup=vp.fact_lookup(vc.cache(sources[f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json']))
        for idx,row in rows.iterrows():
            original=fmap[row.accession]
            a,ctx,amb=vp.snapshot(original,lookup)
            b,latest,_,_=vp.later_bundle(a,ctx,original,lookup,fmap)
            for version,raw in [('A',a),('B',b)]:
                v=np.array([vp.ratios(raw)[f] for f in rm.base.FEATURES])
                assert np.allclose(v,row[[version+'_'+f for f in rm.base.FEATURES]].to_numpy(float),rtol=1e-12,atol=1e-12,equal_nan=True)
                check_count+=1
            assert latest==row.later_accession
            eligible=None;byfeature={}
            for feature,c in ctx.items():
                valid={}
                for acc,records in lookup[c['tag']].items():
                    filing=fmap.get(acc)
                    if not filing or not original['filingDate']<filing['filingDate']<=vp.CUTOFF:continue
                    values={r['val'] for r in records if r.get('start','')==c['start'] and r.get('end')==c['end']}
                    if len(values)==1:valid[acc]=float(next(iter(values)))
                byfeature[feature]=valid
                eligible=set(valid) if eligible is None else eligible.intersection(valid)
            options=sorted(eligible or [],key=lambda k:(fmap[k]['filingDate'],k))
            for split in splits:
                block=split['block']
                if idx not in trains[block]:continue
                cutoff=str(split['test_start'].date())
                candidates=[a for a in options if fmap[a]['filingDate']<cutoff]
                chosen=candidates[-1] if candidates else ''
                raw=a.copy()
                if chosen:raw.update({f:valid[chosen] for f,valid in byfeature.items()})
                features=vp.ratios(raw)
                av=np.array([vp.ratios(a)[f] for f in rm.base.FEATURES])
                fv=np.array([features[f] for f in rm.base.FEATURES])
                assert raw['assets']>0 and np.isfinite(raw['assets'])
                assert np.array_equal(np.isnan(av),np.isnan(fv))
                for f,value in features.items():frames[block].at[idx,'B_'+f]=value
                selected=chosen or row.accession
                filed=fmap[selected]['filingDate']
                assert filed<cutoff
                lineage.append({'block':block,'row_id':row.row_id,'cik':cik,'original_accession':row.accession,
                    'fit_date':cutoff,'decision_date':str(row.decision_date.date()),'selected_accession':selected,
                    'selected_filed':filed,'later_available':bool(chosen),'latest_accession':latest or row.accession,
                    'latest_filed':fmap[latest or row.accession]['filingDate'],
                    'latest_not_available_at_fit':bool(latest and fmap[latest]['filingDate']>=cutoff),
                    'registry_event_365':int(row.registry_event_365),'sample_weight':row.sample_weight,
                    'n_changed_raw':int(sum(a[f]!=raw[f] for f in ctx)),
                    'n_changed_features':int((~np.isclose(av,fv,rtol=0,atol=0,equal_nan=True)).sum())})
                for f,c in ctx.items():facts.append({'block':block,'row_id':row.row_id,'component':f,
                    'tag':c['tag'],'unit':'USD','start':c['start'],'end':c['end'],'A':a[f],
                    'fit_date_value':raw[f],'selected_accession':selected,'selected_filed':filed})
        if number%100==0:print(json.dumps({'companies':number,'baseline_checks':check_count}),flush=True)
    assert check_count==2*len(df)
    trace=pd.DataFrame(lineage)
    trace.to_parquet(OUT/'fit_date_lineage.parquet',index=False)
    pd.DataFrame(facts).to_parquet(OUT/'fit_date_fact_lineage.parquet',index=False)
    summaries=[]
    for block,g in trace.groupby('block'):
        record={'block':block,'n_train':len(g),'n_train_positive':int(g.registry_event_365.sum())}
        for col in ['later_available','latest_not_available_at_fit']:
            record[col+'_n']=int(g[col].sum());record[col+'_weighted_percent']=100*np.average(g[col],weights=g.sample_weight)
        for col in ['n_changed_raw','n_changed_features']:
            record[col+'_windows']=int(g[col].gt(0).sum())
        record['asof_latest_source_differ_n']=int(g.selected_accession.ne(g.latest_accession).sum())
        summaries.append(record)
    pd.DataFrame(summaries).to_csv(OUT/'fit_date_coverage.csv',index=False)
    rec=rm.Recorder(OUT/'models')
    for split in splits:
        block=split['block'];frame=frames[block];train=split['indices']['refit'];test=split['indices']['test']
        frame=attach_active_lineage(frame,trace,block)
        source=DATA/f'fit_date_{block}.parquet';frame.to_parquet(source,index=False)
        assert np.array_equal(frame.row_id,df.row_id)
        assert frame.loc[train,'mature_date'].le(split['test_start']).all()
        for model in ['LR','LGBM']:
            bundle=rm.fit_pipeline(frame,train,'B',model)
            assert bundle['converged']
            rec.save_fit(bundle,'fit_date',block,'B',model)
            rec.score(bundle,frame,test,'fit_date',block,'B','A',model)
            for version in ['A','B']:
                anchor=joblib.load(OLD/'results/models/artifacts'/f'fixed_full__{block}__{version}__{model}.joblib')
                assert anchor['train_row_ids']==df.loc[train,'row_id'].tolist()
                rec.score(anchor,df,test,'original_fixed_anchor',block,version,'A',model)
        rec.split(frame,train,'fit_date',block,'refit',split['test_start'])
        rec.flush()
    finalize(check_count,summaries)

def attach_active_lineage(frame,trace,block):
    frame=frame.copy()
    if 'unlimited_later_accession' not in frame:
        frame['unlimited_later_accession']=frame['later_accession']
        frame['unlimited_later_filed']=frame['later_filed']
    frame['later_accession']=''
    frame['later_filed']=''
    frame['n_coherent_changed']=0
    frame['feature_information_rule']='A outside eligible training; before-fit coherent bundle inside training'
    index={rid:i for i,rid in zip(frame.index,frame.row_id)}
    for row in trace.loc[trace.block.eq(block)].itertuples():
        i=index[row.row_id]
        if row.later_available:
            frame.at[i,'later_accession']=row.selected_accession
            frame.at[i,'later_filed']=row.selected_filed
        frame.at[i,'n_coherent_changed']=row.n_changed_raw
    return frame

def finalize(check_count=None,summaries=None):
    if check_count is None:
        check_count=11004
        summaries=pd.read_csv(OUT/'fit_date_coverage.csv').to_dict('records')
        rm.base.write_json(OUT/'completion_amendment.json',{
            'reason':'Metric-only finalizer corrected probability column name to the Recorder schema prediction.',
            'effect':'No source construction, model training, predictions or scientific specification changed.',
            'reran_training':False,'prediction_sha256':rm.base.sha256(OUT/'models/predictions.parquet'),
            'original_execution_script_sha256':json.loads((OUT/'plan.json').read_text(encoding='utf-8'))['script_sha256'],
            'corrected_script_sha256':rm.base.sha256(__file__)})
        lineage=pd.read_parquet(OUT/'fit_date_lineage.parquet')
        metadata_changes=[]
        for block in sorted(lineage.block.unique()):
            path=DATA/f'fit_date_{block}.parquet'
            before=pd.read_parquet(path)
            before_hash=rm.base.sha256(path)
            after=attach_active_lineage(before,lineage,block)
            inputs=[a+'_'+f for a in ['A','B','C'] for f in rm.base.FEATURES]
            pd.testing.assert_frame_equal(before[inputs],after[inputs],check_exact=True)
            after.to_parquet(path,index=False)
            metadata_changes.append({'block':block,'before_sha256':before_hash,'after_sha256':rm.base.sha256(path)})
        rm.base.write_json(OUT/'lineage_metadata_amendment.json',{
            'reason':'Make active B-source metadata describe fit-date-selected values; preserve original latest-source metadata with unlimited_ prefix.',
            'all_numerical_inputs_identical':True,'reran_training':False,'datasets':metadata_changes})
    predictions=pd.read_parquet(OUT/'models/predictions.parquet')
    metrics=pd.read_csv(OUT/'models/metrics.csv')
    checks=[]
    for _,m in metrics.iterrows():
        p=predictions.loc[(predictions.experiment==m.experiment)&(predictions.block==m.block)&(predictions.model==m.model)&(predictions.train_version==m.train_version)]
        probs=p['prediction'].to_numpy();y=p.registry_event_365.to_numpy();w=p.sample_weight.to_numpy()
        vals={'average_precision':average_precision_score(y,probs,sample_weight=w),
              'brier':np.average((y-probs)**2,weights=w),'roc_auc':roc_auc_score(y,probs,sample_weight=w)}
        for key,value in vals.items():checks.append(abs(value-m[key]))
    assert max(checks)<1e-12
    contrasts=[]
    for (block,model),g in metrics.groupby(['block','model']):
        anchor=g.loc[(g.experiment=='original_fixed_anchor')&(g.train_version=='A')].iloc[0]
        past=g.loc[g.experiment=='fit_date'].iloc[0]
        latest=g.loc[(g.experiment=='original_fixed_anchor')&(g.train_version=='B')].iloc[0]
        for metric in ['average_precision','brier','roc_auc','retrospective_recall_at_5percent']:
            contrasts.append({'block':block,'model':model,'metric':metric,'original_A_train_A_score':anchor[metric],
                 'fit_date_train_A_score':past[metric],'latest_B_train_A_score':latest[metric],
                 'fit_date_minus_original':past[metric]-anchor[metric],'latest_minus_fit_date':latest[metric]-past[metric]})
    pd.DataFrame(contrasts).to_csv(OUT/'fit_date_comparisons.csv',index=False)
    manifest={'status':'PASS','finished_utc':datetime.now(timezone.utc).isoformat(),'original_reconstruction_checks':check_count,
        'fits':6,'independent_metric_cells':len(checks),'max_metric_difference':max(checks),
        'cohort_sha256':rm.base.sha256(ROOT/'datasets/model_cohort.parquet'),
        'plan_sha256':rm.base.sha256(OUT/'plan.json'),'script_sha256':rm.base.sha256(__file__),
        'source_cutoff':'2026-09-21','selected_disclosures_strictly_before_fit_date':True,
        'all_test_scoring_inputs_A':True,'human_or_historical_XBRL_certification':False,
        'output_hashes':{str(p.relative_to(REV)):rm.base.sha256(p) for p in list(OUT.rglob('*'))+list(DATA.glob('fit_date_*.parquet')) if p.is_file() and p!=OUT/'manifest.json'}}
    assert manifest['cohort_sha256']==rm.EXPECTED_HASH
    rm.base.write_json(OUT/'manifest.json',manifest)
    print(json.dumps({'status':'PASS','fit_date':summaries,'metric_cells':len(checks)}),flush=True)

if __name__=='__main__':
    if '--finalize-only' in sys.argv:finalize()
    else:run()
