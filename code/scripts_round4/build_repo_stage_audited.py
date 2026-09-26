"""Stage the audited revision for the reproducibility repository.

Round-one and round-two result trees are carried over unchanged from the previous stage
so that the published repository keeps one continuous history, while the manuscript,
figures, tables and documentation are replaced by the audited versions.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
STAGE = ROOT / 'repo_stage'
PREV = BASE / 'revision_20260923_jrmv/repo_stage'
MAN = ROOT / 'manuscript'
SUB = ROOT / 'submission'
DELIVERY = ROOT / 'delivery'
RESULTS = ROOT / 'results'

SKIP_SUFFIXES = {'.joblib'}
SKIP_NAMES = {'predictions.parquet', 'validation_predictions.parquet', 'split_audit.json',
              'fit_preprocessing_audit.json'}
SKIP_DIR_NAMES = {'__pycache__', 'staging', 'extracted', 'artifacts', 'deliverables',
                  'temp', 'package_failures', 'chrome-profile'}
TEXT_SUFFIXES = {'.json', '.md', '.csv', '.py', '.txt', '.jsonl', '.tex', '.cff',
                 '.gitignore', 'LICENSE'}
REDACTIONS = [
    (re.compile(r'[A-Za-z]:[\\/]AcademicData[\\/][^\s",;)\]\']*'), '<archived-record-root>/...'),
    (re.compile(r'[A-Za-z]:[\\/]MLWork[\\/][^\s",;)\]\']*'), '<working-tree-root>/...'),
    (re.compile(r'C:[\\/]Users[\\/][^\s",;)\]\']*'), '<local-path>'),
    (re.compile(r'\bE:[\\/]AcademicData\b'), '<archived-record-root>'),
    (re.compile(r'\bD:[\\/]MLWork\b'), '<working-tree-root>'),
]
report = {'copied': 0, 'skipped': 0, 'redacted': 0}


def copy_tree(source: Path, target: Path) -> None:
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
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_SUFFIXES:
            text = path.read_text(encoding='utf-8', errors='ignore')
            new = text
            for pattern, replacement in REDACTIONS:
                new = pattern.sub(replacement, new)
            if new != text:
                report['redacted'] += 1
            destination.write_text(new, encoding='utf-8', newline='\n')
        else:
            shutil.copy2(path, destination)
        report['copied'] += 1


if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE.mkdir(parents=True)

# Carry over the frozen data, scripts and result trees from the published stage.
for rel in ['code/datasets', 'code/datasets_round2', 'results/round1', 'results/round2']:
    source = PREV / rel
    if source.exists():
        copy_tree(source, STAGE / rel)

# New scripts for this revision round, plus the superseded ones for provenance.
copy_tree(BASE / 'scripts', STAGE / 'code/scripts')
copy_tree(BASE / 'revision_20260922/scripts', STAGE / 'code/scripts_round1')
copy_tree(BASE / 'revision_20260922_round2/scripts', STAGE / 'code/scripts_round2')
copy_tree(BASE / 'revision_20260923_jrmv/scripts', STAGE / 'code/scripts_round3')
copy_tree(ROOT / 'scripts', STAGE / 'code/scripts_round4')

# Documentation and results for the audited revision.
copy_tree(RESULTS, STAGE / 'results/round4')
for name, target in [
    (BASE / 'revision_20260922_round2/reproducibility/README.md', 'docs/reproducibility_readme.md'),
    (BASE / 'revision_20260922_round2/reproducibility/data_dictionary.md', 'docs/data_dictionary.md'),
    (BASE / 'revision_20260922_round2/reproducibility/environment.json', 'docs/environment.json'),
    (BASE / 'revision_20260922_round2/reproducibility/requirements-lock.txt', 'docs/requirements-lock.txt'),
    (BASE / 'revision_20260922_round2/reproducibility/reproduce.py', 'docs/reproduce.py'),
    (BASE / 'revision_20260922_round2/reproducibility/portable_validation.md', 'docs/portable_validation.md'),
    (ROOT / 'results/compliance_audit.json', 'docs/compliance_audit.json'),
    (ROOT / 'results/audit_edits.json', 'docs/audit_edits.json'),
    (ROOT / 'results/writing_audit_report.md', 'docs/writing_audit_report.md'),
    (ROOT / 'results/submission_final_check.json', 'docs/submission_final_check.json'),
    (SUB / 'requirement_checklist.json', 'docs/submission_requirement_checklist.json'),
    (BASE / 'revision_20260923_jrmv/results/zenodo_doi_record.json', 'docs/zenodo_doi_record.json'),
]:
    source = Path(name)
    if source.exists():
        destination = STAGE / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        report['copied'] += 1

# Manuscript, figures, tables and LaTeX source.
DEST_MAN = STAGE / 'manuscript'
shutil.rmtree(DEST_MAN, ignore_errors=True)
(DEST_MAN / 'figures').mkdir(parents=True)
(DEST_MAN / 'tables').mkdir(parents=True)
(DEST_MAN / 'latex').mkdir(parents=True)
for name, target in [
    (DELIVERY / 'Financial_Data_Version_Risk_Manuscript.pdf', 'manuscript.pdf'),
    (DELIVERY / 'Financial_Data_Version_Risk_Manuscript.docx', 'manuscript.docx'),
    (DELIVERY / 'Financial_Data_Version_Risk_Supplement.pdf', 'supplement.pdf'),
    (DELIVERY / 'Financial_Data_Version_Risk_Supplement.docx', 'supplement.docx'),
    (SUB / 'pdf/main_manuscript_anonymised.pdf', 'submission_main_text.pdf'),
    (SUB / 'pdf/title_page.pdf', 'submission_title_page.pdf'),
    (SUB / 'pdf/cover_letter.pdf', 'submission_cover_letter.pdf'),
    (SUB / 'pdf/supplementary_material.pdf', 'submission_supplementary.pdf'),
    (SUB / 'latex/financial_data_version_risk.tex', 'latex/submission_source.tex'),
    (MAN / 'main_template.md', 'source/main_template.md'),
    (MAN / 'manuscript.md', 'source/manuscript.md'),
    (SUB / 'front_matter.json', 'source/front_matter.json'),
]:
    source = Path(name)
    if source.exists():
        destination = DEST_MAN / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        report['copied'] += 1
for pattern, folder in [(SUB / 'figures', 'figures'), (MAN / 'figures', 'figures'),
                        (SUB / 'tables', 'tables')]:
    for path in sorted(pattern.glob('*')):
        if path.suffix in {'.csv', '.svg', '.pdf'} or pattern == SUB / 'tables':
            shutil.copy2(path, DEST_MAN / folder / path.name)
            report['copied'] += 1

print(json.dumps({**report,
                  'staged_files': sum(1 for p in STAGE.rglob('*') if p.is_file())},
                 indent=2))
