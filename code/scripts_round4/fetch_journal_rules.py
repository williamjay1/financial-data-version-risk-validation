"""Fetch the publisher's editorial policy and submission guideline pages as plain text."""
import re
import urllib.request
from pathlib import Path

OUT = Path('revision_20260924_audited/temp/risknet')
OUT.mkdir(parents=True, exist_ok=True)
PAGES = {
    'editorial_policies': 'https://www.risk.net/static/editorial-policies',
    'submission_guidelines': 'https://www.risk.net/static/risk-journals-submission-guidelines',
}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'}

for name, url in PAGES.items():
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=40) as response:
        html = response.read().decode('utf-8', 'ignore')
    (OUT / f'{name}.html').write_text(html, encoding='utf-8')
    body = re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>', ' ', html)
    body = re.sub(r'(?is)<br\s*/?>|</(p|div|li|h[1-6]|tr)>', '\n', body)
    body = re.sub(r'(?is)<li[^>]*>', '\n- ', body)
    text = re.sub(r'(?s)<[^>]+>', ' ', body)
    text = (text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
            .replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')
            .replace('&rsquo;', "'").replace('&lsquo;', "'").replace('&mdash;', '-')
            .replace('&ndash;', '-'))
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    (OUT / f'{name}.txt').write_text(text.strip(), encoding='utf-8')
    print(name, len(html), '->', len(text))
