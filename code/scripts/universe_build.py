"""Build an unlabeled historical annual-filing frame and audit local official SEC records.

The HF source is a third-party master-index mirror, not asserted complete SEC truth.
No non-BRD record is assigned a negative outcome. No fitting or training occurs.
"""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from universe_probe import BASE

ANNUAL={'10-K','10-KT'}
CSR=Path('<archived-record-root>/...')

def local_official():
    rows=[]; inputs=[]; failures=[]
    for p in sorted(CSR.glob('CIK*.json')):
        match=re.match(r'CIK(\d+)',p.name)
        if not match:continue
        cik=match.group(1).zfill(10)
        try:
            content=p.read_bytes(); payload=json.loads(content)
            data=payload.get('filings',{}).get('recent',payload)
            if not isinstance(data.get('form'),list):continue
            inputs.append({'path':str(p),'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),'cik':cik})
            for i,form in enumerate(data['form']):
                date=data['filingDate'][i]
                if form in ANNUAL and '2010-01-01'<=date<='2021-12-31':
                    rows.append({'cik':cik,'accession_number':data['accessionNumber'][i],'official_filing_date':date,'official_form_type':form,'official_report_date':data.get('reportDate',['']*len(data['form']))[i],'official_raw_path':str(p)})
        except Exception as exc:failures.append({'path':str(p),'error':str(exc)})
    pd.DataFrame(inputs).to_csv(BASE/'results/universe_local_official_input_manifest.csv',index=False)
    (BASE/'results/universe_local_official_failures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
    return pd.DataFrame(rows).drop_duplicates(['cik','accession_number','official_form_type','official_filing_date'])

def main(manifest_path):
    manifest=Path(manifest_path)
    records=json.loads(manifest.read_text(encoding='utf-8'))
    if len(records)!=20 or not all(x.get('verified_sha256') for x in records):raise ValueError('Require all 20 verified source shards')
    (BASE/'datasets').mkdir(exist_ok=True)
    kept=[]; counts=[]; shard_audit=[]
    columns=['cik','company_name','form_type','date_filed','filename','url','year','quarter','master_metadata']
    for rec in records:
        source=Path(rec['raw_path'])
        actual=hashlib.sha256(source.read_bytes()).hexdigest()
        if actual!=rec['expected_sha256']:raise ValueError(f'Raw hash changed: {source}')
        frame=pq.read_table(source,columns=columns).to_pandas()
        dates=pd.to_datetime(frame.date_filed)
        shard_audit.append({'source_path':rec['source_path'],'rows':len(frame),'date_min':str(dates.min()),'date_max':str(dates.max()),'year_date_mismatch':int((dates.dt.year!=frame.year).sum()),'quarter_date_mismatch':int((dates.dt.quarter!=frame.quarter).sum())})
        counts.append(frame.groupby(['year','quarter','form_type'],dropna=False).size().reset_index(name='rows'))
        part=frame.loc[frame.year.between(2010,2021)&frame.form_type.isin(ANNUAL)].copy()
        part['source_shard']=rec['source_path']
        part['source_master_last_data_received']=part.master_metadata.apply(lambda x:x.get('Last Data Received') if isinstance(x,dict) else None)
        part=part.drop(columns='master_metadata').rename(columns={'date_filed':'filing_date'})
        kept.append(part)
        print(f"Parsed {rec['source_path']}: {len(frame)} metadata rows; {len(part)} annual records",flush=True)
    allcounts=pd.concat(counts).groupby(['year','quarter','form_type'],as_index=False,dropna=False)['rows'].sum()
    allcounts.to_csv(BASE/'results/universe_all_form_year_quarter_counts.csv',index=False)
    nd_source=Path('<archived-record-root>/...')
    nd=pd.read_excel(nd_source).set_index('Form')
    nd_rows=[]
    mirror_counts=allcounts.groupby(['year','form_type'])['rows'].sum()
    for year in range(2010,2022):
        for form in ['10-K','10-KT','10-K/A','10-KT/A']:
            reference=int(nd.loc[form,year]) if form in nd.index and pd.notna(nd.loc[form,year]) else 0
            actual=int(mirror_counts.get((year,form),0))
            nd_rows.append({'year':year,'form_type':form,'hf_mirror_rows':actual,'sraf_20260318_rows':reference,'mirror_minus_sraf':actual-reference})
    nd_audit=pd.DataFrame(nd_rows)
    nd_audit.to_csv(BASE/'results/universe_sraf_count_crosscheck.csv',index=False)
    pd.DataFrame(shard_audit).to_csv(BASE/'results/universe_shard_audit.csv',index=False)
    df=pd.concat(kept,ignore_index=True)
    df['cik']=df.cik.astype(str).str.zfill(10)
    df['filing_date']=pd.to_datetime(df.filing_date).dt.strftime('%Y-%m-%d')
    df['accession_number']=df.filename.str.extract(r'/(\d{10}-\d{2}-\d{6})\.txt')[0]
    df['path_cik']=df.filename.str.extract(r'edgar/data/(\d+)/')[0].str.zfill(10)
    duplicates=df.duplicated(['cik','form_type','filing_date','filename'],keep=False)
    df[duplicates].to_csv(BASE/'results/universe_duplicate_records.csv',index=False)
    before=len(df)
    df=df.drop_duplicates(['cik','form_type','filing_date','filename']).sort_values(['filing_date','cik','accession_number'])
    df.to_parquet(BASE/'datasets/universe_annual_filings_2010_2021.parquet',index=False)
    df.to_csv(BASE/'datasets/universe_annual_filings_2010_2021.csv',index=False)
    entity=df.groupby('cik',as_index=False).agg(first_filing_date=('filing_date','min'),last_filing_date=('filing_date','max'),n_annual_filings=('accession_number','size'),n_filing_years=('year','nunique'))
    entity.to_csv(BASE/'datasets/universe_ciks_2010_2021.csv',index=False)
    annual=df.groupby('year',as_index=False).agg(annual_filings=('accession_number','size'),distinct_ciks=('cik','nunique'),distinct_accessions=('accession_number','nunique'),date_min=('filing_date','min'),date_max=('filing_date','max'))
    for form in sorted(ANNUAL):
        tab=df[df.form_type==form].groupby('year').size()
        annual[form]=annual.year.map(tab).fillna(0).astype(int)
    annual.to_csv(BASE/'results/universe_annual_counts_2010_2021.csv',index=False)
    quarterly=df.groupby(['year','quarter'],as_index=False).agg(annual_filings=('accession_number','size'),distinct_ciks=('cik','nunique'))
    quarterly.to_csv(BASE/'results/universe_annual_quarter_counts_2010_2021.csv',index=False)
    official=local_official()
    audit=official.merge(df[['cik','accession_number','filing_date','form_type','source_shard']],on=['cik','accession_number'],how='left',indicator=True)
    audit['date_match']=audit.official_filing_date.eq(audit.filing_date)
    audit['form_match']=audit.official_form_type.eq(audit.form_type)
    audit.to_csv(BASE/'results/universe_official_crosscheck.csv',index=False)
    summary={
      'status':'UNLABELED_FILING_FRAME_ONLY','source':'https://huggingface.co/datasets/kapilrao/SEC_filings_1994_2024',
      'source_manifest':str(manifest),'source_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
      'source_total_rows':sum(x['rows'] for x in shard_audit),'source_declared_total_rows':24943448,
      'source_download_bytes':sum(x['bytes'] for x in records),'source_all_20_sha256_verified':True,
      'raw_annual_rows':before,'unique_annual_filing_rows':len(df),'duplicate_rows_removed':before-len(df),
      'distinct_ciks':df.cik.nunique(),'distinct_accessions':df.accession_number.nunique(),
      'missing_accession':int(df.accession_number.isna().sum()),'path_cik_mismatch':int(df.cik.ne(df.path_cik).sum()),
      'expected_quarters':48,'observed_quarters':len(quarterly),
      'allsource_year_date_mismatch':sum(x['year_date_mismatch'] for x in shard_audit),
      'allsource_quarter_date_mismatch':sum(x['quarter_date_mismatch'] for x in shard_audit),
      'official_local_records':len(official),'official_local_distinct_ciks':official.cik.nunique(),
      'official_matched_records':int(audit['_merge'].eq('both').sum()),
      'official_unmatched_records':int(audit['_merge'].eq('left_only').sum()),
      'official_date_mismatches_when_matched':int((audit['_merge'].eq('both')&~audit.date_match).sum()),
      'official_form_mismatches_when_matched':int((audit['_merge'].eq('both')&~audit.form_match).sum()),
      'sraf_count_check_cells':len(nd_audit),'sraf_count_check_exact_matches':int(nd_audit.mirror_minus_sraf.eq(0).sum()),
      'sraf_count_check_total_abs_difference':int(nd_audit.mirror_minus_sraf.abs().sum()),
      'sraf_count_source':str(nd_source),'sraf_count_source_sha256':hashlib.sha256(nd_source.read_bytes()).hexdigest(),
      'limitations':['Third-party mirror completeness not established by known-filer crosscheck.','License card only says likely public domain; no explicit dataset redistribution license.','Annual filers are not automatically exchange-listed public operating companies.','No outcome labels or verified negatives assigned.','Joint filings, repeated/accession CIK and BRD group mapping require downstream entity audit.','2010-2021 is filing calendar year, not fiscal year.','No report date or acceptance timestamp in this master-index source.','Master index is retrospective archive; historical index corrections may exist.'],
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    }
    (BASE/'results/universe_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=int),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=int),flush=True)

if __name__=='__main__':main(sys.argv[1])
