"""Read-only source/feature/stage tracing. No fit, no changes to prior rounds."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, time
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import requests

ROUND=Path(__file__).resolve().parents[1]
ROOT=ROUND.parent
PREV=ROOT/'revision_20260922'
OUT=ROUND/'results/source_semantics'
RAW=Path('<archived-record-root>/...')
OUT.mkdir(parents=True,exist_ok=True)
RAW.mkdir(parents=True,exist_ok=True)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def cache_sources():
    spec=importlib.util.spec_from_file_location('vintage',ROOT/'scripts/build_vintage_panel.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    sources=m.sources()
    def read(url):
        rec=sources[url];p=ROOT/'cache/sec'/(rec['sha256']+'.json')
        assert sha(p)==rec['sha256']
        return json.loads(p.read_text(encoding='utf-8'))
    return sources,read

def build():
    p=pd.read_parquet(ROOT/'datasets/model_cohort.parquet')
    p['row_id']=p.cik+'|'+p.accession
    f=pd.read_parquet(ROOT/'datasets/vintage_facts.parquet')
    changed=pd.read_csv(PREV/'results/corrected_models_v2/changed_features.csv',dtype={'cik':str})
    changed=changed[changed.arm.isin(['A','B'])].copy()
    changed['row_id']=changed.cik+'|'+changed.accession
    membership=pd.read_parquet(ROOT/'results/models_20260921T093517075175Z_split_membership.parquet')
    stage={rid:[] for rid in p.row_id}
    for s in membership.itertuples():stage[s.row_id].append(s.block+':'+s.role)
    changed=changed.merge(p[['row_id','decision_date','fiscal_end','registry_event_365','cluster_id']],on='row_id',how='left')
    changed['original_stages']=changed.row_id.map(lambda x:';'.join(stage[x]))
    changed['evidence_class']=np.where(changed.cik.eq('0001409916'),'scale_supported_display_only','sign_unresolved')
    changed['author_confirmation']='NOT_COMPLETED'
    changed.to_csv(OUT/'six_feature_cells_stage_trace.csv',index=False)
    applied=pd.read_csv(PREV/'results/corrected_models_v2/applied_fact_changes.csv',dtype={'cik':str},keep_default_na=False)
    applied=applied[applied.arm.isin(['A','B'])].copy()
    applied['row_id']=applied.cik+'|'+applied.original_accession
    applied['original_stages']=applied.row_id.map(lambda x:';'.join(stage[x]))
    applied['changed_AB_model_features']=applied.apply(lambda r:';'.join(changed.loc[changed.row_id.eq(r.row_id)&changed.arm.eq(r.arm),'feature']),axis=1)
    applied['evidence_class']=np.where(applied.cik.eq('0001409916'),'scale_supported_display_only','sign_unresolved')
    applied.to_csv(OUT/'source_keys_to_components_features_stages.csv',index=False)
    # Joint historical 26-context result: this is not each correction's causal effect.
    old=pd.read_parquet(PREV/'results/models/predictions.parquet')
    new=pd.read_parquet(PREV/'results/corrected_models_v2/predictions.parquet')
    old=old[old.experiment.isin(['original_four_cell','fixed_full'])].copy()
    old['comparison']=old.experiment.map({'original_four_cell':'tuned','fixed_full':'fixed'})
    new['comparison']=new.experiment.map({'source_corrected_tuned':'tuned','source_corrected_fixed':'fixed'})
    keys=['comparison','block','model','train_version','score_version','row_id']
    matched=old[keys+['prediction']].merge(new[keys+['prediction']],on=keys,suffixes=('_original','_26_context_proposal'),validate='one_to_one')
    matched['prediction_delta']=matched.prediction_26_context_proposal-matched.prediction_original
    matched['absolute_delta']=matched.prediction_delta.abs()
    matched[matched.row_id.isin(changed.row_id)].to_csv(OUT/'affected_rows_historical_prediction_deltas.csv',index=False)
    summary=matched.groupby(keys[:-1],as_index=False).agg(n_test=('row_id','size'),mean_prediction_delta=('prediction_delta','mean'),max_abs_delta=('absolute_delta','max'),mean_abs_delta=('absolute_delta','mean'))
    counts=matched.assign(changed=matched.absolute_delta.gt(1e-12)).groupby(keys[:-1],as_index=False).changed.sum()
    summary.merge(counts,on=keys[:-1]).to_csv(OUT/'joint_26_context_prediction_effect_summary.csv',index=False)
    # Three key transition observations, RTW event, and two accounting-scope examples.
    tr=pd.read_csv(PREV/'results/models/transition_records.csv',dtype={'cik':str})
    tr=tr[(tr.registry_event_365.eq(1)) | tr.n_changed_A_B.gt(0)].drop_duplicates('row_id')
    extra_ciks=['0001211351','0001568832','0001632970']
    extras=p[(p.cik.eq('0001211351')&p.registry_event_365.eq(1)) |
             (p.cik.eq('0001568832')&p.accession.eq('0001445305-14-000765')) |
             (p.cik.eq('0001632970')&p.fiscal_end.eq('2020-12-31'))]
    focus=pd.concat([p[p.row_id.isin(tr.row_id)],extras],ignore_index=True).drop_duplicates('row_id')
    focus['original_stages']=focus.row_id.map(lambda x:';'.join(stage[x]))
    focus.to_csv(OUT/'targeted_landmarks.csv',index=False)
    sources,read=cache_sources();requests_out=[];defs=[]
    filings={}
    for cik in set(focus.cik)|set(changed.cik):
        sub=read(f'https://data.sec.gov/submissions/CIK{cik}.json')
        frames=[pd.DataFrame(sub['filings']['recent'])]
        for rec in sub['filings'].get('files',[]):
            u='https://data.sec.gov/submissions/'+rec['name']
            if u in sources:frames.append(pd.DataFrame(read(u)))
        filings[cik]={x['accessionNumber']:x for x in pd.concat(frames).to_dict('records')}
        facts=read(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')
        for tag in ['NetCashProvidedByUsedInOperatingActivities','NetIncomeLoss','RetainedEarningsAccumulatedDeficit']:
            if tag in facts.get('facts',{}).get('us-gaap',{}):
                d=facts['facts']['us-gaap'][tag]
                defs.append({'cik':cik,'tag':tag,'label':d.get('label'),'documentation':d.get('description'),'evidence_status':'CURRENT_COMPANYFACTS_METADATA_NOT_HISTORICAL_INSTANCE_SCHEMA'})
    pd.DataFrame(defs).to_csv(OUT/'concept_documentation_api_metadata.csv',index=False)
    for r in focus.itertuples():
        g=f[(f.cik==r.cik)&(f.original_accession==r.accession)].copy()
        g['relative_change']=(g.B-g.A).abs()/np.maximum(1,np.maximum(g.A.abs(),g.B.abs()))
        g.to_csv(OUT/('targeted_facts_'+r.cik+'_'+r.accession+'.csv'),index=False)
        for arm,acc in [('A',r.accession),('B',r.later_accession or r.accession)]:
            fr=filings[r.cik].get(acc,{})
            requests_out.append({'cik':r.cik,'row_id':r.row_id,'arm':arm,'accession':acc,'filed':fr.get('filingDate',''),'form':fr.get('form',''),'url':f"https://www.sec.gov/Archives/edgar/data/{int(r.cik)}/{acc.replace('-','')}/{fr.get('primaryDocument','')}",'original_stages':r.original_stages})
    pd.DataFrame(requests_out).to_csv(OUT/'targeted_document_requests.csv',index=False)
    summary={'feature_cells_AB':len(changed),'landmarks_AB':changed.row_id.nunique(),'scale_feature_cells':int(changed.evidence_class.eq('scale_supported_display_only').sum()),'sign_unresolved_feature_cells':int(changed.evidence_class.eq('sign_unresolved').sum()),'source_context_arm_rows_AB':len(applied),'targeted_landmarks':len(focus),'prediction_note':'Existing joint 26-context outputs only; cannot attribute global refit changes to an individual fact. No models run.'}
    (OUT/'trace_manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary)); print(changed[['cik','arm','feature','old','new','original_stages']].to_string(index=False));print(pd.DataFrame(requests_out).to_string(index=False))

def download():
    run=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    urls={
      'hashemi_jonsson2017':'https://arc.hhs.se/download.aspx?MediumId=3871',
      'ish_index':'https://www.sec.gov/Archives/edgar/data/278041/000027804112000012/0000278041-12-000012-index.html',
      'sec_negative_values':'https://www.sec.gov/structureddata/announcement/osd_announcement07142017-data-quality-reminder-negative-values',
      'fasb_gaap2012_schema':'https://xbrl.fasb.org/us-gaap/2012/elts/us-gaap-2012-01-31.xsd',
      'fasb_gaap2013_schema':'https://xbrl.fasb.org/us-gaap/2013/elts/us-gaap-2013-01-31.xsd',
      'xbrlus_cashflows':'https://xbrl.us/data-rule/guid-cashflows/'
    }
    rows=[]
    for name,url in urls.items():
        try:
            res=requests.get(url,headers={'User-Agent':'Academic source verification research; noncommercial'},timeout=35)
            suffix='.pdf' if res.content.startswith(b'%PDF') else '.bin'
            path=RAW/f'{name}_{run}{suffix}'
            with path.open('xb') as fh:fh.write(res.content)
            path.chmod(0o444)
            row={'url':url,'status':res.status_code,'raw_path':str(path),'sha256':sha(path),'bytes':len(res.content),'content_type':res.headers.get('Content-Type'),'readonly':True}
        except Exception as e:row={'url':url,'error':str(e)}
        rows.append(row); print(json.dumps(row),flush=True);time.sleep(1)
    (OUT/f'retrieval_attempts_{run}.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')

def finalize():
    import xml.etree.ElementTree as ET
    ns={'xsd':'http://www.w3.org/2001/XMLSchema'}
    tags=['NetCashProvidedByUsedInOperatingActivities','NetIncomeLoss','RetainedEarningsAccumulatedDeficit']
    rows=[]
    for year in [2012,2013]:
        p=next(RAW.glob(f'fasb_gaap{year}_schema_*.bin'))
        root=ET.parse(p).getroot()
        for tag in tags:
            e=root.find(f"xsd:element[@name='{tag}']",ns)
            rows.append({'taxonomy_year':year,'tag':tag,'type':e.attrib.get('type'),'balance':e.attrib.get('{http://www.xbrl.org/2003/instance}balance','ABSENT'),'period_type':e.attrib.get('{http://www.xbrl.org/2003/instance}periodType'),'url':f'https://xbrl.fasb.org/us-gaap/{year}/elts/us-gaap-{year}-01-31.xsd','raw_path':str(p),'raw_sha256':sha(p),'issuer_schemaRef_confirmed':False})
    pd.DataFrame(rows).to_csv(OUT/'canonical_taxonomy_attributes.csv',index=False)
    d=pd.read_csv(OUT/'sign_unresolved_discrepancies.csv',dtype={'cik':str},keep_default_na=False)
    interpretations={
      '0000278041':'Statement line denotes cash PROVIDED, with positive displayed 46,273 thousand; proposed positive sign is economically plausible, but presentation role and instance context remain unauthenticated.',
      '0001064728':'Positive retained earnings 3,066.4 million in 2012 comparative balance/equity supports positive economic stock; credit attribute itself does not make instance value negative.',
      '0001066923':'Positive consolidated net income in 2020 comparative includes discontinued-operation disposal gain; operating loss alone does not determine total NetIncomeLoss sign.',
      '0001076682':'Accumulated deficit (90,888) thousand supports negative economic stock, but parentheses alone do not authenticate instance sign; negated presentation label is unresolved.'}
    d['canonical_type']='xbrli:monetaryItemType'
    d['canonical_period_type']=d.tag.map({'NetCashProvidedByUsedInOperatingActivities':'duration','NetIncomeLoss':'duration','RetainedEarningsAccumulatedDeficit':'instant'})
    d['canonical_balance']=d.tag.map({'NetCashProvidedByUsedInOperatingActivities':'ABSENT','NetIncomeLoss':'credit','RetainedEarningsAccumulatedDeficit':'credit'})
    for col in ['issuer_schemaRef','original_instance_value','original_instance_context_id','original_instance_entity','original_instance_dimensions','original_instance_period','original_instance_unit','presentation_label_role','negated_label_usage']:
        d[col]='UNKNOWN_NOT_AUTHENTICATED'
    d['original_instance_url']=d.cik.map({'0001064728':'https://www.sec.gov/Archives/edgar/data/1064728/000106472814000015/btu-20131231.xml'}).fillna('UNKNOWN_INSTANCE_FILENAME')
    d['instance_retrieval_status']=np.where(d.cik.eq('0001064728'),'exact_index_link_identified_HTTP403_and_web_fetch_unavailable','index_not_retrievable_no_instance_authentication')
    d['economic_interpretation']=d.cik.map(interpretations)
    d['default_analysis_decision']='KEEP_API_VALUE; sign reversal only as disputed sensitivity'
    d['author_decision_options']='KEEP_API | DISPLAY_SUPPORTED_REPLACEMENT_ONLY | ORIGINAL_INSTANCE_CERTIFIED_REPLACEMENT | UNRESOLVED'
    for col in ['author_name','author_review_date','author_selected_decision','author_evidence_locator','author_explanation']:d[col]=''
    d.to_csv(OUT/'author_pending_sign_confirmation.csv',index=False)
    old=pd.read_parquet(PREV/'results/models/predictions.parquet');new=pd.read_parquet(ROUND/'results/scale_only/predictions.parquet')
    old=old[old.experiment.isin(['original_four_cell','fixed_full'])].copy()
    old['comparison']=old.experiment.map({'original_four_cell':'tuned','fixed_full':'fixed'})
    new['comparison']=new.experiment.map({'source_corrected_tuned':'tuned','source_corrected_fixed':'fixed'})
    keys=['comparison','block','model','train_version','score_version','row_id']
    match=old[keys+['prediction']].merge(new[keys+['prediction']],on=keys,suffixes=('_raw','_scale22'),validate='one_to_one')
    match['delta']=match.prediction_scale22-match.prediction_raw;match['absdelta']=match.delta.abs();match['changed_gt_1e12']=match.absdelta.gt(1e-12)
    sm=match.groupby(keys[:-1],as_index=False).agg(n_test=('row_id','size'),mean_prediction_delta=('delta','mean'),max_abs_delta=('absdelta','max'),mean_abs_delta=('absdelta','mean'),n_changed_above_1e12=('changed_gt_1e12','sum'))
    sm.to_csv(OUT/'scale22_prediction_effect_summary.csv',index=False)
    match[match.row_id.str.startswith('0001409916')].to_csv(OUT/'scale22_nobilis_test_prediction_trace.csv',index=False)
    print(sm.groupby(['comparison','model']).agg(max_abs_delta=('max_abs_delta','max'),changed=('n_changed_above_1e12','sum')).to_string())
    print('Author pending sign confirmations:',len(d))

def targeted_ledger():
    req=pd.read_csv(OUT/'targeted_document_requests.csv',dtype={'cik':str},keep_default_na=False)
    rows=[]
    def add(cik,feature,arm,value,locator,evidence_file,mechanism,evidence_url=None):
        r=req[(req.cik==cik)&(req.arm==arm)].iloc[0]
        f=pd.read_csv(OUT/f"targeted_facts_{cik}_{r.row_id.split('|')[1]}.csv",keep_default_na=False)
        fact=f[f.feature==feature].iloc[0]
        assert float(fact[arm])==float(value),(cik,feature,arm,fact[arm],value)
        rows.append({'cik':cik,'row_id':r.row_id,'feature':feature,'tag':fact.tag,'start':fact.start,'end':fact.end,'unit':fact.unit,'arm':arm,'source_accession':r.accession,'api_value':value,'display_normalized_value':value,'source_url':evidence_url or r.url,'locator':locator,'evidence_capture':str(evidence_file),'evidence_capture_sha256':sha(evidence_file),'original_stages':r.original_stages,'status':'display_supported_originalXBRL_not_authenticated','mechanism':mechanism,'selection':'targeted_mechanism_not_probability_sample','human_signoff':'NOT_COMPLETED'})
    rentech_b=RAW/'web_target_excerpt2_20260923_001.json'
    rentech_a=RAW/'web_target_last_values_20260923_001.json'
    for arm,vals in [('A',{'assets':360528000,'liabilities':105200000,'current_liabilities':51725000}),('B',{'assets':360528000,'liabilities':112255000,'current_liabilities':58780000,'equity':208848000})]:
        for feat,val in vals.items():add('0000868725',feat,arm,val,'A: consolidated balance sheet p.65; B: Note 3 Revisions p.88, as previously filed/as revised',rentech_a if arm=='A' else rentech_b,'documented_income_tax_payable_revision; separate_current_assets_change_not_attributed')
    for arm,vals in [('A',{'assets':22245,'liabilities':1178561,'cash':22158,'net_income':-298977}),('B',{'assets':1413856,'liabilities':3258886,'cash':188607,'net_income':-1311915})]:
        for feat,val in vals.items():add('0001310497',feat,arm,val,'A: balance sheet / income statement, year ended March 31 2013; B: 2013 comparative column, Note 1 Rio Plata accounting acquirer',next(RAW.glob(f'silverstream_{arm}_jina_*.bin')),'reverse_takeover_changes_accounting_predecessor')
    for arm in ['A','B']:
        for feat,val in {'assets':1178512000,'liabilities':1451785000,'retained_earnings':-792851000}.items():
            evidence=next(RAW.glob('gymboree_A_jina_*.bin')) if arm=='A' else RAW/'web_target_last_values_20260923_001.json'
            add('0000786110',feat,arm,val,'A: consolidated balance sheets p.38, July 30 2016; B: condensed balance sheets p.5, July 30 2016 comparative',evidence,'26_week_transition; selected_instant_values_unchanged')
    pd.DataFrame(rows).to_csv(OUT/'targeted_new_display_verification.csv',index=False)
    prior=pd.read_csv(PREV/'results/source_audit/source_fact_verification.csv',dtype={'cik':str},keep_default_na=False)
    reuse=prior[prior.audit_id.isin(['E02','P20','P22'])].copy()
    reuse['reuse_status']='prior_frozen_display_verification; mechanism passages re-read round2; not originalXBRL certification'
    reuse.to_csv(OUT/'targeted_prior_display_verification_reused.csv',index=False)
    print('New targeted display checks:',len(rows),'Prior checks retained:',len(reuse))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['build','download','finalize','targeted']);args=parser.parse_args()
    {'build':build,'download':download,'finalize':finalize,'targeted':targeted_ledger}[args.command]()
