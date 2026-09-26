"""Deterministic eight-company BRD/SEC connection audit; no fitting/negative labels.

--download performs at most two primary API requests per sampled company, plus
explicitly listed older submissions files when needed. All requests use the
bounded corporate_probe.py writer, all raw files use unique E: names.
Default only reads already downloaded probes and writes derived audit evidence.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'
PROBE = ROOT / 'scripts/corporate_probe.py'
YEARS = (2009,2011,2013,2015,2017,2019,2021,2022)


def manifests():
    return [r for p in sorted(OUT.glob('corporate_access_manifest_*.json')) for r in json.loads(p.read_text())]


def record(url):
    found = [r for r in manifests() if r['url'] == url]
    return found[-1] if found else None


def payload(url):
    row = record(url)
    if row is None or row.get('status') != 200:
        return None
    data = Path(row['raw_path']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == row['sha256']
    return data


def write_json(name, value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true')
    args = parser.parse_args()
    archive = zipfile.ZipFile(BytesIO(payload('https://lopucki.law.ufl.edu/download_cases_table.php')))
    brd = pd.read_csv(BytesIO(archive.read(next(x for x in archive.namelist() if x.endswith('.csv')))),encoding='cp1252',low_memory=False)
    brd['event_date'] = pd.to_datetime(brd.DateFiled)
    brd = brd.loc[brd.CikBefore.notna()].copy()
    brd['cik'] = brd.CikBefore.map(lambda x:f'{int(x):010d}')
    chosen, used = [], set()
    for year in YEARS:
        part = brd.loc[(brd.event_date.dt.year == year)&~brd.cik.isin(used)].sort_values(['event_date','cik','PrimaryKey'])
        if part.empty:
            raise ValueError(f'No eligible distinct CIK in {year}')
        row = part.iloc[0]
        used.add(row.cik)
        chosen.append({k: str(row[k]) for k in ['PrimaryKey','NameCorp','cik','DateFiled','Date10kBefore','Date10kBeforeLink']})
    plan = {'years':YEARS,'rule':'For each fixed year, choose earliest DateFiled, then lowest normalized CIK, then PrimaryKey; skip already selected CIK. No filtering on API or fact availability. Eight different CIK. This is an access audit of positive cases, not a prevalence sample.', 'companies':chosen}
    planpath = OUT/'corporate_connection_sample_plan.json'
    if planpath.exists():
        assert json.loads(planpath.read_text()) == json.loads(json.dumps(plan))
    else:
        write_json(planpath.name,plan)
    print(json.dumps(plan,ensure_ascii=False),flush=True)
    urls = []
    for case in chosen:
        urls += [f"https://data.sec.gov/submissions/CIK{case['cik']}.json", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{case['cik']}.json"]
    if args.download:
        pending = [url for url in urls if record(url) is None]
        for start in range(0,len(pending),12):
            subprocess.run([sys.executable,str(PROBE),*pending[start:start+12]],check=True)
        # Current JSON may only contain recent filings. Download only history
        # files whose official date interval intersects the three pre-event years.
        older = []
        for case in chosen:
            raw = payload(f"https://data.sec.gov/submissions/CIK{case['cik']}.json")
            if raw is None:
                continue
            event = pd.Timestamp(case['DateFiled'])
            for item in json.loads(raw)['filings']['files']:
                if pd.Timestamp(item['filingFrom']) < event and pd.Timestamp(item['filingTo']) >= event-pd.DateOffset(years=3):
                    url = 'https://data.sec.gov/submissions/'+item['name']
                    if record(url) is None:
                        older.append(url)
        for start in range(0,len(older),12):
            subprocess.run([sys.executable,str(PROBE),*older[start:start+12]],check=True)
    results, facts_rows, vintage_rows, protocols = [], [], [], []
    for case in chosen:
        cik, event = case['cik'],pd.Timestamp(case['DateFiled'])
        suburl = f'https://data.sec.gov/submissions/CIK{cik}.json'
        facturl = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
        row = {**case,'event_date':str(event.date()),'submissions_status':(record(suburl) or {}).get('status','not_requested'),'companyfacts_status':(record(facturl) or {}).get('status','not_requested')}
        subraw, factraw = payload(suburl),payload(facturl)
        if subraw is None:
            row['audit_status']='submissions_unavailable';results.append(row);continue
        sub = json.loads(subraw)
        pieces = [pd.DataFrame(sub['filings']['recent'])]
        hist_missing=[]
        for item in sub['filings']['files']:
            if pd.Timestamp(item['filingFrom']) < event and pd.Timestamp(item['filingTo']) >= event-pd.DateOffset(years=3):
                raw=payload('https://data.sec.gov/submissions/'+item['name'])
                if raw is None:hist_missing.append(item['name'])
                else:pieces.append(pd.DataFrame(json.loads(raw)))
        filings=pd.concat(pieces,ignore_index=True).drop_duplicates('accessionNumber')
        links=re.findall(r'\d{10}-\d{2}-\d{6}',case['Date10kBeforeLink'])
        if links:
            matched=filings.loc[filings.accessionNumber==links[-1]]
            row['brd_link_accession']=links[-1]
            if len(matched)==1:
                original=matched.iloc[0]
                row.update(brd_link_sec_form=original.form,brd_link_sec_filed=original.filingDate,
                           brd_link_is_pre_event=pd.Timestamp(original.filingDate)<event)
        annual=filings.loc[(filings.form=='10-K')&(pd.to_datetime(filings.filingDate)<event)].sort_values(['filingDate','acceptanceDateTime'])
        row['history_files_missing']=';'.join(hist_missing)
        if annual.empty:
            row['audit_status']='no_pre_event_10k_in_retrieved_history';results.append(row);continue
        latest=annual.iloc[-1]
        row.update(last_10k_accession=latest.accessionNumber,last_10k_filed=latest.filingDate,
                   last_10k_period_end=latest.reportDate,last_10k_acceptance=latest.acceptanceDateTime,
                   days_filing_to_event=(event-pd.Timestamp(latest.filingDate)).days,
                   brd_period_matches_sec=str(pd.Timestamp(case['Date10kBefore']).date())==latest.reportDate)
        if factraw is None:
            row['audit_status']='companyfacts_unavailable';results.append(row);continue
        facts=json.loads(factraw)['facts'].get('us-gaap',{})
        n_available=0
        # Snapshot constrained to the exact last pre-event annual filing accession.
        for tag in ['Assets','Liabilities','StockholdersEquity','CashAndCashEquivalentsAtCarryingValue','NetIncomeLoss','Revenues']:
            table=pd.DataFrame(facts.get(tag,{}).get('units',{}).get('USD',[]))
            if table.empty:continue
            eligible=table.loc[(table.accn==latest.accessionNumber)&(table.filed<=latest.filingDate)&(table.end==latest.reportDate)].copy()
            if not eligible.empty:
                # For flows select annual span, never mix quarterly and annual values.
                if 'start' in eligible and eligible.start.notna().any():
                    duration=(pd.to_datetime(eligible.end)-pd.to_datetime(eligible.start)).dt.days
                    eligible=eligible.loc[duration.between(330,400)]
                if not eligible.empty:
                    n_available+=1
                    for fact in eligible.drop_duplicates(['accn','end','val']).to_dict('records'):
                        facts_rows.append({'cik':cik,'NameCorp':case['NameCorp'],'tag':tag,'unit':'USD',**fact})
            # Look for same tag/unit/period with different values in later filings.
            groupkeys=['end']+(['start'] if 'start' in table and table.start.notna().any() else [])
            for _, group in table.groupby(groupkeys,dropna=False):
                if group.val.nunique()>1 and (group.filed<=latest.filingDate).any() and (group.filed>latest.filingDate).any():
                    for fact in group.sort_values(['filed','accn']).head(12).to_dict('records'):
                        vintage_rows.append({'cik':cik,'NameCorp':case['NameCorp'],'tag':tag,'unit':'USD','note':'Different later value in same tag/unit/period; not automatically proof of a formal restatement.',**fact})
                    break
        row['n_requested_standard_tags_available']=n_available
        row['n_requested_standard_tags']=6
        row['audit_status']='joined_snapshot' if n_available else 'no_requested_standard_tags_at_exact_accession'
        results.append(row)
    for i,page in enumerate(pymupdf.open(stream=archive.read('Protocols.pdf'),filetype='pdf')):
        if i in [1,2,3,4,7,12,15]:protocols.append({'page_1_based':i+1,'text':page.get_text()})
    pd.DataFrame(results).to_csv(OUT/'corporate_connection_audit.csv',index=False)
    pd.DataFrame(facts_rows).to_csv(OUT/'corporate_connection_facts.csv',index=False)
    pd.DataFrame(vintage_rows).to_csv(OUT/'corporate_connection_vintages.csv',index=False)
    write_json('corporate_codebook_evidence.json',protocols)
    summary={'n_fixed_sample':len(chosen),'status_counts':pd.Series([r['audit_status'] for r in results]).value_counts().to_dict(),
             'n_facts_rows':len(facts_rows),'n_vintage_rows':len(vintage_rows),'no_negative_labels_created':True,
             'no_models_fitted':True,'sample_plan_sha256':hashlib.sha256(planpath.read_bytes()).hexdigest()}
    write_json('corporate_connection_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
