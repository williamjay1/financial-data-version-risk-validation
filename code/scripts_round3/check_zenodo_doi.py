"""Look up whether Zenodo has minted a DOI for the published GitHub release."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

HEADERS = {'User-Agent': 'dsh-agent (reproducibility check)'}


def get(url: str):
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return {'error': f'{type(exc).__name__}: {exc}'}


QUERIES = [
    'financial-data-version-risk-validation',
    'Financial data version risk in bankruptcy model validation',
    'williamjay1',
]
for query in QUERIES:
    url = ('https://zenodo.org/api/records?size=5&q=' +
           urllib.parse.quote(f'"{query}"'))
    data = get(url)
    print('=== query:', query)
    if 'error' in data:
        print('   ', data['error'])
        continue
    hits = data.get('hits', {})
    print('    total:', hits.get('total'))
    for record in hits.get('hits', [])[:5]:
        meta = record.get('metadata', {})
        print('   ', record.get('doi'), '|', meta.get('title', '')[:80],
              '|', record.get('created', '')[:10],
              '|', (meta.get('related_identifiers') or [{}])[0].get('identifier', '')) 
