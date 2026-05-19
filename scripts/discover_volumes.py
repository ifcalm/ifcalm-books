#!/usr/bin/env python3
"""Discover volume page titles for a history by parsing its main Wikisource page."""
import sys, urllib.request, urllib.parse, re
from pathlib import Path
from collections import OrderedDict

USER_AGENT = 'ifcalm-books/1.0'

def fetch_raw(title):
    url = 'https://zh.wikisource.org/w/index.php?title={}&action=raw'.format(
        urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')

def discover_volumes(main_page: str, prefix: str) -> dict[int, str]:
    """Parse the main page and extract volume page titles.
    Returns dict of {volume_number: page_title}.
    """
    text = fetch_raw(main_page)
    volumes: dict[int, str] = OrderedDict()

    # Pattern 1: * [[prefix/卷XX|...]]
    for m in re.finditer(r'\*\s*\[\[((?:' + re.escape(prefix) + r'/)?卷(\d+))[|\]]', text):
        page_title, vol_str = m.group(1), m.group(2)
        vol = int(vol_str)
        if vol not in volumes:
            volumes[vol] = page_title

    # Pattern 2: [[prefix/卷XX|...]]  (non-* links)
    if not volumes:
        for m in re.finditer(r'\[\[((?:' + re.escape(prefix) + r'/)?卷(\d+))[|\]]', text):
            page_title, vol_str = m.group(1), m.group(2)
            vol = int(vol_str)
            if vol not in volumes:
                volumes[vol] = page_title

    return volumes


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python discover_volumes.py <main_page> <prefix>")
        print("Example: python discover_volumes.py 史記 史記")
        sys.exit(1)

    main_page = sys.argv[1]
    prefix = sys.argv[2]
    volumes = discover_volumes(main_page, prefix)
    print(f"Found {len(volumes)} volumes for {main_page}:")
    for vol, title in list(volumes.items())[:5]:
        print(f"  Vol {vol}: {title}")
    if len(volumes) > 5:
        print(f"  ... and {len(volumes) - 5} more")
    print(f"  Max vol: {max(volumes.keys()) if volumes else 'N/A'}")
    print(f"  Gaps: {sorted(set(range(1, max(volumes.keys())+1)) - set(volumes.keys()))[:10] if volumes else 'N/A'}")
