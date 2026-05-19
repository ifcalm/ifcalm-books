#!/usr/bin/env python3
"""Quick test of wikitext_cleaner on 史记/卷001."""
import sys, urllib.request, urllib.parse
sys.path.insert(0, 'lib')
from wikitext_cleaner import clean_wikitext

USER_AGENT = 'ifcalm-books/1.0'

def fetch_raw(title):
    url = 'https://zh.wikisource.org/w/index.php?title={}&action=raw'.format(
        urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')

raw = fetch_raw('史記/卷001')
clean = clean_wikitext(raw)

print(f"Raw: {len(raw)} chars, Clean: {len(clean)} chars")
print("=" * 60)
print(clean[:3000])
print("...")
print("\n" + "=" * 60)
print("Last 500 chars:")
print(clean[-500:])
