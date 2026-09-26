"""Assemble the revised main manuscript: tables from frozen outputs, then compliance QA.

The script rebuilds every table from frozen CSVs, substitutes the table
placeholders in the template, normalises typography, and then fails loudly on
any violation of the manuscript conventions that apply to this revision.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
SOURCE_ROUND = BASE / 'revision_20260922_round2'
OLD = BASE / 'revision_20260922'
OUT = ROOT / 'manuscript'
RESULTS = ROOT / 'results'
OUT.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)
E = SOURCE_ROUND / 'results/evaluation_diagnostics'
D = SOURCE_ROUND / 'results/development_controls'
SRC: dict[str, str] = {}
FAIL: list[str] = []


def read(path: Path) -> pd.DataFrame:
    SRC[str(path.relative_to(BASE))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path)


def table(head, rows) -> str:
    lines = ['| ' + ' | '.join(head) + ' |',
             '| ' + ' | '.join(['---'] * len(head)) + ' |']
    for r in rows:
        lines.append('| ' + ' | '.join(str(c) for c in r) + ' |')
    return '\n'.join(lines)


def block(b: str) -> str:
    return b.replace('_', '-')


def num(x, fmt='{:.3f}') -> str:
    return fmt.format(x).replace('\u2212', '-')


# ---------------------------------------------------------------- tables
flow = read(BASE / 'results/cohort_flow.csv')
T1 = table(['Sequential eligibility stage', 'Windows', 'CIKs', 'Positive windows'],
           [[x.stage, f'{x.rows:,}', f'{x.ciks:,}', str(x.positive_windows)]
            for x in flow.itertuples()])

four = read(E / 'four_cell_decomposition_unrounded.csv')
g = four.query("model=='LGBM' and metric=='average_precision'")
T2 = table(['Test block', 'AA', 'AB', 'BA', 'BB', 'I', 'F', 'J', 'Total'], [
    [block(x.block)] + [num(getattr(x, c) * 100) for c in
                        ['AA', 'AB', 'BA', 'BB', 'input_AB_minus_AA',
                         'fit_BA_minus_AA', 'interaction', 'total_BB_minus_AA']]
    for x in g.itertuples()])

ex = read(E / 'version_exposure_summary.csv')
rows = []
for (dom, label), s in ex.loc[ex.domain != 'full_cohort'].groupby(['domain', 'label'], sort=True):
    cells = []
    for group in ['no_later_bundle', 'later_without_raw_change', 'later_with_raw_change']:
        z = s.loc[s.exposure_group == group].iloc[0]
        cells.append(f'{z.raw_n:,} ({z.within_label_weighted_fraction * 100:.1f}%)')
    rows.append([block(dom), str(label)] + cells)
T3 = table(['Test block', 'Event', 'No later bundle', 'Later unchanged', 'Later changed'], rows)

fit = read(SOURCE_ROUND / 'results/fit_date/fit_date_comparisons.csv')
cov = read(SOURCE_ROUND / 'results/fit_date/fit_date_coverage.csv')
rows = []
for x in fit.query("model=='LGBM' and metric=='average_precision'").itertuples():
    z = cov.loc[cov.block == x.block].iloc[0]
    rows.append([block(x.block)] +
                [num(getattr(x, c) * 100) for c in
                 ['original_A_train_A_score', 'fit_date_train_A_score',
                  'latest_B_train_A_score']] +
                [f'{z.latest_not_available_at_fit_n} / {z.n_train:,}',
                 f'{z.latest_not_available_at_fit_weighted_percent:.3f}%'])
T4 = table(['Test block', 'A fit', 'As of fit date', 'Latest later version fit',
            'Late records / development N', 'Late weight'], rows)

cpi = read(D / 'CPI_domain_diagonal.csv').query("model=='LGBM'")
labels = {'full_train_full_test': 'Full / Full',
          'full_train_size_test': 'Full / Size',
          'size_train_size_test': 'Size / Size'}
rows = []
for b in sorted(cpi.block.unique()):
    for exp in labels:
        s = cpi.loc[(cpi.block == b) & (cpi.experiment == exp)]
        a = s.loc[s.train_version == 'A'].iloc[0]
        v = s.loc[s.train_version == 'B'].iloc[0]
        rows.append([block(b), labels[exp], f'{int(a.n)} / {int(a.positive_windows)}',
                     num(a.weighted_prevalence * 100),
                     num(a.average_precision * 100),
                     num(v.average_precision * 100),
                     num((v.average_precision - a.average_precision) * 100, '{:+.3f}')])
T5 = table(['Test block', 'Develop / Evaluate', 'N / positives', 'Event %',
            'AA %', 'BB %', 'Difference (pp)'], rows)

scale = read(SOURCE_ROUND / 'results/scale_only/four_cell_differences.csv')
disputed = read(OLD / 'results/corrected_models_v2/four_cell_differences.csv')
rows = []
for b in sorted(g.block.unique()):
    orig = g.loc[g.block == b].iloc[0]
    for name, s, exper in [('Unadjusted', four, None),
                           ('Scale supported', scale, 'source_corrected_tuned'),
                           ('Scale plus disputed signs', disputed, 'source_corrected_tuned')]:
        if exper is None:
            z = orig
            total = z.total_BB_minus_AA
        else:
            z = s.loc[(s.block == b) & (s.model == 'LGBM') &
                      (s.metric == 'average_precision') &
                      (s.experiment == exper)].iloc[0]
            total = z.total_refit_difference
        rows.append([block(b), name, num(z.AA * 100), num(z.BB * 100),
                     num(total * 100, '{:+.3f}')])
T6 = table(['Test block', 'Input scenario', 'AA %', 'BB %', 'Difference (pp)'], rows)

TABLES = {'TABLE_1': T1, 'TABLE_2': T2,
          'TABLE_3': T5,   # size domain separation
          'TABLE_4': T3,   # later version exposure
          'TABLE_5': T4,   # fit date disclosure rule
          'TABLE_6': T6}

text = (OUT / 'main_template.md').read_text(encoding='utf-8')
for key, value in TABLES.items():
    text = text.replace('{{' + key + '}}', value)
if re.search(r'\{\{.*?\}\}', text):
    FAIL.append('unsubstituted placeholder: ' + str(re.findall(r'\{\{.*?\}\}', text)))

# ------------------------------------------------------- typography rules
text = text.replace('\u2212', '-')          # minus sign to hyphen
text = text.replace('\u2014', ', ')         # em dash removed
text = re.sub(r'(?<=\d)\u2013(?=\d)', '-', text)   # numeric en dash range
text = text.replace('\u2013', ', ')         # remaining en dash removed
text = re.sub(r'[ \t]{2,}', ' ', text)
text = re.sub(r' +([,.;:])', r'\1', text)

(OUT / 'manuscript.md').write_text(text, encoding='utf-8')

# ------------------------------------------------------------- citation order
keys_in_order: list[str] = []
for m in re.finditer(r'@([A-Za-z0-9_]+)', text):
    k = m.group(1)
    if k not in keys_in_order:
        keys_in_order.append(k)
number = {k: i + 1 for i, k in enumerate(keys_in_order)}


def rewrite_citation(match):
    body = match.group(1)
    numbers = []
    for part in body.split(';'):
        part = part.strip().lstrip('@')
        part = re.sub(r'^-', '', part)
        if part not in number:
            FAIL.append('citation key not in bibliography: ' + part)
            numbers.append('?')
        else:
            numbers.append(str(number[part]))
    numbers = sorted(numbers, key=lambda x: (x == '?', int(x) if x.isdigit() else 999))
    return '[' + ', '.join(numbers) + ']'


text = re.sub(r'\[([^\]]*@[^\]]*)\]', rewrite_citation, text)
if re.search(r'@[A-Za-z]', text):
    FAIL.append('unresolved citation key: ' + str(re.findall(r'@[A-Za-z0-9_]+', text)[:5]))

# ------------------------------------------------------------- references list
REFS = json.loads((OUT / 'references.json').read_text(encoding='utf-8'))
ref_lines = []
for k in keys_in_order:
    if k not in REFS:
        FAIL.append('missing reference entry: ' + k)
        continue
    ref_lines.append(f'{number[k]}. ' + re.sub(r'\s+', ' ', REFS[k]).strip())
unused = sorted(set(REFS) - set(keys_in_order))
if unused:
    FAIL.append('reference entry never cited: ' + str(unused))

text = text + '\n' + '\n'.join(ref_lines) + '\n'
(OUT / 'manuscript.md').write_text(text, encoding='utf-8')
(OUT / 'generated_tables.json').write_text(json.dumps(TABLES, indent=2), encoding='utf-8')
(OUT / 'display_sources.json').write_text(json.dumps(SRC, indent=2), encoding='utf-8')

# ----------------------------------------------------------------- QA gates
body_only = text.split('# References')[0]
if '\u2014' in text:
    FAIL.append('em dash present')
if '\u2013' in text:
    FAIL.append('en dash present')
if '\u2212' in text:
    FAIL.append('unicode minus present')
if '  ' in body_only:
    FAIL.append('double space in body')
for term in ['journal', 'Journal', 'JRMV', 'manuscript was', 'the authors revised',
             'in this revision', 'this revision', 'editor', 'Editor',
             'this paper is organized', 'the remainder of this paper',
             'as noted above', 'we now turn to', 'it is worth noting that',
             'cannot be overemphasized', 'it should be emphasized that',
             'the authors believe that this study']:
    if term in body_only:
        FAIL.append('disallowed term in body: ' + term)
if 'reviewer' in body_only:
    FAIL.append('review process language in body')

for n in range(1, 7):
    hits = len(re.findall(rf'^Table {n}\.', body_only, re.M))
    if hits != 1:
        FAIL.append(f'Table {n} caption count {hits}')
    if not re.search(rf'Table {n}(?!\.)', body_only.replace(f'Table {n}.', '')):
        FAIL.append(f'Table {n} never mentioned in text')
for n in range(1, 6):
    hits = len(re.findall(rf'^Figure {n}\.', body_only, re.M))
    if hits != 1:
        FAIL.append(f'Figure {n} caption count {hits}')
    if not re.search(rf'Figure {n}(?!\.)', body_only.replace(f'Figure {n}.', '')):
        FAIL.append(f'Figure {n} never mentioned in text')

first_table, first_figure, caption_position = [], [], {}
seen = set()
for m in re.finditer(r'(Table|Figure) (\d+)', body_only):
    kind, n = m.group(1), int(m.group(2))
    is_caption = body_only[max(0, m.start() - 1):m.start()] in ('\n', '') and \
        body_only[m.end():m.end() + 1] == '.'
    if is_caption:
        caption_position.setdefault((kind, n), m.start())
        continue
    if (kind, n) in seen:
        continue
    seen.add((kind, n))
    if kind == 'Table':
        first_table.append(n)
    else:
        first_figure.append(n)
if first_table != list(range(1, 7)):
    FAIL.append('table first mention order: ' + str(first_table))
if first_figure != list(range(1, 6)):
    FAIL.append('figure first mention order: ' + str(first_figure))
for n in range(1, 7):
    mention = body_only.find(f'Table {n}')
    cap = caption_position.get(('Table', n))
    if cap is not None and mention > cap:
        FAIL.append(f'Table {n} caption precedes its first mention')
for n in range(1, 6):
    mention = body_only.find(f'Figure {n}')
    cap = caption_position.get(('Figure', n))
    if cap is not None and mention > cap:
        FAIL.append(f'Figure {n} caption precedes its first mention')

seen: set[int] = set()
running_max = 0
for m in re.finditer(r'\[([\d, ]+)\]', body_only):
    for part in m.group(1).split(','):
        n = int(part.strip())
        if n in seen:
            continue
        if n <= running_max:
            FAIL.append(f'citation {n} first appears after citation {running_max}')
        seen.add(n)
        running_max = max(running_max, n)

words = len(re.findall(r"\b[\w']+\b", body_only))
summary = {
    'words_before_references': words,
    'citations': len(keys_in_order),
    'tables': len(re.findall(r'^Table \d+\.', body_only, re.M)),
    'figures': len(re.findall(r'^Figure \d+\.', body_only, re.M)),
    'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
    'failures': FAIL,
}
(RESULTS / 'manuscript_build.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
shutil.copy(OLD / 'manuscript/references.bib', OUT / 'references.bib')
print(json.dumps(summary, indent=2))
if FAIL:
    raise SystemExit('compliance failures: ' + '; '.join(FAIL))
# Keep a second copy whose citations remain as keys, for the author-date
# submission pack required by the publisher's reference style.
author_date = (OUT / 'main_template.md').read_text(encoding='utf-8')
for key, value in TABLES.items():
    author_date = author_date.replace('{{' + key + '}}', value)
author_date = author_date.replace('\u2212', '-')
author_date = author_date.replace('\u2014', ', ')
author_date = re.sub(r'(?<=\d)\u2013(?=\d)', '-', author_date)
author_date = author_date.replace('\u2013', ', ')
(OUT / 'manuscript_author_date.md').write_text(author_date, encoding='utf-8')
print('wrote manuscript_author_date.md (citation keys preserved)')
