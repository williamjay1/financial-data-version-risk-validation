"""Render selected delivered pages plus a word-level framing audit of the PDF."""
from pathlib import Path
import json

import fitz

PDF = Path('revision_20260923_jrmv/delivery/Financial_Data_Version_Risk_Manuscript.pdf')
OUT = Path('revision_20260923_jrmv/temp/pdfpages')
OUT.mkdir(parents=True, exist_ok=True)

doc = fitz.open(str(PDF))
report = {'pages': doc.page_count, 'out_of_frame': [], 'overlaps': []}
for index, page in enumerate(doc):
    width, height = page.rect.width, page.rect.height
    words = page.get_text('words')
    for x0, y0, x1, y1, text, *_ in words:
        if x0 < 4 or y0 < 4 or x1 > width - 4 or y1 > height - 4:
            report['out_of_frame'].append({'page': index + 1, 'text': text,
                                           'box': [round(x0), round(y0), round(x1), round(y1)]})
    # Detect lines whose baselines are closer than 60 percent of the font height,
    # which is what a collapsed line spacing or overlap looks like.
    lines = {}
    for x0, y0, x1, y1, text, *_ in words:
        lines.setdefault(round(y0), []).append((x0, x1, text))
    keys = sorted(lines)
    for a, b in zip(keys, keys[1:]):
        if 0 < b - a < 3:
            report['overlaps'].append({'page': index + 1, 'y_a': a, 'y_b': b})

for index in [0, 3, 4, 6, 8, 10, 15]:
    if index < doc.page_count:
        pix = doc[index].get_pixmap(dpi=90)
        target = OUT / f'page{index + 1:02d}.png'
        pix.save(str(target))
        report.setdefault('renders', []).append(str(target))
doc.close()
Path('revision_20260923_jrmv/results/pdf_layout_audit.json').write_text(
    json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k: (v if k not in ('out_of_frame', 'overlaps') else len(v))
                  for k, v in report.items()}, indent=2))
