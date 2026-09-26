"""Reconstruct finite availability caps from frozen D: SEC caches; no network."""
from pathlib import Path
from datetime import datetime, timezone
import sys
import json
import hashlib
import shutil
import numpy as np
import pandas as pd

REV = Path(__file__).resolve().parents[1]
ROOT = REV.parent
sys.path.insert(0, str(ROOT/'scripts'))
import build_vintage_panel as vp
import run_vintage_models as vm

CAPS = [90,365,730]

def cache(source):
    p=ROOT/'cache/sec'/(source['sha256']+'.json')
    if not p.exists() or vm.sha256(p)!=source['sha256']:
        raise ValueError('Frozen D: cache missing or mismatched: '+str(p))
    return json.loads(p.read_text(encoding='utf-8'))

def build():
    assert REV.drive.lower()=='d:'
    assert shutil.disk_usage(REV).free>2*1024**3
    out=REV/'results/version_caps'; out.mkdir(parents=True,exist_ok=True)
    data=REV/'datasets';data.mkdir(exist_ok=True)
    source=ROOT/'datasets/model_cohort.parquet'
    assert vm.sha256(source)=='724122d3ca7a0a123de244112aa604d6da7a008497cc6ce526f8f07327916e21'
    df=pd.read_parquet(source)
    sources=vp.sources()
    outputs={cap:df.copy() for cap in CAPS}
    trace=[];comparisons=[];facttrace=[];warnings=[]
    checked=0
    for i,(cik,rows) in enumerate(df.groupby('cik'),1):
        sub=cache(sources[f'https://data.sec.gov/submissions/CIK{cik}.json'])
        frames=[pd.DataFrame(sub['filings']['recent'])]
        for older in sub['filings'].get('files',[]):
            url='https://data.sec.gov/submissions/'+older['name']
            if url in sources:frames.append(pd.DataFrame(cache(sources[url])))
        filings=pd.concat(frames,ignore_index=True).drop_duplicates('accessionNumber')
        filingmap={r['accessionNumber']:r for r in filings.to_dict('records')}
        lookup=vp.fact_lookup(cache(sources[f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json']))
        for idx,row in rows.iterrows():
            original=filingmap[row.accession]
            a,ctx,amb=vp.snapshot(original,lookup)
            b,acc,c,ca=vp.later_bundle(a,ctx,original,lookup,filingmap)
            for name,raw in [('A',a),('B',b)]:
                got=np.array([vp.ratios(raw)[f] for f in vm.FEATURES])
                expected=row[[name+'_'+f for f in vm.FEATURES]].to_numpy(float)
                assert np.allclose(got,expected,rtol=1e-12,atol=1e-12,equal_nan=True),(cik,row.accession,name)
                comparisons.append({'cik':cik,'accession':row.accession,'version':name,'match':True})
            assert acc==row.later_accession
            decision=pd.Timestamp(row.decision_date)
            eligible=None;byfeature={}
            for feature,context in ctx.items():
                valid={}
                for candidate,records in lookup[context['tag']].items():
                    filing=filingmap.get(candidate)
                    if not filing or not original['filingDate']<filing['filingDate']<=vp.CUTOFF:continue
                    matched=[r for r in records if r.get('start','')==context['start'] and r.get('end')==context['end']]
                    values={r['val'] for r in matched}
                    if len(values)==1:
                        valid[candidate]=float(next(iter(values)))
                        mismatch=[r.get('filed') for r in matched if r.get('filed')!=filing['filingDate']]
                        if mismatch:warnings.append({'cik':cik,'original_accession':row.accession,'candidate':candidate,'feature':feature,'record_dates':mismatch,'submission_date':filing['filingDate']})
                byfeature[feature]=valid
                eligible=set(valid) if eligible is None else eligible.intersection(valid)
            options=sorted(eligible or [],key=lambda k:(filingmap[k]['filingDate'],k))
            for cap in CAPS:
                deadline=min(decision+pd.Timedelta(days=cap),pd.Timestamp(vp.CUTOFF))
                optionscap=[k for k in options if pd.Timestamp(filingmap[k]['filingDate'])<=deadline]
                chosen=optionscap[-1] if optionscap else ''
                raw=a.copy()
                if chosen:raw.update({f:valid[chosen] for f,valid in byfeature.items()})
                features=vp.ratios(raw)
                av=np.array([vp.ratios(a)[f] for f in vm.FEATURES])
                bv=np.array([features[f] for f in vm.FEATURES])
                assert np.isfinite(features['log_assets']),('Nonpositive capped assets',cik,row.accession,cap)
                assert np.array_equal(np.isnan(av),np.isnan(bv)),('Mask mismatch',cik,row.accession,cap)
                changed=int(sum(a[f]!=raw[f] for f in ctx))
                filed=filingmap[chosen]['filingDate'] if chosen else ''
                for feature,value in features.items():outputs[cap].at[idx,'B_'+feature]=value
                outputs[cap].at[idx,'later_accession']=chosen
                outputs[cap].at[idx,'later_filed']=filed
                outputs[cap].at[idx,'n_coherent_changed']=changed
                outputs[cap].at[idx,'revision_availability_cap_days']=cap
                tr={'cik':cik,'accession':row.accession,'cap_days':cap,'decision_date':row.decision_date,
                    'registry_event_365':row.registry_event_365,'first_registry_event':row.first_registry_event,
                    'sample_weight':row.sample_weight,'selected_accession':chosen or row.accession,
                    'later_bundle_available':bool(chosen),'later_filed':filed,'deadline':str(deadline.date()),
                    'source_lag_days':(pd.Timestamp(filed)-decision).days if chosen else 0,
                    'raw_changed_components':changed,'model_input_changed':bool(np.any(~np.isclose(av,bv,equal_nan=True,rtol=0,atol=0)))}
                trace.append(tr)
                for feature,context in ctx.items():
                    facttrace.append({'cik':cik,'accession':row.accession,'cap_days':cap,'feature':feature,
                                      'tag':context['tag'],'unit':'USD','start':context['start'],'end':context['end'],
                                      'A':a[feature],'capped':raw[feature],'selected_accession':chosen or row.accession})
            checked+=1
        if i%100==0:print(json.dumps({'companies':i,'landmarks_reconstructed':checked}),flush=True)
    assert checked==len(df)
    paths={}
    for cap,frame in outputs.items():
        p=data/f'cap_{cap}.parquet';frame.to_parquet(p,index=False)
        validated=vm.validate_cohort(frame)
        assert len(validated)==len(df)
        paths[str(cap)]={'path':str(p),'sha256':vm.sha256(p),'n':len(frame)}
    trace=pd.DataFrame(trace);trace.to_parquet(out/'cap_lineage.parquet',index=False)
    pd.DataFrame(facttrace).to_parquet(out/'cap_fact_lineage.parquet',index=False)
    pd.DataFrame(comparisons).to_csv(out/'original_reconstruction_checks.csv',index=False)
    vm.write_json(out/'record_filing_date_warnings.json',warnings)
    summary=[]
    for cap,rows in trace.groupby('cap_days'):
        w=rows.sample_weight.to_numpy()
        summary.append({'cap_days':int(cap),'n':len(rows),'available_n':int(rows.later_bundle_available.sum()),
            'available_weighted_percent':100*np.average(rows.later_bundle_available,weights=w),
            'raw_changed_n':int(rows.raw_changed_components.gt(0).sum()),
            'raw_changed_weighted_percent':100*np.average(rows.raw_changed_components.gt(0),weights=w),
            'input_changed_weighted_percent':100*np.average(rows.model_input_changed,weights=w)})
    pd.DataFrame(summary).to_csv(out/'cap_coverage.csv',index=False)
    # Source timing describes all latest-B windows, not just a selected time cap.
    t=df[['cik','accession','decision_date','first_registry_event','registry_event_365','sample_weight','later_accession','later_filed','n_coherent_changed']].copy()
    date=pd.to_datetime(t.later_filed,errors='coerce')
    dec=pd.to_datetime(t.decision_date)
    event=pd.to_datetime(t.first_registry_event,errors='coerce')
    end=dec+pd.Timedelta(days=365)
    t['source_lag_days']=(date-dec).dt.days
    t['timing_category']='no_later_bundle'
    positive=t.registry_event_365.eq(1);present=date.notna()
    t.loc[present&positive&date.lt(event),'timing_category']='positive_before_event'
    t.loc[present&positive&date.eq(event),'timing_category']='positive_on_event_day'
    t.loc[present&positive&date.gt(event),'timing_category']='positive_after_event'
    t.loc[present&~positive&date.le(end),'timing_category']='negative_within_365_day_window'
    t.loc[present&~positive&date.gt(end),'timing_category']='negative_after_365_day_window'
    t.to_parquet(out/'latest_source_timing.parquet',index=False)
    timing=t.groupby(['registry_event_365','timing_category']).agg(n=('cik','size'),weighted_n=('sample_weight','sum'),raw_changed_n=('n_coherent_changed',lambda x:int(x.gt(0).sum()))).reset_index()
    timing.to_csv(out/'latest_source_timing_summary.csv',index=False)
    manifest={'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'analysis_status':'revision_stage_after_original_results',
        'source_cohort':str(source),'source_cohort_sha256':vm.sha256(source),'script_sha256':vm.sha256(Path(__file__)),
        'protocol_sha256':vm.sha256(REV/'REVISION_PROTOCOL.md'),'source_reconstruction_matches':len(comparisons),
        'landmarks':len(df),'outputs':paths,'record_filing_date_mismatches':len(warnings),
        'cutoff':vp.CUTOFF,'rule':'last single common accession filed after original filing and no later than origin+cap; original A fallback; preserve original concepts, units, periods and masks',
        'interpretation':'Retrospective availability diagnostics, not prospective prediction.'}
    vm.write_json(out/'manifest.json',manifest)
    print(json.dumps(vm.clean_json(manifest)),flush=True)

if __name__=='__main__':build()
