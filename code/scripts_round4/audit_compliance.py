"""Compliance audit for the audited revision against the nine writing requirements.

Technical exceptions are declared here rather than hidden: SEC form identifiers, the
language tag in the front matter, and the name of the official EDGAR interface. Nothing
else is exempt.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BODY_SRC = ROOT / 'manuscript/manuscript.md'
text = BODY_SRC.read_text(encoding='utf-8')
body = text.split('# References')[0]
abstract = body.split('# Abstract')[1].split('**Keywords')[0].strip()
FAIL: list[str] = []
report: dict[str, object] = {}

HYPHEN_ALLOWED = {
    '10-K', '10-KT', '10-Q', 'en-US', 'original-accession',
}
hyphens = sorted(set(re.findall(r'\b[A-Za-z0-9]+-[A-Za-z0-9]+(?:/[A-Za-z]+)?\b', body)))
# Numeric year spans and the frozen table labels of the input data are not prose
# compounds, so they are separated from the words that the rule governs.
numeric = [h for h in hyphens if re.fullmatch(r'\d{4}-\d{4}|t-\d+', h)]
wordish = [h for h in hyphens if h not in numeric]
unexpected = [h for h in wordish if h not in HYPHEN_ALLOWED]
report['hyphenated_terms'] = hyphens
report['year_spans_and_labels'] = numeric
report['hyphen_exceptions'] = sorted(set(wordish) & HYPHEN_ALLOWED)
report['hyphen_unexpected'] = unexpected

SOFT = ['need not', 'does not', 'do not', 'did not', 'cannot', 'can not', 'is not',
        'are not', 'was not', 'were not', 'never', 'neither', 'rather than', 'no claim',
        'not evidence', 'no new', 'no same', 'no mature', 'not available', 'unavailable']
hits = {p: len(re.findall(re.escape(p), body, re.I)) for p in SOFT}
report['defensive_phrases'] = {k: v for k, v in hits.items() if v}
report['abstract_negations'] = re.findall(r'\b(not|no|never|cannot|without|nor)\b',
                                          abstract, re.I)

report['em_dash_body'] = body.count('\u2014')
report['en_dash_body'] = body.count('\u2013')
report['minus_sign_body'] = body.count('\u2212')

PROCESS = ['this revision', 'in this revision', 'reviewer', 'round one', 'round two',
           'we now', 'as noted above', 'the remainder of this paper', 'revision round',
           'pending', 'manuscript was', 'editor']
found = [p for p in PROCESS if p in body.lower()]
report['process_language'] = found

journal = re.findall(r'Journal of [A-Z][A-Za-z ]+', body)
report['journal_names_body'] = journal

order = []
for match in re.finditer(r'\[(\d+(?:, \d+)*)\]', body):
    for part in match.group(1).split(','):
        value = int(part.strip())
        if value not in order:
            order.append(value)
report['citation_first_order'] = order

table_mentions, figure_mentions = [], []
for match in re.finditer(r'(Table|Figure) (\d+)', body):
    kind, number = match.group(1), int(match.group(2))
    is_caption = body[match.start() - 1:match.start()] == '\n' and body[match.end()] == '.'
    if is_caption:
        continue
    target = table_mentions if kind == 'Table' else figure_mentions
    if number not in target:
        target.append(number)
report['table_mentions'] = table_mentions
report['figure_mentions'] = figure_mentions

AI = ('OpenAI Codex was used only for limited Python code assistance and English language '
      'polishing. All substantive research tasks, including study design, data collection '
      'and processing, analysis, interpretation, and manuscript preparation, were performed '
      'by the authors. AI did not generate or alter data or determine conclusions, and the '
      'authors take full responsibility for the manuscript.')
report['ai_statement_verbatim'] = AI in body

PREVIEW = ['this paper is organized', 'the paper proceeds', 'the remainder of this',
           'is structured as follows', 'we organize the paper']
report['structure_previews'] = [p for p in PREVIEW if p in body.lower()]

report['word_count'] = len(re.findall(r"\b[\w']+\b", body))
report['abstract_words'] = len(re.findall(r"\b[\w']+\b", abstract))
report['quantified_claims'] = len(re.findall(r'\d+\.\d+', body))
report['figures_embedded'] = len(re.findall(r'^Figure \d+\.', body, re.M))

if unexpected:
    FAIL.append('unexpected hyphenated terms: ' + ', '.join(unexpected))
if report['em_dash_body'] or report['en_dash_body'] or report['minus_sign_body']:
    FAIL.append('dash character in body')
if found:
    FAIL.append('process language: ' + ', '.join(found))
if journal:
    FAIL.append('journal name in body: ' + ', '.join(journal))
if order != sorted(order):
    FAIL.append('citation order not ascending by first appearance')
if table_mentions != list(range(1, 7)):
    FAIL.append('table mention order: ' + str(table_mentions))
if figure_mentions != list(range(1, 6)):
    FAIL.append('figure mention order: ' + str(figure_mentions))
for n in range(1, 7):
    if len(re.findall(rf'^Table {n}\.', body, re.M)) != 1:
        FAIL.append(f'Table {n} caption count wrong')
for n in range(1, 6):
    if len(re.findall(rf'^Figure {n}\.', body, re.M)) != 1:
        FAIL.append(f'Figure {n} caption count wrong')
if AI not in body:
    FAIL.append('AI statement is not the required verbatim text')
if report['structure_previews']:
    FAIL.append('structure preview present')
if not 150 <= report['abstract_words'] <= 200:
    FAIL.append(f"abstract is {report['abstract_words']} words")
if report['abstract_negations']:
    FAIL.append('abstract contains negated phrasing: ' + str(report['abstract_negations']))

report['failures'] = FAIL
(ROOT / 'results/compliance_audit.json').write_text(
    json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(report, indent=2, ensure_ascii=False))
if FAIL:
    raise SystemExit('compliance failures: ' + '; '.join(FAIL))
