#!/usr/bin/env python3
"""Compare the corpus with a pinned WYG traditional-character Zhuangzi zhu.

Read-only. Fetch the ten manifest URLs into --source-dir first (via GitHub
connector or another ordinary public download). Preserve original characters;
only the comparison view uses OpenCC t2s. Requires requirements-zhuangzi.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from opencc import OpenCC
from rapidfuzz.distance import Levenshtein

ROOT = Path(__file__).resolve().parents[1]
CC = OpenCC('t2s')
HEAD = re.compile(r'^\s*(?:(?:内|內|外|雜)篇)?(.+?)第([一二三四五六七八九十]+)\s*$')


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def number(text: str) -> int:
    digits = '一二三四五六七八九'
    if '十' not in text:
        return digits.index(text) + 1
    left, right = text.split('十')
    return (digits.index(left) + 1 if left else 1) * 10 + (digits.index(right) + 1 if right else 0)


def norm(text: str) -> str:
    return ''.join(c for c in CC.convert(text) if unicodedata.category(c).startswith('L') or c in '□⬤')


def parse_volume(raw: str, volume: int) -> list[dict]:
    # Parentheses exclusively encode interlinear commentary in this witness.
    # Keep commentary separately with raw offsets and leaf references.
    stripped, source_positions, notes = [], [], []
    depth = 0
    note_start = 0
    page = None
    pages_at_offset = []
    # Remove metadata separately so the dotall alternative cannot consume it.
    raw_without_headers = re.sub(r'^#.*$', lambda m: ' ' * len(m[0]), raw, flags=re.M)
    for match in re.finditer(r'<pb:([^>]+)>|[()]|.', raw_without_headers, re.S):
        value = match[0]
        if value.startswith('<pb:'):
            page = match[1]
            continue
        if value == '(':
            if depth == 0:
                note_start = match.start()
            depth += 1
        elif value == ')':
            depth -= 1
            if depth < 0:
                raise ValueError(f'Unmatched note close in volume {volume}')
            if depth == 0:
                notes.append({'raw_start': note_start, 'raw_end': match.end(), 'leaf': page,
                              'text': re.sub(r'<pb:[^>]+>|[¶\s/()]', '', raw[note_start:match.end()])})
        elif depth == 0 and value != '¶':
            stripped.append(value)
            source_positions.append(match.start())
            pages_at_offset.append(page)
    if depth:
        raise ValueError(f'Unclosed note in volume {volume}')
    text = ''.join(stripped)
    chapters, current, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        heading = HEAD.match(line.strip())
        if heading:
            current = {'number': number(heading[2]), 'traditional_title': heading[1], 'volume': volume,
                       'raw_heading_start': source_positions[offset],
                       'text': '', 'leaves': [], 'raw_positions': [], 'notes': []}
            chapters.append(current)
        elif current and line.strip() and not re.match(r'\s*(欽定四庫全書|[莊荘]子注[巻卷])', line):
            for j, char in enumerate(line):
                if not char.isspace():
                    current['text'] += char
                    current['leaves'].append(pages_at_offset[offset + j])
                    current['raw_positions'].append(source_positions[offset + j])
        offset += len(line)
    for i, c in enumerate(chapters):
        begin = c['raw_heading_start']
        end = chapters[i + 1]['raw_heading_start'] if i + 1 < len(chapters) else len(raw)
        c['notes'] = [n for n in notes if begin <= n['raw_start'] <= end]
    return chapters


def compare(chapter: dict, local: dict) -> dict:
    traditional = chapter['text']
    simple = CC.convert(traditional)
    if len(simple) != len(traditional):
        raise ValueError('Length-changing conversion requires explicit offset alignment')
    indexes = [i for i, c in enumerate(simple) if unicodedata.category(c).startswith('L') or c in '□⬤']
    source = ''.join(simple[i] for i in indexes)
    path = ROOT / local['path']
    raw_local = path.read_text(encoding='utf-8')
    body = norm(raw_local.split('---', 2)[2])
    differences = []
    for op in Levenshtein.opcodes(body, source):
        if op.tag == 'equal':
            continue
        start = indexes[op.dest_start] if op.dest_start < len(indexes) else len(traditional)
        end = indexes[op.dest_end] if op.dest_end < len(indexes) else len(traditional)
        differences.append({'kind': op.tag, 'local_offset': op.src_start, 'source_offset': op.dest_start,
                            'local': body[op.src_start:op.src_end], 'source_simplified': source[op.dest_start:op.dest_end],
                            'source_traditional': traditional[start:end],
                            'source_leaf': chapter['leaves'][min(start, len(traditional) - 1)],
                            'before': body[max(0, op.src_start - 18):op.src_start],
                            'after': body[op.src_end:op.src_end + 18],
                            'traditional_before': traditional[max(0, start - 18):start],
                            'traditional_after': traditional[end:end + 18]})
    gaps = [{'offset': i, 'symbol': c, 'leaf': chapter['leaves'][i],
             'context': traditional[max(0, i - 15):i + 16]} for i, c in enumerate(traditional) if c in '□⬤']
    return {'number': local['number'], 'title': local['title'], 'traditional_title': chapter['traditional_title'],
            'path': local['path'], 'volume': chapter['volume'], 'local_sha256': digest(raw_local),
            'traditional_sha256': digest(traditional), 'local_characters': len(body), 'source_characters': len(source),
            'first_leaf': chapter['leaves'][0], 'last_leaf': chapter['leaves'][-1], 'source_gaps': gaps,
            'differences': differences}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=Path.home() / '.cache/ifcalm-books/zhuangzi-traditional')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extract', type=Path, help='Optional traditional prose and notes for manual inspection')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'scripts/data/zhuangzi_traditional_sources.json').read_text())
    local = json.loads((ROOT / 'scripts/data/zhuangzi_sources.json').read_text())['chapters']
    chapters = []
    for volume in manifest['volumes']:
        raw = (args.source_dir / volume['file']).read_text(encoding='utf-8')
        if digest(raw) != volume['sha256']:
            raise ValueError('Source hash differs: ' + volume['file'])
        data = raw.encode('utf-8')
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != volume['git_blob_sha1']:
            raise ValueError('Source Git blob differs: ' + volume['file'])
        chapters.extend(parse_volume(raw, volume['number']))
    if [c['number'] for c in chapters] != list(range(1, 34)):
        raise ValueError('Expected all 33 chapters in order')
    results = [compare(c, l) for c, l in zip(chapters, local)]
    if min(r['source_characters'] for r in results) < 500:
        raise ValueError('Short or incomplete chapter extraction')
    output = {'source': manifest, 'normalization': 'Source preserved in traditional characters; comparison only: OpenCC t2s, Unicode letters plus source gap symbols',
              'interpretation': 'Difference groups include variants, source transcription defects, and normalization effects; not an error count.',
              'chapters': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.extract:
        args.extract.write_text(json.dumps(chapters, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Compared all 33 chapters from {len(manifest["volumes"])} traditional volumes; '
          f'{sum(len(r["differences"]) for r in results)} difference groups, '
          f'{sum(len(r["source_gaps"]) for r in results)} source gap symbols.')


if __name__ == '__main__':
    main()
