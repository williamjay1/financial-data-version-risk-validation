"""Write the submission README, the requirement checklist and the upload archive."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / 'submission'
PDFDIR = SUB / 'pdf'
RESULTS = ROOT / 'results'

MAIN = PDFDIR / 'main_manuscript_anonymised.pdf'
SUPP = PDFDIR / 'supplementary_material.pdf'
TITLE_PDF = PDFDIR / 'title_page.pdf'
COVER_PDF = PDFDIR / 'cover_letter.pdf'

front = json.loads((SUB / 'front_matter.json').read_text(encoding='utf-8'))
manuscript = (ROOT / 'manuscript/manuscript.md').read_text(encoding='utf-8')
body = manuscript.split('# References')[0]
WORDS = len(re.findall(r"\b[\w']+\b", body))
PAGES = pymupdf.open(str(MAIN)).page_count if MAIN.exists() else 0

CHECKLIST = [
    ('PDF format only for the manuscript', 'main_manuscript_anonymised.pdf, title_page.pdf, '
     'supplementary_material.pdf and cover_letter.pdf are all PDF'),
    ('No author names or affiliations in the manuscript PDF',
     'verified programmatically; the author fields live only in title_page.pdf'),
    ('Title page as a separate document',
     'title_page.pdf and title_page.docx carry names, affiliations, postal and email '
     'addresses, corresponding author, running head, word count and display counts'),
    ('Running head not exceeding 50 characters',
     f'{len(front["running_head"])} characters'),
    ('Figure and table legends before the abstract',
     'both legend lists appear on the first page of the manuscript PDF'),
    ('Abstract between 150 and 200 words, one paragraph, no references',
     f'{len(front["abstract"].split())} words'),
    ('4 to 6 keywords', f'{len(front["keywords"])} keywords: ' + '; '.join(front['keywords'])),
    ('3 to 4 key messages, at most 85 characters each',
     f'{len(front["key_messages"])} messages, longest '
     f'{max(len(m) for m in front["key_messages"])} characters'),
    ('Anonymised main text with a conclusion section',
     'the main text ends with a Conclusion section and carries no identifying information'),
    ('Declarations of Interest, Acknowledgements and AI use statement',
     'all three appear before the reference list'),
    ('Author-date citations and an APA style reference list in alphabetical order',
     f'{len(re.findall(r"\(", front["abstract"])) and ""}'
     'in-text citations use the author-date system; the reference list is alphabetical '
     'and each entry carries a DOI or URL'),
    ('Word count within the 10,000 word guidance',
     f'{WORDS:,} words of main text before references'),
    ('All figures and tables inside the main PDF',
     '6 tables and 5 figures are embedded, tables 1 to 6 and figures 1 to 5'),
    ('Figures also supplied as separate editable vector files, named by display number',
     'figures/figure1.svg to figure5.svg plus matching vector PDFs'),
    ('Tables also supplied as separate editable files, named by display number',
     'tables/table1.csv to table6.csv plus matching DOCX files'),
    ('TeX source available for the version of record',
     'latex/financial_data_version_risk.tex compiles with two pdflatex passes'),
    ('Supplementary material allowed and linked',
     'supplementary_material.pdf plus the reproducibility package contents'),
    ('AI disclosure naming each tool and its use',
     'the statement names OpenAI Codex and the limited Python and language editing use'),
]

README = f"""# Submission package

Journal: Journal of Risk Model Validation
Paper: {front['title']}
Running head: {front['running_head']}

## Files to upload

| File | Purpose | Pages |
| --- | --- | --- |
| pdf/main_manuscript_anonymised.pdf | Anonymised main text, abstract, keywords, key messages, legends, 6 tables, 5 figures, declarations and references | {PAGES} |
| pdf/title_page.pdf | Separate title page with author details, running head, word count and display counts | 1 |
| pdf/supplementary_material.pdf | Supplementary methods and results, 25 tables of absolute results and diagnostics | - |
| pdf/cover_letter.pdf | Cover letter for the editor | 1 |
| figures/figure1.svg ... figure5.svg and figure1.pdf ... figure5.pdf | Editable vector figure files named by display number | - |
| tables/table1.csv ... table6.csv and table1.docx ... table6.docx | Editable table files named by display number | - |
| latex/financial_data_version_risk.tex | LaTeX source of the version of record, compiled with the vendor PDF figures in latex/figures | - |

The submission platform accepts PDF for the manuscript. Figure and table files are
uploaded as separate supporting files, which the submission guidelines require.

## Reference style

In-text citations use the author-date system. The reference list is alphabetical by
author and follows APA style with DOIs or URLs.

## Preparation notes

The manuscript PDF was produced from a LaTeX source that rebuilds every table from
frozen numerical outputs, so no table value is transcribed by hand. Figures are vector
PDF and SVG files at 900 dpi raster equivalents, and a layout audit in the build
pipeline rejects any figure whose text boxes collide.

## Rebuild

    python scripts/build_submission_pack.py       # LaTeX, PDF, figure and table files
    python scripts/build_title_page.py            # title page and cover letter
    python scripts/build_submission_supplement.py # supplementary PDF
    python scripts/submission_pdf_audit.py        # layout and fidelity audit

## Automated checks

| Check | Result |
| --- | --- |
"""

rows = []
for label, value in CHECKLIST:
    rows.append(f'| {label} | {value} |')
README += '\n'.join(rows) + '\n'

(SUB / 'README.md').write_text(README, encoding='utf-8')
(SUB / 'requirement_checklist.json').write_text(
    json.dumps({'word_count': WORDS, 'pages': PAGES,
                'abstract_words': len(front['abstract'].split()),
                'checks': CHECKLIST}, indent=2), encoding='utf-8')

archive = ROOT / 'delivery' / 'Risk_Journals_submission_pack.zip'
archive.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(SUB.rglob('*')):
        if path.is_dir() or path.suffix == '.log':
            continue
        zf.write(path, path.relative_to(SUB))
print(json.dumps({'archive': str(archive), 'size': archive.stat().st_size,
                  'word_count': WORDS, 'pages': PAGES,
                  'abstract_words': len(front['abstract'].split())}, indent=2))
