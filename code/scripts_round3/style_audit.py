from pathlib import Path
import re

t = Path('revision_20260923_jrmv/manuscript/manuscript.md').read_text(encoding='utf-8')
body = t.split('# References')[0]
terms = ['furthermore', 'Furthermore', 'Moreover', 'It should be noted',
         'it is important to note', 'In addition,', 'Taken together', 'notably',
         'Interestingly', 'To summarize', 'In summary', 'Overall,', 'crucially',
         'Importantly', 'it is worth', 'arguably', 'To the best of']
for term in terms:
    n = body.count(term)
    if n:
        print(term, n)
print('---')
print('body words', len(re.findall(r"\b[\w'-]+\b", body)))
print('hyphenated tokens', len(set(re.findall(r"\b[A-Za-z]+-[A-Za-z]+\b", body))))
print('sections', re.findall(r'^#+ .*', body, re.M)[:40])
