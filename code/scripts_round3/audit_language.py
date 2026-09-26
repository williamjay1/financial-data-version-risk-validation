"""Audit the manuscript for defensive phrasing, negation and process language."""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path('revision_20260923_jrmv/manuscript/main_template.md')
text = SRC.read_text(encoding='utf-8')
body, _, refs = text.partition('# References')
lines = body.split('\n')

PATTERNS = {
    'negation (not/cannot/never)': r'\b(does not|do not|did not|cannot|can not|is not|are not|was not|were not|never|neither|nor|no [a-z]+)\b',
    'limitation words': r'\b(limit|limits|limited|limitation|boundary|boundaries|remain|remains|unknown|cannot be)\b',
    'deferral words': r'\b(beyond|further|future work|next|extend|extension|not claimed|no claim|not evidence|not a|rather than)\b',
    'process language': r'\b(we report|we describe|we now|in this revision|round|revision|reviewer|submission|as noted|we present|is organized|remainder of)\b',
    'hyphen use': r'\b[A-Za-z]+-[A-Za-z]+\b',
    'journals': r'\b(Journal of|JRMV|Risk Journals)\b',
}

results: dict[str, list[tuple[int, str]]] = {k: [] for k in PATTERNS}
for number, line in enumerate(lines, start=1):
    for name, pattern in PATTERNS.items():
        for match in re.finditer(pattern, line, re.I):
            results[name].append((number, match.group(0)))
            break

out = ['# Manuscript language audit', '',
       f'Source: {SRC}', f'Body lines: {len(lines)}', '']
for name, hits in results.items():
    out.append(f'## {name}: {len(hits)} lines')
    out.append('')
    for number, sample in hits[:60]:
        out.append(f'- line {number}: `{sample}`')
    out.append('')

abstract = body.split('# Abstract')[1].split('**Keywords')[0].strip()
out += ['## Abstract, verbatim', '', abstract, '',
        '## Abstract negation hits', '']
for match in re.finditer(r'\b(not|no|never|cannot|without|nor)\b', abstract, re.I):
    out.append(f'- `{abstract[max(0, match.start() - 60):match.end() + 60]}`')
Path('revision_20260923_jrmv/results/language_audit.md').write_text('\n'.join(out),
                                                                    encoding='utf-8')
print('\n'.join(out[:80]))
