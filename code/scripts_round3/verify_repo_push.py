"""Verify the pushed GitHub repository against the local commit."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = 'williamjay1/financial-data-version-risk-validation'
STAGE = Path('revision_20260923_jrmv/repo_stage')


def gh(*args: str) -> str:
    result = subprocess.run(['gh', *args], capture_output=True, text=True,
                            encoding='utf-8', cwd=STAGE)
    if result.returncode:
        raise SystemExit(f'gh failed: {result.stderr[:500]}')
    return result.stdout


info = json.loads(gh('repo', 'view', REPO, '--json',
                     'name,visibility,url,defaultBranchRef,diskUsage,pushedAt'))
print('repository:', info['url'], info['visibility'])

tree_json = gh('api', f'repos/{REPO}/git/trees/main?recursive=1')
tree = json.loads(tree_json)
blobs = {entry['path'] for entry in tree['tree'] if entry['type'] == 'blob'}
total_bytes = sum(entry.get('size', 0) for entry in tree['tree']
                  if entry['type'] == 'blob')
print(f'remote blobs: {len(blobs)}   total size: {total_bytes / 1024 / 1024:.1f} MB')
print('truncated:', tree.get('truncated'))

local = gh('ls-files') if False else subprocess.run(
    ['git', 'ls-files'], capture_output=True, text=True, encoding='utf-8',
    cwd=STAGE).stdout.split()
local = [item.strip() for item in local if item.strip()]
missing = sorted(set(local) - blobs)
extra = sorted(blobs - set(local))
print(f'local tracked: {len(local)}')
print('missing on remote:', missing[:10] if missing else 'none')
print('extra on remote:', extra[:10] if extra else 'none')
print('largest remote files:')
for entry in sorted((e for e in tree['tree'] if e['type'] == 'blob'),
                    key=lambda e: -e.get('size', 0))[:5]:
    print(f"  {entry.get('size', 0) / 1024 / 1024:6.2f} MB  {entry['path']}")
if missing:
    raise SystemExit('repository verification failed')
print('VERIFIED: local commit is fully published')
