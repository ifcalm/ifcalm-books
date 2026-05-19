#!/usr/bin/env python3
"""Analyze Wikisource wikitext for 二十四史 to understand template usage."""
import urllib.request, urllib.parse, re
from collections import Counter

USER_AGENT = 'ifcalm-books/1.0'

def fetch_raw(title):
    url = 'https://zh.wikisource.org/w/index.php?title={}&action=raw'.format(
        urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')

# Analyze 史记/卷001
raw = fetch_raw('史記/卷001')

templates = re.findall(r'\{\{([^|{}#:]+)', raw)
print("=== Templates in 史记/卷001 ===")
for name, count in Counter(templates).most_common(40):
    print(f"  {name}: {count}")

print(f"\n=== Total length: {len(raw)} chars ===")

# Check heading structure
headings = re.findall(r'^(=+)\s*(.+?)\s*\1$', raw, re.M)
print("\n=== Headings ===")
for level, title in headings:
    print(f"  {'#' * len(level)} {title.strip()}")

# Last 800 chars to see references/footnotes
print("\n=== Last 800 chars ===")
print(raw[-800:])

# Check 汉书 too
print("\n\n=== 汉书/卷001 templates ===")
raw2 = fetch_raw('漢書/卷001')
templates2 = re.findall(r'\{\{([^|{}#:]+)', raw2)
for name, count in Counter(templates2).most_common(20):
    print(f"  {name}: {count}")
