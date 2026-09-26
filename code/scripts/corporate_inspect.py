"""Read-only inspection of bounded corporate raw probes; derived evidence to D:."""
import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifests = sorted(OUT.glob('corporate_access_manifest_*.json'))
    records = [row for path in manifests for row in json.loads(path.read_text())]
    def payload(url):
        matches = [x for x in records if x['url'] == url and x.get('status') == 200]
        row = matches[-1]
        path = Path(row['raw_path'])
        assert sha(path) == row['sha256']
        return path.read_bytes()
    archive = zipfile.ZipFile(BytesIO(payload('https://lopucki.law.ufl.edu/download_cases_table.php')))
    member = next(x for x in archive.namelist() if x.endswith('.csv'))
    brd = pd.read_csv(BytesIO(archive.read(member)), encoding='cp1252', low_memory=False)
    brd['parsed_event_date'] = pd.to_datetime(brd.DateFiled)
    brd['normalized_cik'] = brd.CikBefore.map(lambda v: f'{int(v):010d}' if pd.notna(v) else None)
    yearly = brd.groupby(brd.parsed_event_date.dt.year).agg(
        n_cases=('PrimaryKey', 'size'), n_cases_with_cik=('CikBefore', 'count'),
        n_distinct_cik=('CikBefore', 'nunique')).reset_index(names='event_year')
    yearly.to_csv(OUT / 'corporate_brd_counts.csv', index=False)
    recent = brd.loc[brd.parsed_event_date >= '2009-01-01']
    brd_sample = brd.loc[brd.NameCorp.str.contains('Hertz', case=False) | (brd.parsed_event_date >= '2021-01-01'),
        ['PrimaryKey','NameCorp','CikBefore','normalized_cik','DateFiled','Date10kBefore',
         'Date10kBeforeLink','CaseNum','Chapter','DistFiled','AssetsBefore','Refile']]
    brd_sample.to_csv(OUT / 'corporate_brd_sample.csv', index=False)
    schemas = {'brd': {'rows': len(brd), 'original_columns': len(brd.columns)-2,
                       'columns': list(brd.columns[:-2]), 'date_min': str(brd.parsed_event_date.min().date()),
                       'date_max': str(brd.parsed_event_date.max().date()), 'cik_nonmissing_cases': int(brd.CikBefore.notna().sum()),
                       'distinct_cik_nonmissing': int(brd.CikBefore.nunique()),
                       'cases_2009_on': len(recent), 'distinct_cik_2009_on': int(recent.CikBefore.nunique())},
               'sec': {}, 'notes': ['Case rows are not independent companies.',
                'BRD Date10kBefore is the covered period end, not SEC submission date.',
                'Dates in acceptanceDateTime are preserved verbatim; no intraday timezone claim.',
                'As-of sample uses filed strictly before decision_date and accession joins.']}
    samples, asof, vintages = [], [], []
    for cik, name, decision_date in [('0000886158','BBBY','2023-03-01'),('0001657853','Hertz','2020-03-01')]:
        sub = json.loads(payload(f'https://data.sec.gov/submissions/CIK{cik}.json'))
        filings = pd.DataFrame(sub['filings']['recent'])
        facts = json.loads(payload(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'))
        schemas['sec'][cik] = {'current_name': sub['name'], 'recent_count': len(filings),
            'recent_columns': list(filings.columns), 'older_files': sub['filings']['files'],
            'facts_top_keys': list(facts), 'Assets_USD_example': facts['facts']['us-gaap']['Assets']['units']['USD'][-1]}
        sample = filings.loc[(filings.form == '10-K') | filings['items'].str.contains('1.03', na=False)].copy()
        sample.insert(0,'cik',cik); sample.insert(1,'case_name',name)
        samples.append(sample)
        for tag in ['Assets','Liabilities','StockholdersEquity','CashAndCashEquivalentsAtCarryingValue']:
            concept = facts['facts']['us-gaap'].get(tag, {})
            data = pd.DataFrame(concept.get('units', {}).get('USD', []))
            if data.empty:
                continue
            eligible = data.loc[(data.filed < decision_date) & data.form.isin(['10-K','10-Q','10-K/A','10-Q/A'])]
            if eligible.empty:
                continue
            chosen = eligible.sort_values(['end','filed','accn']).iloc[-1]
            same = eligible.loc[(eligible.end == chosen.end) & (eligible.accn == chosen.accn)]
            assert same.val.nunique() == 1
            accession = filings.loc[filings.accessionNumber == chosen.accn]
            assert len(accession) == 1 and accession.iloc[0].filingDate == chosen.filed
            asof.append({'cik':cik,'name':name,'decision_date':decision_date,'tag':tag,'unit':'USD',
                         'period_end':chosen.end,'value':chosen.val,'filed':chosen.filed,'accession':chosen.accn,
                         'form':chosen.form,'acceptanceDateTime':accession.iloc[0].acceptanceDateTime})
            if cik == '0000886158' and tag == 'Assets':
                v = data.loc[data.end == '2017-02-25'].copy()
                v.insert(0,'cik',cik); v.insert(1,'tag',tag); vintages.append(v)
    pd.concat(samples, ignore_index=True).to_csv(OUT / 'corporate_submissions_sample.csv',index=False)
    pd.DataFrame(asof).to_csv(OUT / 'corporate_asof_facts.csv',index=False)
    pd.concat(vintages, ignore_index=True).to_csv(OUT / 'corporate_vintage_example.csv',index=False)
    protocols = pymupdf.open(stream=archive.read('Protocols.pdf'), filetype='pdf')
    excerpts = []
    for i, page in enumerate(protocols):
        text = page.get_text()
        if 'Date10kBefore. This field' in text or 'DateFiled. The month' in text:
            excerpts.append({'pdf_page_1_based':i+1,'text':text})
    (OUT / 'corporate_brd_protocol_evidence.json').write_text(json.dumps(excerpts,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT / 'corporate_schema.json').write_text(json.dumps(schemas,ensure_ascii=False,indent=2),encoding='utf-8')
    summary = {'manifest_files':[{'path':str(p),'sha256':sha(p)} for p in manifests],
               'n_requests':len(records),'total_downloaded_bytes':sum(x.get('bytes',0) for x in records),
               'statuses':pd.Series([x.get('status','error') for x in records]).value_counts().to_dict(),
               'cases_not_training_cohort':True,'models_fitted':0,
               'outputs':{p.name:sha(p) for p in OUT.glob('corporate_*') if p.is_file() and not p.name.startswith('corporate_access_manifest') and p.name != 'corporate_inspection_manifest.json'}}
    (OUT / 'corporate_inspection_manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'brd_rows':len(brd),'cases_2009_on':len(recent),'distinct_cik_2009_on':int(recent.CikBefore.nunique()),'asof_rows':len(asof),'requests':len(records),'downloaded_bytes':summary['total_downloaded_bytes']},ensure_ascii=False))


if __name__ == '__main__':
    main()
