"""Small, sequential, transparent HTTP availability probe. No bulk collection.

Raw responses are created with exclusive mode under the authorized E: raw folder.
Every run uses new timestamp/UUID names; pre-existing raw files are never modified.
No credentials, fabricated contact address, or access-control workarounds are used.
Usage: python corporate_probe.py URL [URL ...]
"""
import argparse
import hashlib
import json
import stat
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

RAW = Path('<archived-record-root>/...')
ROOT = Path(__file__).resolve().parents[1]
UA = 'Codex public-data feasibility audit/1.0 (one-off access test; no bulk collection)'
MAX_BYTES = 25 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('urls', nargs='+')
    args = parser.parse_args()
    if len(args.urls) > 12:
        parser.error('At most 12 small requests per probe')
    RAW.mkdir(parents=True, exist_ok=True)
    out = ROOT / 'results'
    out.mkdir(parents=True, exist_ok=True)
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    rows = []
    for i, url in enumerate(args.urls):
        entry = {'url': url, 'request_utc': datetime.now(timezone.utc).isoformat(),
                 'user_agent': UA, 'used_authentication': False}
        try:
            with requests.get(url, headers={'User-Agent': UA}, timeout=35, stream=True) as response:
                body = bytearray()
                for block in response.iter_content(65536):
                    body.extend(block)
                    if len(body) > MAX_BYTES:
                        raise ValueError('Small-sample limit exceeded; response not saved')
                filename = RAW / f'probe_{run}_{i:02d}.bin'
                with filename.open('xb') as handle:
                    handle.write(body)
                filename.chmod(stat.S_IREAD)
                entry.update(status=response.status_code, final_url=response.url,
                             content_type=response.headers.get('Content-Type'), bytes=len(body),
                             raw_path=str(filename), sha256=hashlib.sha256(body).hexdigest(),
                             response_headers={k: response.headers[k] for k in ('Last-Modified','ETag','Content-Disposition') if k in response.headers})
        except Exception as exc:
            entry['error'] = f'{type(exc).__name__}: {exc}'
        rows.append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if i + 1 < len(args.urls):
            time.sleep(1.1)
    manifest = out / f'corporate_access_manifest_{run}.json'
    manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'MANIFEST={manifest}', flush=True)


if __name__ == '__main__':
    main()
