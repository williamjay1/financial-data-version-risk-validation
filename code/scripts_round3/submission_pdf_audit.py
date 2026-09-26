"""Render submission PDF pages and audit layout, text fidelity and pagination."""
from pathlib import Path
import json

import pymupdf

PDF = Path('revision_20260923_jrmv/submission/pdf/main_manuscript_anonymised.pdf')
OUT = Path('revision_20260923_jrmv/temp/subpages')
OUT.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(str(PDF))
report = {'pages': doc.page_count, 'out_of_frame': [], 'images': [], 'warnings': []}
text = '\n'.join(doc[i].get_text() for i in range(doc.page_count))
for i in range(doc.page_count):
    page = doc[i]
    width, height = page.rect.width, page.rect.height
    for block in page.get_text('blocks'):
        x0, y0, x1, y1 = block[:4]
        if x0 < 2 or y0 < 2 or x1 > width - 2 or y1 > height - 2:
            report['out_of_frame'].append({'page': i + 1, 'box': [round(v) for v in block[:4]]})
    for image in page.get_images(full=True):
        report['images'].append({'page': i + 1, 'xref': image[0],
                                 'w': image[2], 'h': image[3]})
for token in ['{{', '}}', 'not found', '??', '@']:
    if token in text:
        report['warnings'].append(f'{token} present in PDF text')
for index in [0, 4, 6, 8, 10, 12]:
    if index < doc.page_count:
        pix = doc[index].get_pixmap(dpi=100)
        pix.save(str(OUT / f'subpage{index + 1:02d}.png'))
doc.close()
Path('revision_20260923_jrmv/results/submission_pdf_audit.json').write_text(
    json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()},
                 indent=2))
