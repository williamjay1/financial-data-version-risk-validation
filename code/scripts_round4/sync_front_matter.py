"""Synchronise the submission front matter with the finalized manuscript abstract."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / 'manuscript'
FRONT = ROOT / 'submission/front_matter.json'

text = (MAN / 'manuscript.md').read_text(encoding='utf-8')
body = text.split('# References')[0]
abstract = body.split('# Abstract')[1].split('**Keywords')[0].strip()

data = json.loads(FRONT.read_text(encoding='utf-8'))
data['abstract'] = abstract
FRONT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'abstract_words': len(abstract.split()),
                  'keywords': len(data['keywords']),
                  'key_messages': len(data['key_messages']),
                  'longest_key_message': max(len(m) for m in data['key_messages'])},
                 indent=2))
