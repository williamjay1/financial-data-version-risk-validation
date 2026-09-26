"""Accession-linked annual financial snapshots and coherent later comparatives.

This builds evidence, not a claim of complete historical API vintages. No model
is fitted here. Unknown API coverage is kept in a separate company flow table.
The latest arm uses ONE later accession containing ALL initially observed facts,
with identical concepts, USD units and period boundaries. Initially missing
facts stay missing. No later report is required for cohort eligibility.
"""
import argparse
import hashlib
import json
import math
import shutil
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'
DATA = ROOT / 'datasets'
CACHE = ROOT / 'cache' / 'sec'
TAGS = {
    'assets': ['Assets'],
    'liabilities': ['Liabilities'],
    'equity': ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
    'cash': ['CashAndCashEquivalentsAtCarryingValue', 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'],
    'current_assets': ['AssetsCurrent'],
    'current_liabilities': ['LiabilitiesCurrent'],
    'net_income': ['NetIncomeLoss', 'ProfitLoss'],
    'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'SalesRevenueGoodsNet'],
    'operating_income': ['OperatingIncomeLoss'],
    'operating_cash': ['NetCashProvidedByUsedInOperatingActivities'],
    'retained_earnings': ['RetainedEarningsAccumulatedDeficit'],
}
FLOW = {'net_income', 'revenue', 'operating_income', 'operating_cash'}
CUTOFF = '2026-09-21'

def sources():
    rows = []
    for path in sorted(OUT.glob('corporate_access_manifest_*.json')):
        rows.extend(json.loads(path.read_text(encoding='utf-8')))
    for pattern in ['expanded_sec_manifest_*.jsonl', 'control_sec_manifest_*.jsonl']:
        for path in sorted(OUT.glob(pattern)):
            for line in path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    rows.append(json.loads(line))
    return {r['url']: r for r in rows if r.get('status') == 200 and r.get('raw_path')}

def cached(row):
    """Copy each immutable original once; parsing and subsequent computation use D:."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dst = CACHE / (row['sha256'] + '.json')
    if not dst.exists():
        raw = Path(row['raw_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Raw hash mismatch: ' + row['raw_path'])
        dst.write_bytes(raw)
    return json.loads(dst.read_text(encoding='utf-8'))

def fact_lookup(doc):
    grouped = {}
    for tag in {t for tags in TAGS.values() for t in tags}:
        by_accession = defaultdict(list)
        for value in doc.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).get('USD', []):
            if value.get('filed', '9999') <= CUTOFF and value.get('form') in {'10-K','10-K/A','10-KT','10-KT/A','10-Q','10-Q/A','10-QT'}:
                by_accession[value['accn']].append(value)
        grouped[tag] = by_accession
    return grouped

def snapshot(filing, lookup):
    accn, end, filed = filing['accessionNumber'], filing['reportDate'], filing['filingDate']
    values, context, ambiguous = {}, {}, []
    for feature, tags in TAGS.items():
        values[feature] = np.nan
        for tag in tags:
            found = [r for r in lookup[tag].get(accn, []) if r.get('end') == end and r.get('filed', '9999') <= filed]
            if feature in FLOW:
                found = [r for r in found if r.get('start') and 330 <= (pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).days <= 400]
            else:
                found = [r for r in found if not r.get('start')]
            # Distinct period starts or values under the same accession are not
            # silently resolved by ordering. They require separate source review.
            signatures = {(r.get('start', ''), r['val']) for r in found}
            if len(signatures) > 1:
                ambiguous.append(feature + ':' + tag)
                break
            if len(signatures) == 1:
                fact = found[0]
                values[feature] = float(fact['val'])
                context[feature] = {'tag':tag, 'start':fact.get('start',''), 'end':end,
                                    'unit':'USD', 'accn':accn, 'filed':filed}
                break
    return values, context, ambiguous

def later_bundle(a, contexts, original, lookup, filing_map):
    possibilities = None
    per_feature = {}
    for feature, ctx in contexts.items():
        valid = {}
        for accn, rows in lookup[ctx['tag']].items():
            filing = filing_map.get(accn)
            if not filing or not original['filingDate'] < filing['filingDate'] <= CUTOFF:
                continue
            candidates = [r for r in rows if r.get('start','') == ctx['start'] and r.get('end') == ctx['end']]
            unique = {r['val'] for r in candidates}
            if len(unique) == 1:
                valid[accn] = float(next(iter(unique)))
        per_feature[feature] = valid
        possibilities = set(valid) if possibilities is None else possibilities.intersection(valid)
    b = a.copy()
    latest_accession = ''
    if contexts and possibilities:
        latest_accession = max(possibilities, key=lambda k: (filing_map[k]['filingDate'], k))
        b.update({feature: valid[latest_accession] for feature, valid in per_feature.items()})
    c = a.copy()
    c_accn = {}
    for feature, valid in per_feature.items():
        if valid:
            chosen = max(valid, key=lambda k:(filing_map[k]['filingDate'],k))
            c[feature] = valid[chosen]
            c_accn[feature] = chosen
    return b, latest_accession, c, c_accn

def ratios(values):
    a = values['assets']
    result = {'log_assets': math.log(a) if np.isfinite(a) and a > 0 else np.nan}
    for key in ['liabilities','equity','cash','net_income','revenue','operating_income','operating_cash','retained_earnings']:
        result[key + '_to_assets'] = values[key] / a if np.isfinite(a) and a > 0 else np.nan
    result['working_capital_to_assets'] = (values['current_assets'] - values['current_liabilities']) / a if np.isfinite(a) and a > 0 else np.nan
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    lookup_sources = sources()
    with zipfile.ZipFile(BytesIO(Path(lookup_sources['https://lopucki.law.ufl.edu/download_cases_table.php']['raw_path']).read_bytes())) as archive:
        brd = pd.read_csv(BytesIO(archive.read(next(n for n in archive.namelist() if n.endswith('.csv')))), encoding='cp1252', low_memory=False)
    brd['event_date'] = pd.to_datetime(brd.DateFiled)
    brd['cik'] = brd.CikBefore.map(lambda v: f'{int(v):010d}' if pd.notna(v) else '')
    DATA.mkdir(exist_ok=True)
    brd.to_parquet(DATA / 'brd_all_events.parquet', index=False)
    first_events = brd.loc[brd.cik.ne('')].groupby('cik').event_date.min().to_dict()
    all_ciks = sorted({u.rsplit('CIK',1)[-1].split('.')[0] for u in lookup_sources if '/submissions/CIK' in u and '-submissions-' not in u})
    if args.limit:
        all_ciks = all_ciks[:args.limit]
    panel, flows, fact_rows, case_links = [], [], [], []
    for i,cik in enumerate(all_ciks,1):
        sub = cached(lookup_sources[f'https://data.sec.gov/submissions/CIK{cik}.json'])
        frames = [pd.DataFrame(sub['filings']['recent'])]
        missing_history = []
        for older in sub['filings'].get('files', []):
            # All later history can contain comparative vintages; original
            # annual eligibility still ends in 2021.
            url = 'https://data.sec.gov/submissions/' + older['name']
            if url in lookup_sources:
                frames.append(pd.DataFrame(cached(lookup_sources[url])))
            elif older['filingTo'] >= '2008-01-01':
                missing_history.append(older['name'])
        filings = pd.concat(frames,ignore_index=True).drop_duplicates('accessionNumber')
        filing_map = {r['accessionNumber']:r for r in filings.to_dict('records')}
        for case in brd.loc[brd.cik.eq(cik)].to_dict('records'):
            import re
            matched = re.findall(r'\d{10}-\d{2}-\d{6}',str(case.get('Date10kBeforeLink','')))
            original = filing_map.get(matched[-1]) if matched else None
            case_links.append({'cik':cik,'case_id':str(case['PrimaryKey']),'event_date':str(case['event_date'].date()),
                               'linked_accession':matched[-1] if matched else '',
                               'link_matched':original is not None,'linked_form':original.get('form') if original else None,
                               'linked_filed':original.get('filingDate') if original else None,
                               'link_on_or_after_event': original['filingDate'] >= str(case['event_date'].date()) if original else None})
        annual = filings.loc[filings.form.isin(['10-K','10-KT']) & filings.filingDate.between('2008-01-01','2021-12-30')].copy()
        annual = annual.loc[annual.reportDate.fillna('').ne('')].sort_values(['filingDate','accessionNumber']).drop_duplicates('reportDate',keep='first')
        fact_url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
        flow = {'cik':cik,'current_name_audit_only':sub.get('name'),'annual_filings':len(annual),
                'facts_available':fact_url in lookup_sources,'missing_history':'|'.join(missing_history),
                'first_registry_event':str(first_events[cik].date()) if cik in first_events else '',
                'filings_with_item_103':int(filings.get('items',pd.Series('',index=filings.index)).fillna('').str.contains(r'(?:^|,)1\.03(?:,|$)',regex=True).sum())}
        flows.append(flow)
        if fact_url not in lookup_sources:
            continue
        lookup = fact_lookup(cached(lookup_sources[fact_url]))
        for filing in annual.to_dict('records'):
            decision = pd.Timestamp(filing['filingDate']) + pd.Timedelta(days=1)
            event = first_events.get(cik)
            pre_event = event is None or decision < event
            a,contexts,ambiguous = snapshot(filing,lookup)
            b,later_accn,c,c_accns = later_bundle(a,contexts,filing,lookup,filing_map)
            row = {'cik':cik,'accession':filing['accessionNumber'],'form':filing['form'],
                   'filing_date':filing['filingDate'],'decision_date':str(decision.date()),'fiscal_end':filing['reportDate'],
                   'pre_first_registry_event':pre_event,'registry_event_365':int(event is not None and decision < event <= decision+pd.Timedelta(days=365)),
                   'first_registry_event':str(event.date()) if event is not None else '',
                   'report_lag_days':(pd.Timestamp(filing['filingDate'])-pd.Timestamp(filing['reportDate'])).days,
                   'n_original_facts':len(contexts),'ambiguous':';'.join(ambiguous),'later_accession':later_accn,
                   'later_filed':filing_map[later_accn]['filingDate'] if later_accn else '',
                   'n_coherent_changed':sum(a[k]!=b[k] for k in contexts),'n_per_tag_changed':sum(a[k]!=c[k] for k in contexts),
                   'per_tag_accessions':len({c_accns.get(feature,filing['accessionNumber']) for feature in contexts})}
            for version,values in [('A',a),('B',b),('C',c)]:
                row.update({version+'_'+k:v for k,v in ratios(values).items()})
            panel.append(row)
            for feature,ctx in contexts.items():
                fact_rows.append({'cik':cik,'original_accession':filing['accessionNumber'],'feature':feature,**ctx,
                                  'A':a[feature],'B':b[feature],'B_accession':later_accn or filing['accessionNumber'],
                                  'C':c[feature],'C_accession':c_accns.get(feature,filing['accessionNumber'])})
        if i % 50 == 0:
            print(json.dumps({'companies_processed':i,'panel_rows':len(panel),'facts':len(fact_rows)}),flush=True)
    pd.DataFrame(panel).to_parquet(DATA / 'vintage_panel.parquet',index=False)
    pd.DataFrame(fact_rows).to_parquet(DATA / 'vintage_facts.parquet',index=False)
    pd.DataFrame(flows).to_csv(OUT / 'vintage_company_flow.csv',index=False)
    pd.DataFrame(case_links).to_csv(OUT / 'vintage_case_link_audit.csv',index=False)
    summary = {'companies':len(flows),'panel_rows':len(panel),'fact_rows':len(fact_rows),
               'tag_mapping':TAGS,'raw_source_count':len(lookup_sources),'later_version_cutoff':CUTOFF,
               'models_fitted':0,'note':'Extraction panel includes all successfully retrieved entities, including sampled companies and source-audit cases. The locked historical sampling frame, domain rules and weights are applied separately by prepare_model_cohort.py.'}
    (OUT / 'vintage_panel_build_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)

if __name__ == '__main__':
    main()
