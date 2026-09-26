"""Assemble the public reproducibility repository staging tree.

The staging tree is built from the frozen artefacts only: no raw downloaded SEC
records, no local cache, no transient packaging zips. Archived records outside the
repository are redacted from the small number of lineage files that point at them.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
STAGE = ROOT / 'repo_stage'
RESULTS = ROOT / 'results'

SKIP_SUFFIXES = {'.joblib'}
SKIP_NAMES = {'predictions.parquet', 'validation_predictions.parquet',
              'split_audit.json', 'fit_preprocessing_audit.json'}
SKIP_DIR_NAMES = {'__pycache__', 'staging', 'extracted', 'artifacts', 'deliverables',
                  'temp', 'package_failures', 'chrome-profile'}
TEXT_SUFFIXES = {'.json', '.md', '.csv', '.py', '.txt', '.jsonl', '.tex'}
REDACTIONS = [
    # Local working-tree roots and archived raw-record roots are replaced by
    # portable placeholders so that no external machine path is published.
    (re.compile(r'[A-Za-z]:[\\/]AcademicData[\\/][^\s",;)\]\']*'),
     '<archived-record-root>/...'),
    (re.compile(r'[A-Za-z]:[\\/]MLWork[\\/][^\s",;)\]\']*'),
     '<working-tree-root>/...'),
    (re.compile(r'C:[\\/]Users[\\/][^\s",;)\]\']*'), '<local-path>'),
    (re.compile(r'\bE:[\\/]AcademicData\b'), '<archived-record-root>'),
    (re.compile(r'\bD:[\\/]MLWork\b'), '<working-tree-root>'),
]
report = {'copied': 0, 'bytes': 0, 'skipped': 0, 'redacted': []}


def copy_tree(source: Path, target: Path, root: Path) -> None:
    for path in sorted(source.rglob('*')):
        rel = path.relative_to(source)
        if any(part in SKIP_DIR_NAMES for part in rel.parts[:-1]):
            report['skipped'] += 1
            continue
        if path.is_dir():
            continue
        if path.suffix in SKIP_SUFFIXES or path.name in SKIP_NAMES:
            report['skipped'] += 1
            continue
        if path.stat().st_size > 90 * 1024 * 1024:
            report['skipped'] += 1
            continue
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in TEXT_SUFFIXES:
            text = path.read_text(encoding='utf-8', errors='ignore')
            new = text
            for pattern, replacement in REDACTIONS:
                new = pattern.sub(replacement, new)
            if new != text:
                report['redacted'].append(str(destination.relative_to(root)))
            destination.write_text(new, encoding='utf-8', newline='\n')
        else:
            shutil.copy2(path, destination)
        report['copied'] += 1
        report['bytes'] += destination.stat().st_size


if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE.mkdir(parents=True)

PLAN = {
    'code/datasets': [BASE / 'datasets'],
    'code/datasets_round2': [ROOT.parent / 'revision_20260922_round2/datasets'],
    'code/scripts': [BASE / 'scripts'],
    'code/scripts_round1': [ROOT.parent / 'revision_20260922/scripts'],
    'code/scripts_round2': [ROOT.parent / 'revision_20260922_round2/scripts'],
    'code/scripts_final': [ROOT / 'scripts'],
    'results/round1': [BASE / 'results'],
    'results/round2': [ROOT.parent / 'revision_20260922_round2/results'],
    'results/final': [RESULTS],
}
for target_rel, sources in PLAN.items():
    for source in sources:
        if not source.exists():
            print('missing source:', source)
            continue
        copy_tree(source, STAGE / target_rel, STAGE)

print(json.dumps({k: (v if k != 'redacted' else len(v)) for k, v in report.items()},
                 indent=2))
(STAGE / '_stage_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
