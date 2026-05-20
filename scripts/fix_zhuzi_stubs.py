#!/usr/bin/env python3
"""Remove stub/wrapper pages from 诸子 content and renumber remaining files."""

import re, shutil
from pathlib import Path

ZHUZI = Path('content/posts/zhuzi')

def body_text(path):
    parts = path.read_text().split('---\n', 2)
    return parts[2].strip() if len(parts) > 2 else ''

def remove_stubs(text_dir, min_chars=100):
    """Remove files with content < min_chars, renumber remaining."""
    md_files = sorted(f for f in text_dir.rglob('*.md') if f.name != '_index.md')
    stubs = [f for f in md_files if len(body_text(f)) < min_chars]
    good = [f for f in md_files if f not in stubs]

    if not stubs:
        return 0

    name = text_dir.name
    print(f'\n{name}: removing {len(stubs)} stub(s), keeping {len(good)} files')
    for s in stubs:
        print(f'  REMOVE: {s.name} ({len(body_text(s))} chars)')
        s.unlink()

    # Renumber remaining files
    for i, f in enumerate(sorted(good), start=1):
        new_name = f'{name}-{i:03d}.md'
        if f.name != new_name:
            # Update frontmatter weight
            content = f.read_text()
            content = re.sub(r'weight: \d+', f'weight: {i}', content)
            f.write_text(content)
            f.rename(f.parent / new_name)
    return len(stubs)


# Fix each text
fixes = {
    'hanfeizi': 100,   # Remove numbered volume wrappers
    'lvshi-chunqiu': 50,  # Remove redirect pages
    'huainanzi': 50,   # Remove redirect page
}

for slug, min_chars in fixes.items():
    d = ZHUZI / slug
    if d.exists():
        remove_stubs(d, min_chars)

print('\nDone.')
