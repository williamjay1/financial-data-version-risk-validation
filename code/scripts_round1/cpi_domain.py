"""Post hoc CPI-compatible origin-size domain; not full registry eligibility."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import importlib.util, json, os, stat
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('revision_models_readonly',HERE/'revision_models.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
REV=mod.REVISION; OUT=REV/'results/cpi_domain'; DATA=REV/'datasets'
RAW=Path('<archived-record-root>/...')
SERIES='CUUR0000SA0'; BATCHES=[(1980,1980),(2009,2018),(2019,2021)]

def run():
    OUT.mkdir(parents=True,exist_ok=True); DATA.mkdir(exist_ok=True); RAW.mkdir(parents=True,exist_ok=True)
    mod.base.require(not (OUT/'design.json').exists(),'CPI design exists; do not refetch/rerun silently')
    df,binding=mod.load_base()
    design={'recorded_utc':datetime.now(timezone.utc).isoformat(),'analysis_status':'post_hoc_revision',
            'frozen_input_sha256':mod.EXPECTED_HASH,'series':SERIES,'definition':'U.S. city average CPI-U all items, not seasonally adjusted',
            'official_api_documentation':'https://www.bls.gov/developers/api_signature_v2.htm',
            'threshold':'100000000 USD * CPI(month containing decision_date minus two calendar months) / annual mean CPI in 1980',
            'annual_reference_rule':'Use BLS M13 annual average if returned; otherwise arithmetic mean of all 12 published 1980 monthly levels, with the computation disclosed',
            'domain':'Original A assets at the prediction origin only; identical development and test restriction for A/B',
            'models':'Declared fixed LR C1 and LGBM leaves7/minchild30; all four fit-score cells; mature training only',
            'availability_boundary':'Two-month calendar lag is a conservative release-calendar proxy; current NSA historical observations are not authenticated original CPI vintages',
            'claim_boundary':'Registry-compatible size proxy, not reconstruction of complete BRD eligibility, event-time assets, public-company criteria or group identity',
            'raw_policy':'Unique original JSON response names on E, made read-only; parsed cache and all analysis on D',
            'network_policy':'One request per range; stop and record failure instead of repeated probing',
            'script_sha256':mod.base.sha256(__file__),'threads':2}
    mod.base.write_json(OUT/'design.json',design)
    sources=[]; records=[]
    try:
        for start,end in BATCHES:
            url=f'https://api.bls.gov/publicAPI/v2/timeseries/data/{SERIES}?startyear={start}&endyear={end}&annualaverage=true'
            response=requests.get(url,timeout=35,headers={'User-Agent':'Academic data reconstruction; public BLS API'})
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            path=RAW/f'{stamp}_{SERIES}_{start}_{end}.json'
            with path.open('xb') as handle: handle.write(response.content)
            os.chmod(path,stat.S_IREAD)
            source={'url':url,'http_status':response.status_code,'raw_path':str(path),'sha256':mod.base.sha256(path),'bytes':path.stat().st_size}
            sources.append(source); mod.base.write_json(OUT/'raw_manifest.json',sources)
            response.raise_for_status(); payload=response.json()
            mod.base.require(payload.get('status')=='REQUEST_SUCCEEDED',f'BLS API failure: {payload.get("message")}')
            series=payload['Results']['series']; mod.base.require(len(series)==1 and series[0]['seriesID']==SERIES,'Unexpected BLS series')
            source['api_messages']=payload.get('message',[])
            for row in series[0]['data']:
                records.append({'year':int(row['year']),'period':row['period'],'period_name':row.get('periodName'),
                                'value':float(row['value']),'footnotes':json.dumps(row.get('footnotes',[])),
                                'raw_sha256':source['sha256']})
            print(f'Downloaded {start}-{end}: {len(series[0]["data"])} values',flush=True)
    except Exception as exc:
        mod.base.write_json(OUT/'manifest.json',{'status':'not_run_network_or_source_failure','error':repr(exc),'sources':sources,
                          'design_sha256':mod.base.sha256(OUT/'design.json')})
        print('STOP CPI: '+repr(exc),flush=True); return
    mod.base.write_json(OUT/'raw_manifest.json',sources)
    cpi=pd.DataFrame(records); mod.base.require(not cpi.duplicated(['year','period']).any(),'Duplicate CPI period')
    monthly=cpi[cpi.period.str.match(r'M(?:0[1-9]|1[012])$')].copy()
    ref=monthly[monthly.year.eq(1980)]
    mod.base.require(len(ref)==12 and set(ref.period)=={f'M{x:02}' for x in range(1,13)},'Missing 1980 reference months')
    annual=cpi[cpi.year.eq(1980)&cpi.period.eq('M13')]
    base_value=float(annual.value.iloc[0]) if len(annual)==1 else float(ref.value.mean())
    base_method='BLS M13 annual average' if len(annual)==1 else 'arithmetic mean of 12 published monthly levels; unrounded'
    monthly['month']=pd.PeriodIndex([f'{y}-{int(p[1:]):02}' for y,p in zip(monthly.year,monthly.period)],freq='M').astype(str)
    lookup=monthly.set_index('month').value.to_dict()
    lagmonths=(df.decision_date.dt.to_period('M')-2).astype(str)
    values=lagmonths.map(lookup)
    mod.base.require(values.notna().all(),'CPI coverage does not include all two-month lagged origins')
    threshold=1e8*values.to_numpy()/base_value
    mask=df.A_log_assets.to_numpy()>=np.log(threshold)
    # Do not use first_registry_event, outcome or B assets to decide membership.
    cache=df[['row_id','cik','accession','decision_date','A_log_assets']].copy()
    cache['cpi_month']=lagmonths; cache['cpi_level']=values; cache['1980_reference_level']=base_value
    cache['nominal_threshold_usd']=threshold; cache['included']=mask
    cache.to_parquet(DATA/'cpi_origin_domain.parquet',index=False); cpi.to_csv(DATA/'cpi_bls_levels.csv',index=False)
    included=df.loc[mask].copy(); included.to_parquet(DATA/'cpi_domain_cohort.parquet',index=False)
    splits=[]
    for split in mod.base.make_splits(df):
        for stage,ids in split['indices'].items():
            use=ids[mask[ids]]
            splits.append({'block':split['block'],'stage':stage,**mod.base.subset_summary(df.loc[use])})
    pd.DataFrame([{k:v for k,v in x.items() if not isinstance(v,(dict,list))} for x in splits]).to_csv(OUT/'domain_counts.csv',index=False)
    audit={'status':'PASS','cpi_1980_reference':base_value,'cpi_reference_method':base_method,'n_monthly_records':len(monthly),
           'input_rows':len(df),'included_rows':int(mask.sum()),'included_positive_windows':int(df.loc[mask,'registry_event_365'].sum()),
           'min_nominal_threshold':float(threshold.min()),'max_nominal_threshold':float(threshold.max()),
           'all_origin_cpi_months_strictly_before_origin':bool((pd.PeriodIndex(lagmonths,freq='M').end_time<df.decision_date).all()),
           'same_A_B_domain':True,'labels_weights_unchanged':True,'domain_cache_sha256':mod.base.sha256(DATA/'cpi_origin_domain.parquet'),
           'domain_cohort_sha256':mod.base.sha256(DATA/'cpi_domain_cohort.parquet'),'splits':splits}
    mod.base.require(audit['all_origin_cpi_months_strictly_before_origin'],'CPI origin timing violation')
    mod.base.write_json(OUT/'data_audit.json',audit)
    mod.run_fixed_cohort(df,OUT,'cpi1980_size_fixed',development_filter=mask,test_filter=mask)
    mod.base.require(mod.base.sha256(mod.ROOT/'datasets/model_cohort.parquet')==mod.EXPECTED_HASH,'Frozen cohort changed')
    outputs={str(p.relative_to(OUT)):{'sha256':mod.base.sha256(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file()}
    mod.base.write_json(OUT/'manifest.json',{'status':'complete','design_sha256':mod.base.sha256(OUT/'design.json'),
                      'input_binding':binding,'source_raw':sources,'audit':audit,'outputs':outputs})
    print(json.dumps({'complete':True,'included':int(mask.sum()),'1980_CPI':base_value,'method':base_method}),flush=True)

if __name__=='__main__': run()
