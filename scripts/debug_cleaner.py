#!/usr/bin/env python3
"""Debug the wikitext cleaner step by step."""
import sys, urllib.request, urllib.parse, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext

USER_AGENT = 'ifcalm-books/1.0'

def fetch_raw(title):
    url = 'https://zh.wikisource.org/w/index.php?title={}&action=raw'.format(
        urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')

raw = fetch_raw('史記/卷001')

# Find all -{...}- patterns in raw text
variants = re.findall(r'-\{[^}]+\}-', raw)
print(f"Found {len(variants)} -{{...}}- patterns:")
for v in set(variants):
    print(f"  {v}")

# Find all remaining templates in raw text (after -{ clean)
tmp_text = re.sub(r'-\{[^}]+\}-', '', raw)
remaining = re.findall(r'\{\{[^}]+\}\}', tmp_text)
print(f"\nRemaining templates after -{{}}- cleanup ({len(remaining)}):")
from collections import Counter
for name, count in Counter(remaining).most_common(15):
    print(f"  {name}: {count}")

# Run full cleaner
clean = clean_wikitext(raw)

# Check for issues
issue_templates = re.findall(r'\{\{[^}]+\}\}', clean)
if issue_templates:
    print(f"\nRemaining templates in output ({len(issue_templates)}):")
    for t in Counter(issue_templates).most_common(10):
        print(f"  {t[0]}: {t[1]}")

if '<br' in clean:
    print("\nStill has <br> tags")
if '-{' in clean:
    remaining_var = re.findall(r'-\{[^}]*\}-', clean)
    print(f"\nStill has -{{}}- patterns: {remaining_var[:5]}")

print(f"\nRaw: {len(raw)} -> Clean: {len(clean)} chars")
