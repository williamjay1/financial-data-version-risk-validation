"""Download a bounded set of primary-source documents; keep original bytes immutable."""
import hashlib
import json
import os
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = Path('<archived-record-root>/...')
SOURCES = {
    'correia_2025_review.pdf': 'https://researchonline.lse.ac.uk/id/eprint/128340/3/Accounting_and_corporate_failure_the_evolving_role_of_accounting_information_in_bankruptcy_prediction.pdf',
    'sec_api_documentation.html': 'https://www.sec.gov/search-filings/edgar-application-programming-interfaces',
    'nyfed_call_report_readme.txt': 'https://www.newyorkfed.org/medialibrary/media/research/banking_research/balance-sheets-income-statements/README',
}

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    rows = []
    for name, url in SOURCES.items():
        row = {'url': url, 'retrieved_utc': datetime.now(timezone.utc).isoformat()}
        try:
            response = requests.get(url, timeout=45, headers={'User-Agent': 'Academic research source audit/1.0'}, stream=True)
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 15 * 1024 * 1024:
                    raise ValueError('Document exceeds bounded download size')
            path = RAW / f'{run}_{name}'
            with path.open('xb') as output:
                output.write(body)
            os.chmod(path, stat.S_IREAD)
            row.update(status=response.status_code, final_url=response.url, raw_path=str(path),
                       content_type=response.headers.get('Content-Type'), bytes=len(body),
                       sha256=hashlib.sha256(body).hexdigest(), readonly=True)
            if name.endswith('.pdf'):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(path)
                    text = '\n\n'.join(f'PDF PAGE {i + 1}\n{page.extract_text()}' for i, page in enumerate(reader.pages))
                    derived = ROOT / 'results' / f'{run}_{name}.txt'
                    derived.write_text(text, encoding='utf-8')
                    row.update(pages=len(reader.pages), extracted_text=str(derived))
                except Exception as error:
                    row['text_extraction_error'] = repr(error)
        except Exception as error:
            row['error'] = repr(error)
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        time.sleep(1)
    (ROOT / 'results' / f'root_source_manifest_{run}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
