"""Add the documentation, final manuscript materials and packaging to the repository stage."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
STAGE = ROOT / 'repo_stage'
ROUND2 = BASE / 'revision_20260922_round2'
DELIVERY = ROOT / 'delivery'
SUB = ROOT / 'submission'
MAN = ROOT / 'manuscript'
report = {'added': 0}

# The 23 MB CSV mirror of the universe frame is redundant with the parquet copy.
redundant = STAGE / 'code/datasets/universe_annual_filings_2010_2021.csv'
if redundant.exists():
    redundant.unlink()

for suffix in ['.joblib', '.zip']:
    for path in STAGE.rglob(f'*{suffix}'):
        path.unlink()

# --------------------------------------------------------------- manuscript
DEST_MAN = STAGE / 'manuscript'
(DEST_MAN / 'figures').mkdir(parents=True, exist_ok=True)
(DEST_MAN / 'tables').mkdir(parents=True, exist_ok=True)
(DEST_MAN / 'latex').mkdir(parents=True, exist_ok=True)

for name, target in [
    (DELIVERY / 'Financial_Data_Version_Risk_Manuscript.pdf', DEST_MAN / 'manuscript.pdf'),
    (DELIVERY / 'Financial_Data_Version_Risk_Manuscript.docx', DEST_MAN / 'manuscript.docx'),
    (DELIVERY / 'Financial_Data_Version_Risk_Supplement.pdf', DEST_MAN / 'supplement.pdf'),
    (DELIVERY / 'Financial_Data_Version_Risk_Supplement.docx', DEST_MAN / 'supplement.docx'),
    (SUB / 'pdf/main_manuscript_anonymised.pdf', DEST_MAN / 'submission_main_text.pdf'),
    (SUB / 'pdf/title_page.pdf', DEST_MAN / 'submission_title_page.pdf'),
    (SUB / 'pdf/cover_letter.pdf', DEST_MAN / 'submission_cover_letter.pdf'),
    (SUB / 'pdf/supplementary_material.pdf', DEST_MAN / 'submission_supplementary.pdf'),
    (SUB / 'latex/financial_data_version_risk.tex', DEST_MAN / 'latex/submission_source.tex'),
]:
    if name.exists():
        shutil.copy2(name, target)
        report['added'] += 1

for path in sorted((SUB / 'figures').glob('*')):
    shutil.copy2(path, DEST_MAN / 'figures' / path.name)
    report['added'] += 1
for path in sorted((SUB / 'tables').glob('*.csv')):
    shutil.copy2(path, DEST_MAN / 'tables' / path.name)
    report['added'] += 1
for path in sorted((MAN / 'figures').glob('*.svg')):
    shutil.copy2(path, DEST_MAN / 'figures' / path.name)
    report['added'] += 1

# ------------------------------------------------------------ code interface
DOCS = STAGE / 'docs'
DOCS.mkdir(exist_ok=True)
for name, target in [
    (ROUND2 / 'reproducibility/README.md', DOCS / 'reproducibility_readme.md'),
    (ROUND2 / 'reproducibility/data_dictionary.md', DOCS / 'data_dictionary.md'),
    (ROUND2 / 'reproducibility/environment.json', DOCS / 'environment.json'),
    (ROUND2 / 'reproducibility/requirements-lock.txt', DOCS / 'requirements-lock.txt'),
    (ROUND2 / 'reproducibility/reproduce.py', DOCS / 'reproduce.py'),
    (ROUND2 / 'reproducibility/portable_validation.json', DOCS / 'portable_validation.json'),
    (ROUND2 / 'reproducibility/portable_validation.md', DOCS / 'portable_validation.md'),
    (ROUND2 / 'results/final_revision_audit.json', DOCS / 'final_revision_audit.json'),
    (ROUND2 / 'results/final_revision_audit.md', DOCS / 'final_revision_audit.md'),
    (ROOT / 'results/figure_layout_audit.txt', DOCS / 'figure_layout_audit.txt'),
    (ROOT / 'results/manuscript_build.json', DOCS / 'manuscript_build.json'),
    (ROOT / 'results/pdf_qa.json', DOCS / 'pdf_qa.json'),
    (ROOT / 'results/submission_final_check.json', DOCS / 'submission_final_check.json'),
    (SUB / 'requirement_checklist.json', DOCS / 'submission_requirement_checklist.json'),
    (ROOT / 'results/submission_build.json', DOCS / 'submission_build.json'),
]:
    if name.exists():
        shutil.copy2(name, target)
        report['added'] += 1

for name in ['fixed_version_analysis.py']:
    source = ROUND2 / 'scripts' / name
    if source.exists():
        shutil.copy2(source, STAGE / 'code/scripts_round2' / name)

print(json.dumps({'added': report['added'],
                  'staged_files': sum(1 for _ in STAGE.rglob('*') if _.is_file())}, indent=2))
