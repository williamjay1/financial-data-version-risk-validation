"""Expand the BRD event cohort with auditable SEC API snapshots, without fitting.

Resumable by URL, maximum two workers and globally spaced starts. All originals
are written exclusively under E:, made read-only immediately, and hashed.
No authentication, spoofed personal contact, or response-block workarounds.
"""
import argparse
import hashlib
import json
import os
import stat
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'
RAW = Path('<archived-record-root>/...')
UA = 'Academic financial statement reproducibility study/1.0 (public-data research; bounded sequential-rate collection)'
LOCK = threading.Lock()
RATE = {'last': 0.0, 'blocks': 0}
LOCAL = threading.local()

def records():
    out = []
    for path in sorted(OUT.glob('corporate_access_manifest_*.json')):
        out += json.loads(path.read_text(encoding='utf-8'))
    for pattern in ['expanded_sec_manifest_*.jsonl', 'control_sec_manifest_*.jsonl']:
        for path in sorted(OUT.glob(pattern)):
            out += [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    return out

def fetch(url, run):
    with LOCK:
        if RATE['blocks'] >= 3:
            return {'url': url, 'error': 'collection_stopped_after_repeated_403_or_429'}
        delay = max(0, 0.8 - (time.monotonic() - RATE['last']))
        time.sleep(delay)
        RATE['last'] = time.monotonic()
    if not hasattr(LOCAL, 'session'):
        LOCAL.session = requests.Session()
        LOCAL.session.headers['User-Agent'] = UA
    row = {'url': url, 'requested_utc': datetime.now(timezone.utc).isoformat()}
    try:
        with LOCAL.session.get(url, timeout=(12, 45), stream=True) as response:
            chunks = []
            nbytes = 0
            for block in response.iter_content(65536):
                nbytes += len(block)
                if nbytes > 35 * 1024 * 1024:
                    raise ValueError('Response exceeded 35 MiB request bound')
                chunks.append(block)
            body = b''.join(chunks)
            name = RAW / f'{run}_{uuid.uuid4().hex[:10]}_{url.rsplit("/", 1)[-1]}'
            with name.open('xb') as output:
                output.write(body)
            os.chmod(name, stat.S_IREAD)
            row.update(status=response.status_code, raw_path=str(name), bytes=len(body),
                       sha256=hashlib.sha256(body).hexdigest(), final_url=response.url,
                       content_type=response.headers.get('Content-Type'), readonly=True)
            with LOCK:
                if response.status_code in (403, 429):
                    RATE['blocks'] += 1
    except Exception as error:
        row['error'] = repr(error)
    return row

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=0, help='Optional first CIK limit for smoke check; zero means full fixed event cohort')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    (ROOT / 'datasets').mkdir(exist_ok=True)
    known = {r['url']: r for r in records()}
    source = known['https://lopucki.law.ufl.edu/download_cases_table.php']
    body = Path(source['raw_path']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == source['sha256']
    with zipfile.ZipFile(BytesIO(body)) as archive:
        brd = pd.read_csv(BytesIO(archive.read(next(n for n in archive.namelist() if n.endswith('.csv')))), encoding='cp1252', low_memory=False)
    brd['event_date'] = pd.to_datetime(brd.DateFiled)
    cases = brd.loc[brd.event_date.between('2009-01-01', '2022-12-31')].copy()
    cases['cik'] = cases.CikBefore.map(lambda v: f'{int(v):010d}' if pd.notna(v) else '')
    cases.to_parquet(ROOT / 'datasets' / 'expanded_brd_events.parquet', index=False)
    ciks = sorted(cases.loc[cases.cik.ne(''), 'cik'].unique())
    if args.limit:
        ciks = ciks[:args.limit]
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    manifest_path = OUT / f'expanded_sec_manifest_{run}.jsonl'
    allrows = []
    def run_urls(urls, stage):
        pending = list(dict.fromkeys(url for url in urls if url not in known))
        print(json.dumps({'stage': stage, 'pending_requests': len(pending), 'cached_urls': len(urls)-len(pending)}), flush=True)
        with manifest_path.open('a', encoding='utf-8') as log, ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(fetch, url, run) for url in pending]
            for i, future in enumerate(as_completed(futures), 1):
                row = future.result()
                log.write(json.dumps(row, ensure_ascii=False) + '\n')
                log.flush()
                known[row['url']] = row
                allrows.append(row)
                if i % 20 == 0 or i == len(pending) or row.get('status') in (403,429):
                    print(json.dumps({'stage': stage, 'completed': i, 'total': len(pending),
                                      'status_counts': pd.Series([r.get('status','error') for r in allrows]).value_counts().to_dict()}, default=int), flush=True)
    urls = [url for cik in ciks for url in (f'https://data.sec.gov/submissions/CIK{cik}.json', f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')]
    run_urls(urls, 'company_snapshots')
    history = []
    for cik in ciks:
        record = known.get(f'https://data.sec.gov/submissions/CIK{cik}.json', {})
        if record.get('status') != 200:
            continue
        doc = json.loads(Path(record['raw_path']).read_text(encoding='utf-8'))
        for older in doc['filings'].get('files', []):
            if older['filingFrom'] <= '2026-09-21' and older['filingTo'] >= '2008-01-01':
                history.append('https://data.sec.gov/submissions/' + older['name'])
    run_urls(history, 'historical_submissions')
    selected = [known[u] for u in urls + history if u in known]
    (OUT / 'expanded_sec_source_index.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {'run':run,'ciks_requested':len(ciks),'cases_2009_2022':len(cases),
               'source_index_entries':len(selected),'downloaded_this_run':len(allrows),
               'status_counts':pd.Series([r.get('status','error') for r in selected]).value_counts().to_dict(),
               'bytes_this_run':sum(r.get('bytes',0) for r in allrows),'models_fitted':0}
    (OUT / f'expanded_sec_summary_{run}.json').write_text(json.dumps(summary, indent=2, default=int),encoding='utf-8')
    print(json.dumps(summary, default=int), flush=True)

if __name__ == '__main__':
    main()
