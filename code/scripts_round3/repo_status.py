"""Report the final GitHub repository state in a PowerShell-safe way."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = 'williamjay1/financial-data-version-risk-validation'
STAGE = Path('revision_20260923_jrmv/repo_stage')


def gh_json(*args: str):
    result = subprocess.run(['gh', *args], capture_output=True, text=True,
                            encoding='utf-8', cwd=STAGE)
    if result.returncode:
        return {'error': result.stderr.strip()[:300]}
    return json.loads(result.stdout)


meta = gh_json('api', f'repos/{REPO}')
topics = gh_json('api', f'repos/{REPO}/topics', '-H', 'Accept: application/vnd.github+json')
tree = gh_json('api', f'repos/{REPO}/git/trees/main?recursive=1')
blobs = [e for e in tree.get('tree', []) if e['type'] == 'blob']

print('url        :', meta.get('html_url'))
print('visibility :', meta.get('visibility'))
print('license    :', (meta.get('license') or {}).get('spdx_id'))
print('topics     :', ', '.join(topics.get('names', [])))
print('size (KB)  :', meta.get('size'))
print('pushed at  :', meta.get('pushed_at'))
print('files      :', len(blobs))
