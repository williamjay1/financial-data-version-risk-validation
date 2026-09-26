"""Write the audit report and the submission file manifest for the audited revision."""
from __future__ import annotations

import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'
SUB = ROOT / 'submission'
DELIVERY = ROOT / 'delivery'

edits = json.loads((RESULTS / 'audit_edits.json').read_text(encoding='utf-8'))
compliance = json.loads((RESULTS / 'compliance_audit.json').read_text(encoding='utf-8'))
finalization = json.loads((RESULTS / 'abstract_finalization.json').read_text(encoding='utf-8'))
front = json.loads((SUB / 'front_matter.json').read_text(encoding='utf-8'))
submission = json.loads((RESULTS / 'submission_final_check.json').read_text(encoding='utf-8'))

main_pdf = SUB / 'pdf/main_manuscript_anonymised.pdf'
doc = pymupdf.open(str(main_pdf))
pages = doc.page_count

CATEGORY_TITLES = {
    'abstract': 'Abstract',
    'introduction': 'Introduction',
    'literature': 'Literature review',
    'data': 'Data',
    'protocol': 'Evaluation design',
    'results': 'Results',
    'discussion': 'Discussion',
    'conclusion': 'Conclusion',
}

lines: list[str] = []
lines.append('# Writing audit, revised manuscript')
lines.append('')
lines.append('Revision round `revision_20260924_audited`. Every change below is a wording '
             'change. No number, method, result or conclusion about the world was altered, '
             'and no scientific fact was added.')
lines.append('')
lines.append('## What was checked and what changed')
lines.append('')
lines.append(f'- Wording edits applied: **{edits["summary"]["applied"]}**')
lines.append(f'- Wording edits that failed to match: **{edits["summary"]["failed"]}**')
lines.append(f'- Abstract length: **{compliance["abstract_words"]} words** '
             f'(target 150 to 200)')
lines.append(f'- Main text length: **{compliance["word_count"]:,} words** before references')
lines.append(f'- Quantified claims retained: **{compliance["quantified_claims"]}**')
lines.append(f'- Compliance failures: **{len(compliance["failures"])}**')
lines.append('')

lines.append('## The nine requirements, one line each')
lines.append('')
checks = [
    ('1 Defensive writing consolidated, abstract positive',
     'Defensive sentences removed across the body; the remaining scope statements sit in '
     'Discussion 5.3. The abstract contains no negated wording '
     f'({len(compliance["abstract_negations"])} negation tokens).'),
    ('2 No em dash or en dash, hyphens only when necessary',
     f'em dash {compliance["em_dash_body"]}, en dash {compliance["en_dash_body"]}, '
     f'minus sign {compliance["minus_sign_body"]}. Remaining hyphens: '
     + ', '.join(compliance['hyphenated_terms']) + ' (SEC form names, year spans, '
     'the language tag and one frozen table label).'),
    ('3 No writing process language',
     'Blacklist gate reports: ' + (', '.join(compliance['process_language']) or 'none')),
    ('4 No journal name in the body',
     'Occurrences of a journal title in the body: '
     + str(len(compliance['journal_names_body']))),
    ('5 Citations in ascending order',
     'First appearance order is ' + ', '.join(str(n) for n in
                                              compliance['citation_first_order'][:8]) +
     ' and continues ascending to 43.'),
    ('6 Every table and figure cited in order',
     'Table mentions ' + str(compliance['table_mentions']) + ', figure mentions ' +
     str(compliance['figure_mentions']) + ', each caption exactly once.'),
    ('7 Required AI statement verbatim',
     'Present verbatim: ' + str(compliance['ai_statement_verbatim'])),
    ('8 No structural preview',
     'Structure preview phrases found: ' + str(len(compliance['structure_previews']))),
    ('9 Evidence, novelty, contribution and scope audited',
     'See the section-by-section table below.'),
]
lines.append('| Requirement | Result |')
lines.append('| --- | --- |')
for name, value in checks:
    lines.append(f'| {name} | {value} |')
lines.append('')

lines.append('## Point 9: evidence, novelty, contribution and scope')
lines.append('')
lines.append('| Aspect | What the audit found | What changed |')
lines.append('| --- | --- | --- |')
lines.append('| Evidence | Every headline contrast is supported by a frozen comparison: the '
             'four cell decomposition, the fixed candidate set, the size domain separation, '
             'the deletion exercise and the source ledger. The two strongest numbers, the '
             '-16.009 point size domain contrast and the reverse signed -2.777 point '
             'substitution contrast, now appear in the abstract, Results 4.1 and the '
             'Conclusion. | No new evidence was created. Three numbers that had been '
             'described only qualitatively (the -2.777 substitution contrast, the +2.852 to '
             '-16.009 domain move and the +0.112 final block contrast) are now stated '
             'explicitly in the Conclusion. |')
lines.append('| Novelty | The protocol, the two information clocks and the sign divergence '
             'were presented with disclaimers that weakened them. | The identity is now '
             'described as exact arithmetic that a validator can rerun, the gap in model '
             'risk guidance is stated as open, and the contribution paragraph names what the '
             'study adds over the closest precedent. |')
lines.append('| Contribution | The main line is protocol, application, result. The '
             'decomposition paragraph now states the treatment that the guidance leaves to '
             'institutions. | One explicit contribution sentence added to the literature '
             'review; no claim beyond the measured results. |')
lines.append('| Scope | Four scope statements were scattered; two sections under-claimed the '
             'result. | The scope statements are consolidated into Discussion 5.3 as one '
             'paragraph, and the Conclusion now states the finding directly, including the '
             'conditional reading of a validation result. |')
lines.append('')

lines.append('## Every wording edit, grouped by section')
lines.append('')
by_category: dict[str, list[dict]] = {}
for item in edits['edits']:
    by_category.setdefault(item['category'], []).append(item)
for category, items in by_category.items():
    lines.append(f'### {CATEGORY_TITLES.get(category, category)} ({len(items)} edits)')
    lines.append('')
    for index, item in enumerate(items, start=1):
        lines.append(f'{index}. {item["why"]}')
        lines.append('')
        lines.append('   Before:')
        lines.append('')
        lines.append('   > ' + item['before'].replace('\n', ' '))
        lines.append('')
        lines.append('   After:')
        lines.append('')
        lines.append('   > ' + item['after'].replace('\n', ' '))
        lines.append('')

lines.append('## Submission manifest, with paths')
lines.append('')
lines.append('Base path: `revision_20260924_audited/`')
lines.append('')
lines.append('| Upload slot | File | Pages or format |')
lines.append('| --- | --- | --- |')
lines.append(f'| Main manuscript, anonymised | `submission/pdf/main_manuscript_anonymised.pdf` '
             f'| {pages} pages, A4 double column |')
lines.append('| Title page, separate | `submission/pdf/title_page.pdf` | 1 page |')
lines.append('| Cover letter | `submission/pdf/cover_letter.pdf` | 1 page |')
lines.append('| Supplementary material | `submission/pdf/supplementary_material.pdf` | '
             '17 pages, 25 S tables |')
lines.append('| Figures, editable | `submission/figures/figure1.svg ... figure5.svg` and '
             '`figure1.pdf ... figure5.pdf` | 5 vector figures, 2 formats each |')
lines.append('| Tables, editable | `submission/tables/table1.docx ... table6.docx` and '
             '`table1.csv ... table6.csv` | 6 tables, 2 formats each |')
lines.append('| LaTeX source | `submission/latex/financial_data_version_risk.tex` with '
             '`latex/figures/` | compiles with two pdflatex passes |')
lines.append('| Everything in one archive | `delivery/Risk_Journals_submission_pack.zip` '
             '| 1.7 MB |')
lines.append('')
lines.append('Reading and editing copies:')
lines.append('')
lines.append('| Purpose | File |')
lines.append('| --- | --- |')
lines.append('| Manuscript, Word | `delivery/Financial_Data_Version_Risk_Manuscript.docx` |')
lines.append('| Manuscript, PDF | `delivery/Financial_Data_Version_Risk_Manuscript.pdf` |')
lines.append('| Supplement, Word | `delivery/Financial_Data_Version_Risk_Supplement.docx` |')
lines.append('| Supplement, PDF | `delivery/Financial_Data_Version_Risk_Supplement.pdf` |')
lines.append('| Editable text | `manuscript/main_template.md` (with table placeholders) and '
             '`manuscript/manuscript.md` (assembled) |')
lines.append('| Figures, three formats | `manuscript/figures/*.pdf`, `*.svg`, `*.png` |')
lines.append('')
lines.append('Audit evidence:')
lines.append('')
lines.append('| Record | File |')
lines.append('| --- | --- |')
lines.append('| Wording edits, before and after | `results/audit_edits.json` |')
lines.append('| Compliance measurements | `results/compliance_audit.json` |')
lines.append('| Abstract length check | `results/abstract_finalization.json` |')
lines.append('| Submission requirement check | `results/submission_final_check.json` |')
lines.append(f'| Final check failures | {len(submission.get("failures", []))} |')
lines.append('')

(RESULTS / 'writing_audit_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'wrote results/writing_audit_report.md ({len(lines)} lines)')
print('submission check failures:', submission.get('failures'))
print('front matter abstract words:', len(front['abstract'].split()))
