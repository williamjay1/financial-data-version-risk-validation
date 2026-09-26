"""Build the PDF reading copies from the manuscript Markdown.

The DOCX deliverables are the editable versions. The PDFs are produced by
pandoc for HTML and then by headless Chrome for pagination, because the
installed Word version writes PDFs whose text layer loses inter-word spacing and
therefore cannot be searched or copied. Figures are embedded at their full 900
dpi raster size, and the vector PDF and SVG versions ship alongside.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / 'manuscript'
TEMP = ROOT / 'temp'
DELIVERY = ROOT / 'delivery'
TEMP.mkdir(exist_ok=True)
DELIVERY.mkdir(exist_ok=True)

CHROME = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')

CSS = """
@page { size: A4; margin: 19mm 18mm 18mm 18mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Times New Roman", "Liberation Serif", serif; font-size: 10.4pt;
       line-height: 1.30; color: #000; text-align: justify; hyphens: none; }
h1.title { font-size: 15pt; line-height: 1.25; text-align: left; margin: 0 0 10pt 0; font-weight: bold; }
h1 { font-size: 12.5pt; margin: 14pt 0 6pt 0; page-break-after: avoid; }
h2 { font-size: 11.2pt; margin: 12pt 0 5pt 0; page-break-after: avoid; }
h3 { font-size: 10.6pt; margin: 10pt 0 4pt 0; page-break-after: avoid; }
p { margin: 0 0 5pt 0; }
ol, ul { margin: 0 0 6pt 0; padding-left: 16pt; }
li { margin-bottom: 2pt; }
figure { margin: 8pt 0 8pt 0; page-break-inside: avoid; text-align: center; }
figure img { width: 100%; max-width: 100%; }
figcaption { font-size: 9pt; text-align: left; margin-top: 4pt; line-height: 1.25; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 4pt 0 6pt 0;
        page-break-inside: avoid; }
thead { display: table-header-group; }
th { background: #E8EDF2; text-align: center; font-weight: bold; }
th, td { border: 0.5pt solid #BFBFBF; padding: 2.2pt 3pt; }
td:first-child, th:first-child { text-align: left; }
caption { caption-side: top; text-align: left; font-size: 9pt; margin-bottom: 3pt; }
.math { font-family: "Cambria Math", "Times New Roman", serif; }
.math.display { display: block; text-align: center; margin: 6pt 0; }
blockquote { margin: 0; }
code { font-family: "Consolas", monospace; font-size: 9pt; }
"""


def pandoc(source: Path, output: Path, to: str, extra: list[str]) -> None:
    exe = shutil.which('pandoc')
    if not exe:
        raise FileNotFoundError('pandoc is not available')
    command = [exe, str(source), '--standalone', f'--to={to}', '-o', str(output)] + extra
    run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    if run.returncode:
        raise RuntimeError(run.stderr)


def markdown_to_print_html(source: Path, stem: str, title: str) -> Path:
    text = source.read_text(encoding='utf-8')
    # Inline every figure as a base64 data URI: headless Chrome does not load
    # relative file:// images, and a data URI removes that dependency entirely.
    data_uris: list[str] = []
    for match in re.finditer(r'!\[\]\(([^)]+)\)', text):
        rel = match.group(1)
        image = MAN / rel
        if not image.exists():
            raise FileNotFoundError(f'figure not found: {image}')
        encoded = base64.b64encode(image.read_bytes()).decode('ascii')
        mime = 'image/png' if image.suffix.lower() == '.png' else 'image/jpeg'
        data_uris.append(f'data:{mime};base64,{encoded}')
        text = text.replace(match.group(0), f'FIGSRCTOKEN{len(data_uris) - 1}ENDTOKEN')
    staged = TEMP / f'{stem}_inlined.md'
    staged.write_text(text, encoding='utf-8')
    body_html = TEMP / f'{stem}_body.html'
    pandoc(staged, body_html, 'html5', ['--mathml', '--wrap=none'])
    body = body_html.read_text(encoding='utf-8')
    inner = re.search(r'<body[^>]*>(.*)</body>', body, re.S)
    inner = inner.group(1) if inner else body
    for index, uri in enumerate(data_uris):
        pattern = re.compile(r'<p>\s*FIGSRCTOKEN' + str(index) +
                             r'ENDTOKEN(\{[^}]*\})?\s*</p>')
        inner, count = pattern.subn(f'<figure><img src="{uri}"></figure>', inner)
        if count != 1:
            raise SystemExit(f'figure placeholder {index} replaced {count} times')
    if 'FIGSRCTOKEN' in inner:
        raise SystemExit('figure placeholder was not replaced')
    stylesheet = TEMP / f'{stem}.css'
    stylesheet.write_text(CSS, encoding='utf-8')
    page = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<title>{title}</title>\n'
            f'<link rel="stylesheet" href="{stylesheet.as_posix()}">\n'
            '</head>\n<body>\n'
            f'<h1 class="title">{title}</h1>\n'
            f'{inner}\n</body>\n</html>\n')
    html = TEMP / f'{stem}.html'
    html.write_text(page, encoding='utf-8')
    return html


def html_to_pdf(html: Path, pdf: Path) -> str:
    if not CHROME.exists():
        raise FileNotFoundError(f'Chrome not found at {CHROME}')
    if pdf.exists():
        pdf.unlink()
    profile = TEMP / 'chrome-profile'
    command = [str(CHROME), '--headless=new', '--disable-gpu', '--no-first-run',
               '--no-pdf-header-footer', f'--user-data-dir={profile}',
               f'--print-to-pdf={pdf}', html.as_uri()]
    subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                   cwd=ROOT, timeout=600)
    if not pdf.exists():
        raise RuntimeError('Chrome produced no PDF')
    return str(pdf)


if __name__ == '__main__':
    title = ('Financial data version risk in bankruptcy model validation: '
             'separating scoring, development and evaluation effects')
    # Stage the title into the markdown so the HTML heading matches the DOCX.
    staged = TEMP / 'manuscript_print.md'
    text = (MAN / 'manuscript.md').read_text(encoding='utf-8')
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)
    staged.write_text(text.lstrip('\n'), encoding='utf-8')
    html = markdown_to_print_html(staged, 'manuscript_print', title)
    pdf = html_to_pdf(html, DELIVERY / 'Financial_Data_Version_Risk_Manuscript.pdf')

    supp = MAN / 'supplement.md'
    supp_html = markdown_to_print_html(supp, 'supplement_print', 'Supplementary Methods and Results')
    supp_pdf = html_to_pdf(supp_html, DELIVERY / 'Financial_Data_Version_Risk_Supplement.pdf')

    print(json.dumps({'manuscript_pdf': pdf, 'supplement_pdf': supp_pdf}, indent=2))
