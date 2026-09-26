"""Render the supplementary methods and results document as the submission supplement.

The supplement keeps its own S numbering, so the working copy notes that described
the shared displays are dropped here: the figures and tables already appear inside
the main text PDF, which is what the submission requires.
"""
from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
MAN = ROOT / 'manuscript'
TEMP = ROOT / 'temp'
SUB = ROOT / 'submission'
CHROME = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')

CSS = """
@page { size: A4; margin: 19mm 18mm 18mm 18mm; }
body { font-family: "Times New Roman", "Liberation Serif", serif; font-size: 9.6pt;
       line-height: 1.28; color: #000; text-align: justify; }
h1 { font-size: 13pt; margin: 12pt 0 6pt 0; }
h2 { font-size: 11pt; margin: 11pt 0 4pt 0; page-break-after: avoid; }
h3 { font-size: 10.2pt; margin: 9pt 0 3pt 0; }
table { border-collapse: collapse; width: 100%; font-size: 8pt; margin: 4pt 0 6pt 0; }
th { background: #E8EDF2; }
th, td { border: 0.5pt solid #BFBFBF; padding: 2pt 2.4pt; }
td:first-child, th:first-child { text-align: left; }
p { margin: 0 0 4pt 0; }
"""

text = (MAN / 'supplement.md').read_text(encoding='utf-8')
# Drop the working notes that describe displays shared with the main text.
text = re.sub(r'## S0\..*?(?=## S1\.)', '', text, flags=re.S)
text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)
text = text.replace('# Supplementary Methods and Results', '')
staged = TEMP / 'supplement_submission.md'
staged.write_text(text.strip(), encoding='utf-8')

body_html = TEMP / 'supplement_submission_body.html'
subprocess.run(['pandoc', str(staged), '--standalone', '--to=html5', '--mathml',
                '--wrap=none', '-o', str(body_html)], check=True, cwd=ROOT)
inner = re.search(r'<body[^>]*>(.*)</body>',
                  body_html.read_text(encoding='utf-8'), re.S).group(1)
css = TEMP / 'supplement_submission.css'
css.write_text(CSS, encoding='utf-8')
page = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<title>Supplementary Methods and Results</title>\n'
        f'<link rel="stylesheet" href="{css.as_posix()}">\n</head>\n<body>\n'
        '<h1>Supplementary Methods and Results</h1>\n'
        '<p>Supplementary material for the paper '
        '&#8220;Financial data version risk in bankruptcy model validation: separating '
        'scoring, development and evaluation effects&#8221;.</p>\n'
        f'{inner}\n</body>\n</html>\n')
html = TEMP / 'supplement_submission.html'
html.write_text(page, encoding='utf-8')

pdf = SUB / 'pdf' / 'supplementary_material.pdf'
if pdf.exists():
    pdf.unlink()
subprocess.run([str(CHROME), '--headless=new', '--disable-gpu', '--no-first-run',
                '--no-pdf-header-footer', f'--user-data-dir={TEMP / "chrome-profile"}',
                f'--print-to-pdf={pdf}', html.as_uri()],
               capture_output=True, text=True, encoding='utf-8', cwd=ROOT, timeout=600)
print('supplement pdf:', pdf, pdf.exists(), pdf.stat().st_size if pdf.exists() else 0)
