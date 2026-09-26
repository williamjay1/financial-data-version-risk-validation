"""Independent checks of raw provenance and selected derived feasibility evidence."""
import hashlib
import json
import re
import stat
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'
RAW = Path('<archived-record-root>/...')

def main():
    manifests = list(OUT.glob('corporate_access_manifest_*.json')) + list(OUT.glob('root_source_manifest_*.json')) + [OUT / 'bank_raw_manifest.json'] + list(ROOT.glob('literature_access_*.json'))
    records = []
    for path in manifests:
        for row in json.loads(path.read_text(encoding='utf-8')):
            if 'raw_path' not in row and row.get('path'):
                row['raw_path'] = row['path']
            records.append(row)
    issues = []
    for row in records:
        if not row.get('raw_path'):
            continue
        path = Path(row['raw_path'])
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != row['sha256']:
            issues.append({'path': str(path), 'issue': 'hash_mismatch'})
    inventory = []
    for path in sorted(RAW.rglob('*')):
        if path.is_file():
            readonly = bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
            inventory.append({'path': str(path), 'bytes': path.stat().st_size,
                              'readonly': readonly, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUT / 'integrated_raw_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    issues += [{'path': row['path'], 'issue': 'raw_not_readonly'} for row in inventory if not row['readonly']]
    def payload(url):
        found = [r for r in records if r['url'] == url and r.get('status', r.get('http_status')) == 200]
        if not found:
            raise KeyError(url)
        return Path(found[-1]['raw_path']).read_bytes()
    brd_zip = zipfile.ZipFile(BytesIO(payload('https://lopucki.law.ufl.edu/download_cases_table.php')))
    brd = pd.read_csv(BytesIO(brd_zip.read(next(n for n in brd_zip.namelist() if n.endswith('.csv')))), encoding='cp1252', low_memory=False)
    dates = pd.to_datetime(brd.DateFiled)
    recent = brd.loc[dates.between('2009-01-01', '2022-12-31')]
    audit = pd.read_csv(OUT / 'corporate_connection_audit.csv', dtype={'cik': str})
    facts = pd.read_csv(OUT / 'corporate_connection_facts.csv', dtype={'cik': str})
    verified_facts = 0
    for _, row in facts.iterrows():
        company = json.loads(payload(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{row.cik}.json'))
        candidates = company['facts']['us-gaap'][row.tag]['units'][row.unit]
        match = [r for r in candidates if r.get('accn') == row.accn and r.get('end') == row.end
                 and r.get('filed') == row.filed and r.get('val') == row.val
                 and (pd.isna(row.get('start')) or r.get('start') == row.start)]
        selected = audit.loc[audit.cik == row.cik].iloc[0]
        if not match or row.filed >= selected.event_date or row.accn != selected.last_10k_accession:
            issues.append({'cik': row.cik, 'tag': row.tag, 'issue': 'fact_provenance_or_cutoff'})
        else:
            verified_facts += 1
    links = []
    for _, row in audit.iterrows():
        sub = json.loads(payload(f'https://data.sec.gov/submissions/CIK{row.cik}.json'))
        chunks = [pd.DataFrame(sub['filings']['recent'])]
        for older in sub['filings'].get('files', []):
            url = 'https://data.sec.gov/submissions/' + older['name']
            try:
                chunks.append(pd.DataFrame(json.loads(payload(url))))
            except KeyError:
                pass
        allfilings = pd.concat(chunks, ignore_index=True).drop_duplicates('accessionNumber')
        match = re.search(r'(\d{10}-\d{2}-\d{6})', str(row.Date10kBeforeLink))
        if not match:
            continue
        found = allfilings.loc[allfilings.accessionNumber == match.group(1)]
        if len(found):
            link = found.iloc[0]
            links.append({'cik': row.cik, 'name': row.NameCorp, 'event_date': row.event_date,
                          'accession': match.group(1), 'form': link.form, 'filed': link.filingDate,
                          'filed_after_event': link.filingDate > row.event_date})
    pd.DataFrame(links).to_csv(OUT / 'independent_brd_link_dates.csv', index=False)
    bank_records = json.loads(payload('https://api.fdic.gov/banks/failures?limit=10000&sort_by=FAILDATE&sort_order=DESC&format=json'))
    bank = pd.DataFrame([r['data'] for r in bank_records['data']])
    result = {
        'checked_utc': datetime.now(timezone.utc).isoformat(),
        'recorded_raw_hashes_checked': sum(bool(r.get('raw_path')) for r in records),
        'raw_files_including_literature': len(inventory), 'raw_bytes': sum(r['bytes'] for r in inventory),
        'raw_not_readonly': [r['path'] for r in inventory if not r['readonly']],
        'brd_shape': list(brd.shape), 'brd_2009_2022_cases': len(recent),
        'brd_2009_2022_unique_cik': int(recent.CikBefore.nunique()),
        'fixed_positive_case_audit_status': audit.audit_status.value_counts().to_dict(),
        'corporate_facts_raw_matched_and_pre_event': verified_facts,
        'brd_link_date_checks': links,
        'fdic_event_rows': len(bank),
        'issues': issues,
        'interpretation': 'Data-connection audit only; case-only sample cannot establish prevalence, model quality, or population error rates.'
    }
    (OUT / 'independent_stage_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if issues:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
