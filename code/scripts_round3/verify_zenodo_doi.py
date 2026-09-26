"""Verify a Zenodo DOI and resolve its concept DOI before it is written into the paper."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HEADERS = {'User-Agent': 'dsh-agent (doi verification)'}
DOI = sys.argv[1] if len(sys.argv) > 1 else '10.5281/zenodo.22977542'


def fetch(url: str):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


record = fetch('https://zenodo.org/api/records/' + DOI.split('zenodo.')[-1])
meta = record.get('metadata', {})
summary = {
    'doi': record.get('doi'),
    'concept_doi': record.get('conceptdoi'),
    'concept_recid': record.get('conceptrecid'),
    'title': meta.get('title'),
    'version': meta.get('version'),
    'publication_date': meta.get('publication_date'),
    'resource_type': (meta.get('resource_type') or {}).get('type'),
    'license': (meta.get('license') or {}).get('id'),
    'creators': [c.get('name') for c in meta.get('creators', [])],
    'related_identifiers': [i.get('identifier') for i in meta.get('related_identifiers', [])],
    'files': [f.get('key') for f in record.get('files', [])],
    'file_count': len(record.get('files', [])),
    'total_bytes': sum(f.get('size', 0) for f in record.get('files', [])),
    'html': record.get('links', {}).get('self_html'),
}
print(json.dumps(summary, indent=2, ensure_ascii=False))
Path('revision_20260923_jrmv/results/zenodo_doi_record.json').write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')

# Cross check the concept DOI resolves to the same record family.
if summary['concept_doi']:
    concept = fetch('https://zenodo.org/api/records/' + str(summary['concept_recid']))
    cmeta = concept.get('metadata', {})
    print('\nconcept record:', concept.get('doi'), '|', cmeta.get('title'))
    print('concept points at latest version:',
          concept.get('links', {}).get('latest_html'))
