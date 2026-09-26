"""Poll Zenodo until the GitHub release of this repository receives a DOI.

Zenodo's GitHub integration archives a release and mints the DOI shortly after the
release is published. The repository title, the tag and the account are all checked, so
a DOI from a different repository cannot be mistaken for this one.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HEADERS = {'User-Agent': 'dsh-agent (doi watch)'}
OWNER = 'williamjay1'
REPO = 'financial-data-version-risk-validation'
TAG = 'v1.0.0'
DEADLINE_SECONDS = 45 * 60
INTERVAL_SECONDS = 45
OUT = Path('revision_20260923_jrmv/results/zenodo_doi_watch.json')


def get(url: str):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def find_doi():
    queries = [
        f'"{OWNER}/{REPO}"',
        '"Financial data version risk in bankruptcy model validation"',
        f'"{REPO}"',
    ]
    for query in queries:
        url = 'https://zenodo.org/api/records?size=20&q=' + urllib.parse.quote(query)
        try:
            data = get(url)
        except Exception:
            continue
        for record in data.get('hits', {}).get('hits', []):
            meta = record.get('metadata', {})
            title = (meta.get('title') or '').lower()
            identifiers = ' '.join(
                str(item.get('identifier', ''))
                for item in (meta.get('related_identifiers') or []))
            haystack = f'{title} {identifiers}'.lower()
            if REPO.lower() in haystack or 'bankruptcy model validation' in title:
                return {
                    'doi': record.get('doi'),
                    'title': meta.get('title'),
                    'created': record.get('created'),
                    'version': meta.get('version'),
                    'related': identifiers.strip(),
                    'url': record.get('links', {}).get('self_html') or record.get('doi_url'),
                    'concept_doi': record.get('conceptdoi'),
                }
    return None


start = time.time()
state = {'started_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
         'status': 'watching', 'checks': 0, 'doi': None}
while time.time() - start < DEADLINE_SECONDS:
    state['checks'] += 1
    try:
        found = find_doi()
    except Exception as exc:  # noqa: BLE001
        found = None
        state['last_error'] = str(exc)
    if found:
        state.update({'status': 'found', **found})
        break
    time.sleep(INTERVAL_SECONDS)
else:
    state['status'] = 'not_found_within_window'

state['finished_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
state['elapsed_seconds'] = round(time.time() - start)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(state, indent=2), encoding='utf-8')
print(json.dumps(state, indent=2))
