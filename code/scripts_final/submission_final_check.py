"""Final verification of the submission package against the publisher's rules."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

SUB = Path('revision_20260923_jrmv/submission')
FAIL: list[str] = []
report: dict[str, object] = {}

main = SUB / 'pdf/main_manuscript_anonymised.pdf'
doc = pymupdf.open(str(main))
text = '\n'.join(doc[i].get_text() for i in range(doc.page_count))
report['main_pages'] = doc.page_count

for token in ['{{', '}}', '\\begin', '\\end', 'TODO', 'not found']:
    if token in text:
        FAIL.append(f'main PDF contains {token!r}')
# A citation key mark like "@key" would indicate unprocessed references; the
# corresponding author email is the only legitimate at sign in the file.
if re.search(r'@[A-Za-z]', text.replace('junjiezhang2024@shisu.edu.cn', '')):
    FAIL.append('main PDF contains an unprocessed citation key')

for label in ['Administrator', 'MLWork', 'scie_small_sample', 'Acknowledgement of author']:
    if label in text:
        FAIL.append(f'main PDF leaks {label!r}')

tables = [int(n) for n in re.findall(r'Table (\d+):', text)]
figures = [int(n) for n in re.findall(r'Figure (\d+):', text)]
report['table_captions'] = sorted(set(tables))
report['figure_captions'] = sorted(set(figures))
if sorted(set(tables)) != list(range(1, 7)):
    FAIL.append(f'table captions {sorted(set(tables))}')
if sorted(set(figures)) != list(range(1, 6)):
    FAIL.append(f'figure captions {sorted(set(figures))}')

for heading in ['Abstract', 'Keywords', 'Key messages', 'Table legends', 'Figure legends',
                'Declarations of Interest', 'Acknowledgements',
                'Use of artificial intelligence', 'References']:
    if heading not in text:
        FAIL.append(f'missing heading in main PDF: {heading}')

if not re.search(r'\([A-Z][A-Za-z\u2019.\- ]+ (?:et al\. )?\d{4}\)', text):
    FAIL.append('no author-date citations found')

title_text = '\n'.join(p.get_text() for p in pymupdf.open(str(SUB / 'pdf/title_page.pdf')))
for field in ['Corresponding author', 'Running head', 'Word count', 'Tables in the main text',
              'Figures in the main text']:
    if field not in title_text:
        FAIL.append(f'title page missing field: {field}')

fig_files = sorted((SUB / 'figures').glob('figure*'))
table_files = sorted((SUB / 'tables').glob('table*'))
report['figure_files'] = len(fig_files)
report['table_files'] = len(table_files)
if len(fig_files) != 10:
    FAIL.append(f'{len(fig_files)} editable figure files, expected 10')
if len(table_files) != 12:
    FAIL.append(f'{len(table_files)} editable table files, expected 12')

tex = (SUB / 'latex/financial_data_version_risk.tex').read_text(encoding='utf-8')
if '\\documentclass' not in tex or '\\end{document}' not in tex:
    FAIL.append('LaTeX source is incomplete')
if 'figures/' not in tex:
    FAIL.append('LaTeX source does not reference the figure folder')

report['failures'] = FAIL
Path('revision_20260923_jrmv/results/submission_final_check.json').write_text(
    json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
if FAIL:
    raise SystemExit('final checks failed: ' + '; '.join(FAIL))
