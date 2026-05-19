#!/usr/bin/env python3
"""Test cleaner on a single volume of 史记."""
import sys, urllib.request, urllib.parse, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext

USER_AGENT = 'ifcalm-books/1.0'
url = 'https://zh.wikisource.org/w/index.php?title=%E5%8F%B2%E8%A8%98%2F%E5%8D%B7001&action=raw'
req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
with urllib.request.urlopen(req, timeout=60) as r:
    raw = r.read().decode('utf-8')

clean = clean_wikitext(raw)
print(f'Length: {len(raw)} -> {len(clean)} chars')
print('=== First 700 chars ===')
print(clean[:700])
print('...\n=== Last 400 chars ===')
print(clean[-400:])

artifacts = re.findall(r'(\{\{[^}]+\}\}|-\{[^}]*\}-|\[\[[^\]]+\]\]|<[^>]+>)', clean)
if artifacts:
    print(f'\n=== Remaining artifacts ({len(artifacts)}) ===')
    for a in artifacts[:10]:
        print(f'  {repr(a)}')
else:
    print('\nClean! No wiki artifacts remaining.')
