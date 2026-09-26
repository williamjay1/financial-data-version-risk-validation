"""Verify the delivered PDFs: pagination, text fidelity, displays and images."""
from pathlib import Path
import re

import pdfplumber

DELIVERY = Path('revision_20260923_jrmv/delivery')
FAIL: list[str] = []
report = {}
for name in ['Financial_Data_Version_Risk_Manuscript', 'Financial_Data_Version_Risk_Supplement']:
    path = DELIVERY / f'{name}.pdf'
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or '' for p in pdf.pages]
        images = []
        for i, page in enumerate(pdf.pages):
            for im in page.images:
                images.append({'page': i + 1, 'w': round(im['srcsize'][0]),
                               'h': round(im['srcsize'][1])})
    joined = '\n'.join(pages)
    words = re.findall(r'[A-Za-z]{2,}', joined)
    # A dropped-space defect shows up as implausibly long runs of ordinary words.
    # Camel case accounting tag names are legitimately long and are excluded.
    ordinary = [w for w in words
                if not (w[0].isupper() and sum(c.isupper() for c in w) >= 3)]
    longest = max((len(w) for w in ordinary), default=0)
    tables = re.findall(r'Table (\d+)\.', joined)
    figures = re.findall(r'Figure (\d+)\.', joined)
    entry = {'pages': len(pages), 'chars': len(joined), 'longest_token': longest,
             'tables': sorted(set(tables)), 'figures': sorted(set(figures)),
             'images': images, 'placeholders': re.findall(r'\{\{.*?\}\}', joined)}
    report[name] = entry
    if entry['placeholders']:
        FAIL.append(f'{name}: placeholder text in PDF')
    if longest > 30:
        FAIL.append(f'{name}: suspiciously long token {longest}')
    if name.endswith('Manuscript'):
        if sorted(set(tables)) != [str(i) for i in range(1, 7)]:
            FAIL.append(f'{name}: table captions {sorted(set(tables))}')
        if sorted(set(figures)) != [str(i) for i in range(1, 6)]:
            FAIL.append(f'{name}: figure captions {sorted(set(figures))}')
        if len(images) != 5:
            FAIL.append(f'{name}: {len(images)} figures embedded')
report['failures'] = FAIL
Path('revision_20260923_jrmv/results/pdf_qa.json').write_text(
    __import__('json').dumps(report, indent=2), encoding='utf-8')
print(__import__('json').dumps(report, indent=2))
if FAIL:
    raise SystemExit('PDF QA failures: ' + '; '.join(FAIL))
