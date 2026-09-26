"""Small public metadata downloads: immutable originals on E, manifest on D."""
from __future__ import annotations
import argparse, hashlib, json, stat, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE=Path('<working-tree-root>/...')
RAW=Path('<archived-record-root>/...')
UA='Codex public-data feasibility audit/1.0 (one-off metadata access; no bulk SEC collection)'

def run(urls: list[str], max_mb: int=25):
    RAW.mkdir(parents=True, exist_ok=True)
    (BASE/'results').mkdir(parents=True, exist_ok=True)
    runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    rows=[]
    for i,url in enumerate(urls):
        row={'url':url,'request_utc':datetime.now(timezone.utc).isoformat(),'user_agent':UA,'authentication':False}
        try:
            with requests.get(url,headers={'User-Agent':UA},timeout=(15,90),stream=True) as response:
                row.update(status=response.status_code,final_url=response.url,content_type=response.headers.get('Content-Type'),etag=response.headers.get('ETag'),last_modified=response.headers.get('Last-Modified'))
                limit=max_mb*1024**2
                if int(response.headers.get('Content-Length') or 0)>limit:
                    row['error']='Content-Length exceeds configured size cap; no body downloaded'
                else:
                    data=bytearray()
                    for chunk in response.iter_content(1024*1024):
                        data.extend(chunk)
                        if len(data)>limit:
                            raise ValueError('response exceeds configured size cap')
                    path=RAW/f'universe_{runid}_{i:02d}.bin'
                    with path.open('xb') as f: f.write(data)
                    path.chmod(stat.S_IREAD)
                    row.update(raw_path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),read_only=not bool(path.stat().st_mode & stat.S_IWRITE))
        except Exception as exc:
            row['error']=f'{type(exc).__name__}: {exc}'
        rows.append(row)
        manifest=BASE/'results'/f'universe_access_manifest_{runid}.json'
        manifest.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
        time.sleep(1.1)
    print(str(manifest),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('urls',nargs='+')
    parser.add_argument('--max-mb',type=int,default=25)
    args=parser.parse_args()
    if len(args.urls)>12: raise ValueError('maximum 12 URLs per invocation')
    run(args.urls,args.max_mb)
