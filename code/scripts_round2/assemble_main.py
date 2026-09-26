from pathlib import Path
import json,re,hashlib
R=Path(__file__).resolve().parents[1];M=R/'manuscript'
t=(M/'main_template.md').read_text(encoding='utf-8')
tables=json.loads((M/'generated_tables.json').read_text(encoding='utf-8'))
for k,v in tables.items():t=t.replace('{{'+k+'}}',v)
assert not re.search(r'\{\{.*?\}\}',t)
p=M/'manuscript.md';p.write_text(t,encoding='utf-8')
b=(R.parent/'revision_20260922/manuscript/references.bib').read_text(encoding='utf-8')+'\n'+(R/'literature/bibliography_updates.bib').read_text(encoding='utf-8')
(M/'references.bib').write_text(b,encoding='utf-8')
keys=set(re.findall(r'@\w+\{([^,]+),',b));cites=set(re.findall(r'@([\w]+)',t));assert cites<=keys, cites-keys
summary={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'words_with_tables':len(re.findall(r"\b[\w'-]+\b",t)), 'citation_count':len(cites),'citations':sorted(cites),'tables':len(re.findall(r'^Table \d+\.',t,re.M)),'figures':len(re.findall(r'^Figure \d',t,re.M))}
(M/'content_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
