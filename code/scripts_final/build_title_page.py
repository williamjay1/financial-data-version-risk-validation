"""Build the separate title page, the cover letter and the submission checklist.

The publisher requires the title page to be a separate document carrying the
author details, a running head of at most 50 characters, the word count and the
number of figures and tables. The main manuscript PDF must stay anonymised.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / 'manuscript'
SUB = ROOT / 'submission'
TEMP = ROOT / 'temp'
CHROME = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')

FRONT = json.loads((SUB / 'front_matter.json').read_text(encoding='utf-8'))
TITLE = FRONT['title']
RUNNING_HEAD = FRONT['running_head']
body = (MAN / 'manuscript.md').read_text(encoding='utf-8').split('# References')[0]
ABSTRACT_TEXT = FRONT['abstract']
WORD_COUNT = len(re.findall(r"\b[\w']+\b", body))

AUTHOR = FRONT['author']
AFFILIATIONS = FRONT['affiliations']

FIELD_ROWS = [
    ('Title', TITLE),
    ('Author', AUTHOR['name_en']),
    ('Author name in Chinese', AUTHOR['name_zh']),
    ('ORCID', AUTHOR['orcid']),
    ('Affiliation 1', AFFILIATIONS[0]),
    ('Affiliation 2', AFFILIATIONS[1]),
    ('Postal address', AUTHOR['postal_address']),
    ('Email', AUTHOR['email']),
    ('Corresponding author', AUTHOR['corresponding']),
    ('Running head (max 50 characters)', f'{RUNNING_HEAD} ({len(RUNNING_HEAD)} characters)'),
]
DISPLAY_ROWS = [
    ('Word count (main text, excluding references, tables and legends)', f'{WORD_COUNT:,}'),
    ('Tables in the main text', '6'),
    ('Figures in the main text', '5'),
    ('Abstract length', f'{len(ABSTRACT_TEXT.split())} words'),
    ('Keywords', '6'),
    ('Key messages', '4'),
]


def style(doc: Document) -> None:
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.95)
        section.right_margin = Inches(0.95)
    for style_obj in doc.styles:
        if style_obj.type in (1, 2):
            style_obj.font.name = 'Times New Roman'
            style_obj.font.color.rgb = RGBColor(0, 0, 0)
    if 'Normal' in doc.styles:
        doc.styles['Normal'].font.name = 'Times New Roman'
        doc.styles['Normal'].font.size = Pt(10.5)
        doc.styles['Normal'].paragraph_format.space_after = Pt(4)
        doc.styles['Normal'].paragraph_format.line_spacing = 1.06
    if 'Heading 1' in doc.styles:
        doc.styles['Heading 1'].font.size = Pt(14)
        doc.styles['Heading 1'].paragraph_format.space_after = Pt(6)
    if 'Heading 2' in doc.styles:
        doc.styles['Heading 2'].font.size = Pt(11)
        doc.styles['Heading 2'].paragraph_format.space_before = Pt(8)
        doc.styles['Heading 2'].paragraph_format.space_after = Pt(3)


def build_title_page() -> Path:
    doc = Document()
    style(doc)
    para = doc.add_paragraph()
    run = para.add_run('Title page')
    run.bold = True
    run.font.size = Pt(14)
    para.paragraph_format.space_after = Pt(4)
    doc.add_paragraph('Submitted to the Journal of Risk Model Validation').runs[0].italic = True
    table = doc.add_table(rows=len(FIELD_ROWS), cols=2)
    table.style = 'Table Grid'
    for row, (label, value) in zip(table.rows, FIELD_ROWS):
        row.cells[0].text = label
        row.cells[1].text = value
        for cell_index, cell in enumerate(row.cells):
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    run.font.size = Pt(9)
                    run.font.name = 'Times New Roman'
                    if cell_index == 0:
                        run.font.bold = True
    doc.add_heading('Manuscript metrics', level=2)
    table = doc.add_table(rows=len(DISPLAY_ROWS), cols=2)
    table.style = 'Table Grid'
    for row, (label, value) in zip(table.rows, DISPLAY_ROWS):
        row.cells[0].text = label
        row.cells[1].text = value
        for cell_index, cell in enumerate(row.cells):
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    run.font.size = Pt(9)
                    run.font.name = 'Times New Roman'
                    if cell_index == 0:
                        run.font.bold = True
    doc.add_paragraph('The abstract appears in the anonymised main text and in the cover '
                      'letter, and is therefore not repeated on this title page. The list of '
                      'companion files uploaded with this submission is given in the package '
                      'README.')
    output = SUB / 'title_page.docx'
    doc.save(output)
    return output


def build_cover_letter() -> Path:
    doc = Document()
    style(doc)
    doc.add_heading('Cover letter', level=1)
    for paragraph in [
        'Dear Editor,',
        'We submit the research paper titled "' + TITLE + '" for consideration as a research '
        'paper.',
        'The paper addresses a validation problem that current practice leaves open. A '
        'historical financial predictor can have several reported values, and a chronological '
        'train and test split does not specify which version a development process or a scoring '
        'exercise uses. I develop a crossed version validation protocol that holds observation '
        'identities, outcome labels, design weights and initial missingness fixed while version '
        'selection varies separately at development and at scoring. The protocol separates '
        'substitution of scoring inputs, redevelopment of the fitted pipeline and selection of '
        'the evaluated population, and it treats the information available at model fitting '
        'separately from the information available at the prediction origin.',
        'Applied to 5,502 annual filing windows with 188 linked bankruptcy registry events, the '
        'protocol shows that favorable differences between independently redeveloped pipelines '
        'need not reflect improved scoring inputs. The direct substitution contrast was -2.78, '
        '+1.37 and +0.11 average precision points across three test blocks against +4.95, +1.43 '
        'and +1.90 points for redevelopment, and changing the development domain while holding '
        'the evaluation sample fixed altered one contrast from +2.85 to -16.01 points. I read '
        'these results as evidence that financial data versioning belongs in model validation '
        'and governance records, and the paper sets out the reporting fields that make a version '
        'rule auditable.',
        'The paper is original, is not under consideration elsewhere, and has not been published '
        'previously. It is a single author submission. An AI use statement and declarations of '
        'interest appear in the manuscript. The anonymised main text, the supplementary '
        'material, editable figure and table files and the LaTeX source are uploaded with this '
        'letter.',
        'Yours sincerely,',
        AUTHOR['name_en'],
        AFFILIATIONS[0],
        AUTHOR['email'],
    ]:
        doc.add_paragraph(paragraph)
    output = SUB / 'cover_letter.docx'
    doc.save(output)
    return output


def docx_to_pdf(docx: Path) -> str:
    profile = TEMP / 'chrome-profile'
    pdf = SUB / 'pdf' / (docx.stem + '.pdf')
    if pdf.exists():
        pdf.unlink()
    # Convert through HTML so that the PDF text layer keeps its word spacing.
    html = TEMP / (docx.stem + '.html')
    subprocess.run(['pandoc', str(docx), '-o', str(html), '--standalone'],
                   capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    css = TEMP / 'plain.css'
    css.write_text('body{font-family:"Times New Roman",serif;font-size:11pt;'
                   'line-height:1.3;} h1{font-size:15pt;} table{border-collapse:collapse;'
                   'width:100%;font-size:10pt;} td{border:0.5pt solid #999;padding:3pt;}',
                   encoding='utf-8')
    text = html.read_text(encoding='utf-8').replace('</head>',
                                                    f'<link rel="stylesheet" href="{css.as_posix()}"></head>')
    html.write_text(text, encoding='utf-8')
    subprocess.run([str(CHROME), '--headless=new', '--disable-gpu', '--no-first-run',
                    '--no-pdf-header-footer', f'--user-data-dir={profile}',
                    f'--print-to-pdf={pdf}', html.as_uri()],
                   capture_output=True, text=True, encoding='utf-8', cwd=ROOT, timeout=300)
    return str(pdf) if pdf.exists() else 'failed'


if __name__ == '__main__':
    title_docx = build_title_page()
    cover_docx = build_cover_letter()
    report = {
        'title_page_docx': str(title_docx),
        'title_page_pdf': docx_to_pdf(title_docx),
        'cover_letter_docx': str(cover_docx),
        'cover_letter_pdf': docx_to_pdf(cover_docx),
        'word_count': WORD_COUNT,
        'abstract_words': len(ABSTRACT_TEXT.split()),
    }
    if not 150 <= report['abstract_words'] <= 200:
        report['abstract_warning'] = f"abstract is {report['abstract_words']} words"
    (ROOT / 'results' / 'title_page_build.json').write_text(json.dumps(report, indent=2),
                                                            encoding='utf-8')
    print(json.dumps(report, indent=2))
