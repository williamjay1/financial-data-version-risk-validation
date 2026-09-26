"""Locked, reproducible source-audit sampling; no training or dataset modification."""
from pathlib import Path
import hashlib, importlib.util, json
import numpy as np
import pandas as pd

REV=Path(__file__).resolve().parents[1]
ROOT=REV.parent
OUT=REV/'results'/'source_audit'
OUT.mkdir(parents=True,exist_ok=True)
SEED=20260922
cohort_path=ROOT/'datasets'/'model_cohort.parquet'
facts_path=ROOT/'datasets'/'vintage_facts.parquet'
p=pd.read_parquet(cohort_path)
f=pd.read_parquet(facts_path)
p['block']=pd.to_datetime(p.decision_date).dt.year.map(lambda y: '2016_2017' if 2016<=y<=2017 else ('2018_2019' if 2018<=y<=2019 else ('2020_2021' if 2020<=y<=2021 else 'outside_test')))
p['changed']=p.n_coherent_changed.gt(0).astype(int)
p['stratum']=p.block+'|event='+p.registry_event_365.astype(int).astype(str)+'|changed='+p.changed.astype(str)
eligible=p[p.block.ne('outside_test')].sort_values(['stratum','cik','accession']).copy()
rng=np.random.default_rng(SEED)
parts=[];strata=[]
for h,g in eligible.groupby('stratum',sort=True):
    n=min(2,len(g)); idx=np.sort(rng.choice(len(g),size=n,replace=False)); s=g.iloc[idx].copy()
    s['audit_role']='probability';s['audit_N_h']=len(g);s['audit_n_h']=n;s['audit_pi']=n/len(g);s['audit_weight']=len(g)/n
    parts.append(s);strata.append({'stratum':h,'N_h':len(g),'n_h':n,'audit_pi':n/len(g),'audit_weight':len(g)/n,'original_weighted_N_h':float(g.sample_weight.sum())})
prob=pd.concat(parts,ignore_index=True)
fact_groups={(a,b):g for (a,b),g in f.groupby(['cik','original_accession'],sort=False)}
def discrepancy(row):
    g=fact_groups[(row.cik,row.accession)]
    a=g.A.to_numpy(float);b=g.B.to_numpy(float)
    return float(np.nanmax(np.abs(b-a)/np.maximum(1,np.maximum(np.abs(a),np.abs(b)))))
p['extreme_score']=[discrepancy(r) for r in p.itertuples()]
used=set(zip(prob.cik,prob.accession));used_ciks=set()
ext=[]
for acc in ['0001062993-16-008351','0001445305-14-000765']:
    for _,r in p[p.accession.eq(acc)].iterrows():
        if (r.cik,r.accession) not in used:
            ext.append(r);used.add((r.cik,r.accession));used_ciks.add(r.cik)
for _,r in p.sort_values(['extreme_score','cik','accession'],ascending=[False,True,True]).iterrows():
    if len(ext)>=6:break
    if r.extreme_score>0 and (r.cik,r.accession) not in used and r.cik not in used_ciks:
        ext.append(r);used.add((r.cik,r.accession));used_ciks.add(r.cik)
ext=pd.DataFrame(ext);ext['audit_role']='purposive_extreme'
for c in ['audit_N_h','audit_n_h','audit_pi','audit_weight']:ext[c]=np.nan
sample=pd.concat([prob,ext],ignore_index=True)
sample['audit_id']=[f'P{i+1:02}' for i in range(len(prob))]+[f'E{i+1:02}' for i in range(len(ext))]

spec=importlib.util.spec_from_file_location('vintage_builder',ROOT/'scripts'/'build_vintage_panel.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
sources=mod.sources()
def read_cache(url):
    rec=sources[url];path=ROOT/'cache'/'sec'/(rec['sha256']+'.json')
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==rec['sha256']
    return json.loads(raw)
company={};filings={}
for cik in sorted(sample.cik.unique()):
    sub=read_cache(f'https://data.sec.gov/submissions/CIK{cik}.json');company[cik]=sub.get('name','')
    frames=[pd.DataFrame(sub['filings']['recent'])]
    for older in sub['filings'].get('files',[]):
        u='https://data.sec.gov/submissions/'+older['name']
        if u in sources:frames.append(pd.DataFrame(read_cache(u)))
    filings[cik]={r['accessionNumber']:r for r in pd.concat(frames,ignore_index=True).drop_duplicates('accessionNumber').to_dict('records')}
records=[];requests=[]
for r in sample.itertuples():
    g=fact_groups[(r.cik,r.accession)].copy();g['delta']=np.abs(g.B-g.A)/np.maximum(1,np.maximum(np.abs(g.A),np.abs(g.B)))
    nonasset=g[g.feature.ne('assets')]
    changed=nonasset[nonasset.delta.gt(1e-12)].sort_values(['delta','feature'],ascending=[False,True])
    if len(changed):secondary=changed.iloc[0].feature
    elif nonasset.feature.eq('revenue').any():secondary='revenue'
    elif nonasset.feature.eq('liabilities').any():secondary='liabilities'
    elif len(nonasset):secondary=sorted(nonasset.feature)[0]
    else:secondary=None
    for z in g[g.feature.isin(['assets',secondary])].itertuples():
        rec={k:getattr(r,k) for k in ['audit_id','audit_role','stratum','audit_N_h','audit_n_h','audit_pi','audit_weight','sample_weight','cik','accession','fiscal_end','block','registry_event_365','changed']}
        rec.update(company_name=company[r.cik],feature=z.feature,tag=z.tag,start=z.start,end=z.end,unit=z.unit,api_A=z.A,api_B=z.B,B_accession=z.B_accession)
        for arm,acc in [('A',r.accession),('B',z.B_accession)]:
            fr=filings[r.cik].get(acc,{})
            url=f"https://www.sec.gov/Archives/edgar/data/{int(r.cik)}/{acc.replace('-','')}/{fr.get('primaryDocument','')}" if fr.get('primaryDocument') else ''
            rec[arm+'_filed']=fr.get('filingDate','');rec[arm+'_url']=url
            requests.append({'audit_id':r.audit_id,'arm':arm,'cik':r.cik,'company_name':company[r.cik],'accession':acc,'url':url,'filing_date':fr.get('filingDate',''),'primary_document':fr.get('primaryDocument','')})
        records.append(rec)
sample.drop(columns=[c for c in sample if c.startswith(('A_','B_','C_'))]).to_csv(OUT/'sample_landmarks.csv',index=False)
pd.DataFrame(strata).to_csv(OUT/'sampling_strata.csv',index=False)
pd.DataFrame(records).to_csv(OUT/'fact_requests.csv',index=False)
req=pd.DataFrame(requests).drop_duplicates(['audit_id','arm','accession']);req.to_csv(OUT/'document_requests.csv',index=False)
manifest={'seed':SEED,'cohort_sha256':hashlib.sha256(cohort_path.read_bytes()).hexdigest(),'facts_sha256':hashlib.sha256(facts_path.read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256((OUT/'protocol.md').read_bytes()).hexdigest(),'test_landmarks':len(eligible),'probability_landmarks':len(prob),'purposive_landmarks':len(ext),'fact_requests':len(records),'unique_source_urls':req.url.nunique(),'sample_rows':sample.audit_id.tolist()}
(OUT/'sample_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
print(pd.DataFrame(records)[['audit_id','company_name','feature','api_A','api_B','A_url','B_url']].to_string(index=False))
