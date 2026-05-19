#!/usr/bin/env python3
import urllib.request, urllib.parse, re
USER_AGENT = 'ifcalm-books/1.0'
url = 'https://zh.wikisource.org/w/index.php?title=%E5%8F%B2%E8%A8%98%2F%E5%8D%B7001&action=raw'
req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
with urllib.request.urlopen(req, timeout=30) as r:
    raw = r.read().decode('utf-8')

for m in re.finditer(r'-\{zh:絺[^}]*\}-', raw):
    start = max(0, m.start() - 80)
    end = min(len(raw), m.end() + 80)
    print(f"Position {m.start()}: ...{raw[start:end]}...")
    print()
