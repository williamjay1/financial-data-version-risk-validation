"""Freeze the final cohort only after source completion and independent identities.

This audit checks mechanics and provenance, not universal bankruptcy coverage.
The registry-only outcome and reconstructed-vintage restrictions remain binding.
"""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
import expanded_sec_fetch as fetcher

ROOT=Path(__file__).resolve().parents[1]
DATA,OUT=ROOT/'datasets',ROOT/'results'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
    return h.hexdigest()

def main():
    # A failed rerun or an exception must never inherit an earlier permission.
    protocol_path=ROOT/'phase2_protocol.json'
    protocol=json.loads(protocol_path.read_text(encoding='utf-8'))
    protocol['data_gate'].update(training_allowed_now=False,reason='Final data gate being revalidated; permission revoked until all checks pass.')
    protocol_path.write_text(json.dumps(protocol,indent=2,ensure_ascii=False),encoding='utf-8')
    issues=[];checks={}
    def check(name,ok,detail=None):
        checks[name]={'pass':bool(ok),'detail':detail}
        if not ok:issues.append(name)
    frame=pd.read_parquet(DATA/'sampling_frame.parquet')
    selected=frame.loc[frame.selected]
    records={r['url']:r for r in fetcher.records()}
    wanted=[];hist=[]
    for cik in selected.cik:
        su=f'https://data.sec.gov/submissions/CIK{cik}.json'
        fu=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
        wanted += [su,fu]
        row=records.get(su,{})
        if row.get('status')==200:
            p=ROOT/'cache/sec'/f"{row['sha256']}.json"
            doc=json.loads(p.read_text(encoding='utf-8')) if p.exists() else json.loads(Path(row['raw_path']).read_text(encoding='utf-8'))
            hist += ['https://data.sec.gov/submissions/'+h['name'] for h in doc['filings'].get('files',[]) if h['filingTo']>='2008-01-01' and h['filingFrom']<='2026-09-21']
    unresolved=[u for u in wanted if records.get(u,{}).get('status') not in [200,404]]
    bad_history=[u for u in hist if records.get(u,{}).get('status')!=200]
    check('all_selected_primary_urls_terminal',not unresolved,{'required':len(wanted),'unresolved':unresolved})
    check('all_referenced_histories_available',not bad_history,{'required':len(set(hist)),'unresolved':bad_history})
    cachebad=[];verified=0
    for u in set(wanted+hist):
        r=records.get(u,{})
        if r.get('status')!=200:continue
        p=ROOT/'cache/sec'/f"{r['sha256']}.json"
        if not p.exists() or sha(p)!=r['sha256']:cachebad.append(u)
        else:verified+=1
    check('working_cache_hashes_match_original_manifest',not cachebad,{'verified':verified,'bad':cachebad})
    panel=pd.read_parquet(DATA/'vintage_panel.parquet')
    facts=pd.read_parquet(DATA/'vintage_facts.parquet')
    cohort=pd.read_parquet(DATA/'model_cohort.parquet')
    check('fact_key_unique',not facts.duplicated(['cik','original_accession','feature']).any())
    counts=facts.groupby(['cik','original_accession']).agg(b_sources=('B_accession','nunique'),c_sources=('C_accession','nunique'))
    counts.index.names=['cik','accession']
    comparison=panel.set_index(['cik','accession']).join(counts,validate='one_to_one')
    check('B_is_single_accession',comparison.b_sources.dropna().eq(1).all())
    check('C_source_count_includes_retained_original',comparison.per_tag_accessions.eq(comparison.c_sources.fillna(0)).all())
    # Independently reconstruct all ratio columns from the fact table, not the
    # producer's ratios() function. Missing features remain explicit NaNs.
    errors=[]
    denoms=['liabilities','equity','cash','net_income','revenue','operating_income','operating_cash','retained_earnings']
    keys=['cik','original_accession']
    px=panel.set_index(['cik','accession'])
    for version in ['A','B','C']:
        raw=facts.pivot(index=keys,columns='feature',values=version).reindex(px.index)
        assets=raw['assets'].where(raw['assets'].gt(0))
        derived={'log_assets':np.log(assets)}
        derived.update({f+'_to_assets':raw[f]/assets for f in denoms})
        derived['working_capital_to_assets']=(raw.current_assets-raw.current_liabilities)/assets
        for f,v in derived.items():
            x=px[version+'_'+f].to_numpy();z=v.to_numpy()
            if not np.allclose(x,z,rtol=1e-13,atol=1e-13,equal_nan=True):errors.append(version+'_'+f)
    check('all_30_feature_columns_reconstructed',not errors,errors)
    brd=pd.read_parquet(DATA/'brd_all_events.parquet')
    first=brd.loc[brd.cik.ne('')].groupby('cik').event_date.min()
    date=pd.to_datetime(cohort.decision_date);ev=cohort.cik.map(first)
    lab=(date.lt(ev)&ev.le(date+pd.Timedelta(days=365))).astype(int)
    check('independent_direct_registry_labels',np.array_equal(lab,cohort.registry_event_365))
    check('all_before_first_recorded_event',(ev.isna()|date.lt(ev)).all())
    check('original_assets_domain',np.isfinite(cohort.A_log_assets).all())
    check('same_missingness_A_B',np.array_equal(cohort.filter(regex='^A_').isna(),cohort.filter(regex='^B_').isna()))
    check('same_weight_as_locked_frame',np.allclose(cohort.sample_weight,cohort.cik.map(frame.set_index('cik').sample_weight)))
    histframe=pd.read_parquet(DATA/'universe_annual_filings_2010_2021.parquet')
    hk=set(zip(histframe.cik,histframe.accession_number,histframe.filing_date))
    expected=panel.merge(selected[['cik']],on='cik',how='inner')
    permitted=[(c,a,d) in hk for c,a,d in zip(expected.cik,expected.accession,expected.filing_date)]
    expected=expected.loc[np.array(permitted)&expected.decision_date.between('2010-01-01','2021-12-31')&expected.pre_first_registry_event&np.isfinite(expected.A_log_assets)&expected.report_lag_days.ge(0)]
    check('cohort_matches_locked_rules',set(zip(expected.cik,expected.accession))==set(zip(cohort.cik,cohort.accession)))
    common=[c for c in panel.columns if c not in ['cik','accession']]
    left=cohort.set_index(['cik','accession']).sort_index()
    right=expected.set_index(['cik','accession']).sort_index()
    changed=[]
    if left.index.equals(right.index):
        for column in common:
            try:pd.testing.assert_series_equal(left[column],right[column],check_names=False,check_dtype=False,check_exact=True)
            except AssertionError:changed.append(column)
    else:changed=['row_keys']
    check('cohort_values_equal_filtered_panel',not changed,changed)
    fm=frame.set_index('cik')
    sample_errors=[]
    for field in ['cluster_id','sampling_stratum','inclusion_probability','sample_weight']:
        try:pd.testing.assert_series_equal(cohort[field],cohort.cik.map(fm[field]),check_names=False,check_dtype=False,check_exact=True)
        except AssertionError:sample_errors.append(field)
    check('all_sampling_metadata_equal_locked_frame',not sample_errors,sample_errors)
    check('no_duplicate_fiscal_landmarks',not cohort.duplicated(['cik','fiscal_end']).any())
    check('full_365_day_followup',(date+pd.Timedelta(days=365)).le('2022-12-31').all())
    report={'status':'PASS' if not issues else 'FAIL','audit_utc':datetime.now(timezone.utc).isoformat(),
            'checks':checks,'issues':issues,'cohort_rows':len(cohort),'cohort_sha256':sha(DATA/'model_cohort.parquet'),
            'fact_table_sha256':sha(DATA/'vintage_facts.parquet'),'sampling_frame_sha256':sha(DATA/'sampling_frame.parquet'),
            'script_sha256':sha(__file__),'limitations':'Mechanical data gate only; accessible current-API domain, direct registry target, cofiling clusters not complete legal groups, source semantics partly audited.'}
    (OUT/'final_data_gate.json').write_text(json.dumps(report,indent=2,default=int),encoding='utf-8')
    if issues:
        print(json.dumps(report,default=int));raise SystemExit(1)
    summary=json.loads((OUT/'cohort_summary.json').read_text(encoding='utf-8'))
    summary.update(status='FINAL_COHORT_FROZEN',source_collection_complete=True,fact_table_sha256=report['fact_table_sha256'],final_gate_sha256=sha(OUT/'final_data_gate.json'))
    (OUT/'cohort_summary.json').write_text(json.dumps(summary,indent=2,default=int),encoding='utf-8')
    protocol=json.loads((ROOT/'phase2_protocol.json').read_text(encoding='utf-8'))
    protocol['status']='DATA_GATE_PASSED_FOR_RESTRICTED_REGISTRY_TARGET'
    protocol['data_gate'].update(training_allowed_now=True,reason='All sampled sources have explicit terminal status, needed histories and cached hashes verified, paired features/labels/domain checked; limitations constrain claims.',audit='results/final_data_gate.json',cohort_sha256=report['cohort_sha256'])
    (ROOT/'phase2_protocol.json').write_text(json.dumps(protocol,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':report['status'],'checks':len(checks),'cohort_rows':len(cohort),'training_allowed_now':True}))

if __name__=='__main__':main()
