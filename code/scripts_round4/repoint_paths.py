"""Repoint the copied build scripts at the audited revision round.

Only path constants change: the simulation inputs still come from the frozen round-two
results, while the manuscript, figures and outputs come from this round.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
SCRIPTS = ROOT / 'scripts'
DEV = BASE / 'revision_20260923_jrmv'
ROUND2 = BASE / 'revision_20260922_round2'

# script -> {search: replacement}
PATCHES: dict[str, dict[str, str]] = {
    'assemble_manuscript.py': {
        "SOURCE_ROUND = BASE / 'revision_20260922_round2'": "SOURCE_ROUND = BASE / 'revision_20260922_round2'",
        "OLD = BASE / 'revision_20260922'": "OLD = BASE / 'revision_20260923_jrmv'",
    },
    'build_submission_pack.py': {
        "MAN = ROOT / 'manuscript'": "MAN = ROOT / 'manuscript'",
        "FIGSRC = MAN / 'figures'": "FIGSRC = MAN / 'figures'",
        "ROOT / 'results/scale_only/four_cell_differences.csv'":
            "ROUND2 / 'results/scale_only/four_cell_differences.csv'",
        "ROOT.parent / 'revision_20260922/results/corrected_models_v2/four_cell_differences.csv'":
            "ROUND2 / 'results/corrected_models_v2/four_cell_differences.csv'",
    },
    'build_deliverables.py': {
        "SOURCE_ROUND = BASE / 'revision_20260922_round2'": "SOURCE_ROUND = BASE / 'revision_20260922_round2'",
    },
    'build_pdf_reading_copy.py': {},
    'build_title_page.py': {},
    'build_submission_supplement.py': {},
    'build_submission_readme.py': {},
    'submission_final_check.py': {},
    'build_repo_docs.py': {},
    'write_delivery_notes.py': {},
    'build_repo_stage.py': {},
    'build_repo_content.py': {},
    'verify_repo_push.py': {},
    'check_zenodo_doi.py': {},
    'build_figures_publication.py': {},
}

for name, mapping in PATCHES.items():
    path = SCRIPTS / name
    if not path.exists():
        continue
    text = path.read_text(encoding='utf-8')
    original = text
    for search, replacement in mapping.items():
        if search in text and search != replacement:
            text = text.replace(search, replacement)
    if 'ROUND2' in text and 'ROUND2 = ' not in text:
        anchor = 'ROOT = Path(__file__).resolve().parents[1]'
        if anchor in text:
            text = text.replace(
                anchor,
                anchor + "\nROUND2 = Path(__file__).resolve().parents[1].parent / "
                         "'revision_20260922_round2'", 1)
    if text != original:
        path.write_text(text, encoding='utf-8')
        print('patched', name)
    else:
        print('unchanged', name)
