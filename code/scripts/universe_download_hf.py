"""Download only a historical SEC filing-index mirror (no filing text)."""
from __future__ import annotations
import concurrent.futures, hashlib, json, stat, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import requests
from universe_probe import BASE, RAW, UA

TREE=RAW/'universe_20260921T084535Z_48fcec2d_03.bin'
OLD_MANIFEST=BASE/'results/universe_access_manifest_20260921T084718Z_2a5aca4b.json'

def main():
    run=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    entries=[x for x in json.loads(TREE.read_text(encoding='utf-8')) if x['path'].endswith('.parquet')]
    old=json.loads(OLD_MANIFEST.read_text(encoding='utf-8'))
    existing={x['url'].split('/resolve/main/')[-1]:x for x in old if x.get('content_type')=='application/octet-stream'}
    for previous_manifest in sorted((BASE/'results').glob('universe_hf_download_*.json')):
        for entry in json.loads(previous_manifest.read_text(encoding='utf-8')):
            if entry.get('verified_sha256') and Path(entry['raw_path']).exists():
                existing[entry['source_path']]=entry
    manifest=BASE/'results'/f'universe_hf_download_{run}.json'
    rows=[]
    def one(item):
        source=item['path']; url='https://huggingface.co/datasets/kapilrao/SEC_filings_1994_2024/resolve/main/'+source
        expected=item['lfs']['oid']
        row={'source_path':source,'url':url,'expected_sha256':expected,'expected_bytes':item['size'],'request_utc':datetime.now(timezone.utc).isoformat(),'used_authentication':False,'user_agent':UA}
        if source in existing:
            previous=existing[source]
            if previous['sha256']!=expected: raise ValueError('Existing original differs from repository LFS hash')
            row.update(raw_path=previous['raw_path'],sha256=previous['sha256'],bytes=previous['bytes'],status=200,reused_original=True,verified_sha256=True)
            return row
        try:
            with requests.get(url,headers={'User-Agent':UA},timeout=(20,180),stream=True) as r:
                row.update(status=r.status_code,content_type=r.headers.get('Content-Type'),etag=r.headers.get('ETag'))
                r.raise_for_status()
                body=bytearray()
                for block in r.iter_content(1024**2):
                    body.extend(block)
                    if len(body)>120*1024**2: raise ValueError('Shard size cap exceeded')
                raw=RAW/f'universe_hf_{run}_{Path(source).name}'
                with raw.open('xb') as f:f.write(body)
                raw.chmod(stat.S_IREAD)
                digest=hashlib.sha256(body).hexdigest()
                row.update(raw_path=str(raw),bytes=len(body),sha256=digest,verified_sha256=(digest==expected),reused_original=False)
                if digest!=expected:row['error']='LFS content hash mismatch; do not use'
        except Exception as e:row['error']=f'{type(e).__name__}: {e}'
        return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for row in pool.map(one,entries):
            rows.append(row)
            manifest.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
            print(json.dumps({k:row.get(k) for k in ['source_path','status','bytes','verified_sha256','error']},ensure_ascii=False),flush=True)
    print(str(manifest),flush=True)
    if len(rows)!=20 or not all(r.get('verified_sha256') for r in rows):raise SystemExit('INCOMPLETE or invalid shards')

if __name__=='__main__':main()
