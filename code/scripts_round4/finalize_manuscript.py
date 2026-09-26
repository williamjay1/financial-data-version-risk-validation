"""Finalize the audited manuscript: rebuild the template from the source round, apply
the writing edits once, then replace the abstract with the length-compliant version.

Rebuilding from the previous round keeps the process deterministic: one pass over the
source text, so every edit applies to the same baseline and the result is reproducible.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import apply_writing_audit as audit

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
SOURCE = BASE / 'revision_20260923_jrmv/manuscript/main_template.md'
TEMPLATE = ROOT / 'manuscript/main_template.md'

ABSTRACT_OLD_START = 'Financial risk models are validated'
ABSTRACT_NEW = (
    'Financial risk models are validated on historical data whose values are revised after '
    'disclosure, so one accounting period can carry several recorded values. A train and '
    'test split leaves the version of each input open, which makes the result depend on a '
    'version rule that shapes model development and scoring alike. We develop a crossed '
    'version validation protocol that holds observation identities, outcome labels, design '
    'weights and initial missingness fixed while version selection varies separately at '
    'development and at scoring, separating substitution of scoring inputs, redevelopment '
    'of the fitted pipeline and selection of the evaluated population. Applied to 5,502 '
    'annual filing windows with 188 linked bankruptcy registry events, the protocol shows '
    'the reported difference and its sources diverging: the direct substitution contrast '
    'ran from -2.78 to +0.11 average precision points while redevelopment contributed '
    '+1.90 to +4.95 points. Development choices carried the larger influence, with a '
    'development domain change moving one version contrast from +2.85 to -16.01 points '
    'while the evaluation sample stayed fixed. Financial data versioning is a model '
    'validation and governance risk, and a validation report becomes reproducible once it '
    'records the input version rule alongside the extraction date.')


def main() -> None:
    shutil.copy2(SOURCE, TEMPLATE)
    audit.main()

    text = TEMPLATE.read_text(encoding='utf-8')
    head, _, rest = text.partition(ABSTRACT_OLD_START)
    abstract_end = rest.index('**Keywords:')
    tail = rest[abstract_end:]
    text = head + ABSTRACT_NEW + '\n\n' + tail
    TEMPLATE.write_text(text, encoding='utf-8', newline='\n')

    body = text.split('# References')[0]
    abstract = body.split('# Abstract')[1].split('**Keywords')[0].strip()
    words = len(abstract.split())
    report = {'abstract_words': words, 'in_range': 150 <= words <= 200,
              'template': str(TEMPLATE)}
    (ROOT / 'results/abstract_finalization.json').write_text(
        json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    if not report['in_range']:
        raise SystemExit(f'abstract is {words} words')


if __name__ == '__main__':
    main()
