#!/usr/bin/env python3
"""Test fetch + clean for sample 史记 volumes."""
import sys, time, re, urllib.request, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext

USER_AGENT = 'ifcalm-books/1.0'
API = 'https://zh.wikisource.org/w/index.php?title={}&action=raw'

def fetch(title):
    url = API.format(urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8')

for vol in [1, 2, 130]:
    title = '史記/卷{:03d}'.format(vol)
    print(f'Fetching 史記/卷{vol:03d}...', end=' ', flush=True)
    raw = fetch(title)
    clean = clean_wikitext(raw)
    headings = re.findall(r'^###\s+.+$', clean, re.M)
    print(f'OK: {len(raw)} -> {len(clean)} chars, {len(headings)} sections')
    if headings:
        print(f'  First heading: {headings[0]}')
    time.sleep(0.5)
print('All passed!')
