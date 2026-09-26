"""Retrieve official SEC snapshots for the locked probability sample."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import expanded_sec_fetch as sec

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results'

def main():
    sample = pd.read_parquet(ROOT/'datasets/sampling_frame.parquet')
    ciks = sorted(sample.loc[sample.selected,'cik'])
    sec.RAW = Path('<archived-record-root>/...')
    sec.RAW.mkdir(parents=True,exist_ok=True)
    known = {r['url']:r for r in sec.records()}
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    logpath = OUT/f'control_sec_manifest_{run}.jsonl'
    new = []
    def stage(urls,label):
        pending = list(dict.fromkeys(u for u in urls if u not in known))
        print(json.dumps({'stage':label,'pending':len(pending),'already_present':len(urls)-len(pending)}),flush=True)
        # Six concurrent waits hide network latency; starts remain globally
        # spaced by 0.8 seconds in sec.fetch (at most 1.25 requests/second).
        with logpath.open('a',encoding='utf-8') as log, ThreadPoolExecutor(max_workers=6) as pool:
            fs = [pool.submit(sec.fetch,u,run) for u in pending]
            for i,f in enumerate(as_completed(fs),1):
                row = f.result()
                log.write(json.dumps(row,ensure_ascii=False)+'\n')
                log.flush()
                known[row['url']] = row
                new.append(row)
                if i%50 == 0 or i == len(fs):
                    print(json.dumps({'stage':label,'done':i,'total':len(fs),'statuses':pd.Series([r.get('status','error') for r in new]).value_counts().to_dict()},default=int),flush=True)
    urls = [u for c in ciks for u in [f'https://data.sec.gov/submissions/CIK{c}.json',f'https://data.sec.gov/api/xbrl/companyfacts/CIK{c}.json']]
    stage(urls,'selected_cik_snapshots')
    history = []
    for c in ciks:
        r = known.get(f'https://data.sec.gov/submissions/CIK{c}.json',{})
        if r.get('status') != 200:
            continue
        doc = json.loads(Path(r['raw_path']).read_text(encoding='utf-8'))
        for old in doc['filings'].get('files',[]):
            if old['filingTo'] >= '2008-01-01' and old['filingFrom'] <= '2026-09-21':
                history.append('https://data.sec.gov/submissions/'+old['name'])
    stage(history,'selected_cik_history')
    selected = [known[u] for u in urls+history if u in known]
    summary = {'run':run,'selected_ciks':len(ciks),'records':len(selected),'new_downloads':len(new),'new_bytes':sum(r.get('bytes',0) for r in new),'statuses':pd.Series([r.get('status','error') for r in selected]).value_counts().to_dict()}
    (OUT/f'control_sec_summary_{run}.json').write_text(json.dumps(summary,indent=2,default=int),encoding='utf-8')
    print(json.dumps(summary,default=int),flush=True)

if __name__ == '__main__':
    main()
