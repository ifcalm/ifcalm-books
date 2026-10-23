#!/usr/bin/env python3
"""Read-only full-text comparison with new Zhuangzi digital witnesses.

Requires scripts/requirements-zhuangzi.txt. Never changes corpus content.
Raw responses are cached as bytes; unresolved source glyph images stay as □.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from opencc import OpenCC
from rapidfuzz.distance import Levenshtein

ROOT = Path(__file__).resolve().parents[1]
CC = OpenCC('t2s')
INDEX = 'https://www.gushiwen.cn/guwen/book.aspx?id=26'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch(url: str, cache: Path, offline: bool) -> bytes:
    path = cache / (sha(url.encode()) + '.bin')
    if path.exists():
        return path.read_bytes()
    if offline:
        raise ValueError('Missing cached response: ' + url)
    request = urllib.request.Request(url, headers={'User-Agent': 'ifcalm-books text review; https://books.ifcalm.org/'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def normalize(text: str) -> str:
    # Retain source gaps rather than silently deleting image-only characters.
    return ''.join(c for c in CC.convert(text) if unicodedata.category(c).startswith('L') or c == '□')


def parse(raw: bytes, kind: str, url: str) -> dict:
    soup = BeautifulSoup(raw, 'html.parser')
    if kind == 'classic':
        node = soup.find('blockquote')
        if node is None:
            raise ValueError('Missing classic body: ' + url)
        for el in node.select('h1, h2, a, script, style'):
            el.decompose()
    elif kind == 'gushiwen':
        node = soup.select_one('div[id^="zhengwen"] .contson')
        if node is None:
            raise ValueError('Missing gushiwen body: ' + url)
    elif kind == 'sixarts':
        container = soup.select_one('.scroll_maincontent')
        if container is None:
            raise ValueError('Missing sixarts container: ' + url)
        # The site explicitly separates running text from interlinear notes.
        for el in container.select('.budjs, sup'):
            el.decompose()
        node = BeautifulSoup('<div></div>', 'html.parser').div
        for p in container.select('p.bud-text'):
            node.append(p.extract())
    else:
        raise ValueError(kind)
    images = []
    for img in node.find_all('img'):
        images.append({'url': urljoin(url, img.get('src', '')), 'alt': img.get('alt', '')})
        img.replace_with('□')
    text = re.sub(r'\s+', '', node.get_text())
    if kind == 'classic':
        text = re.sub(r'^＞＞', '', text)
    cleanups = []
    if kind == 'sixarts' and url.endswith('/chongx4.html'):
        # A premature </span> in this source leaks the remainder of a note
        # outside .budjs. Remove only the verified annotation, not prose.
        leaked = '：﹃樠，松心，又木名也。﹄松心有脂，液樠正取此義。﹂'
        if text.count(leaked) != 1:
            raise ValueError('Changed malformed source note: ' + url)
        text = text.replace(leaked, '')
        cleanups.append({'kind': 'malformed_interlinear_note', 'removed': leaked})
    normalized = normalize(text)
    return {'text': text, 'normalized': normalized, 'glyph_images': images, 'source_cleanups': cleanups,
            'characters': len(normalized), 'encoding': soup.original_encoding,
            'text_sha256': sha(text.encode()), 'response_sha256': sha(raw),
            'status': 'complete_page' if len(normalized) >= 500 else 'incomplete_page'}


def differences(local: str, witness: str) -> list[dict]:
    rows = []
    for op in Levenshtein.opcodes(local, witness):
        if op.tag == 'equal':
            continue
        rows.append({'kind': op.tag, 'local_offset': op.src_start, 'source_offset': op.dest_start,
                     'local': local[op.src_start:op.src_end], 'source': witness[op.dest_start:op.dest_end],
                     'before': local[max(0, op.src_start - 20):op.src_start],
                     'after': local[op.src_end:op.src_end + 20]})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, default=Path.home() / '.cache/ifcalm-books/zhuangzi-recheck')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--include-text', action='store_true', help='Include extracted source prose for inspection')
    args = parser.parse_args()
    chapters = json.loads((ROOT / 'scripts/data/zhuangzi_sources.json').read_text())['chapters']
    raw_index = fetch(INDEX, args.cache_dir, args.offline)
    index = BeautifulSoup(raw_index, 'html.parser')
    links = [urljoin(INDEX, a['href']) for a in index.select('a[href]') if '/guwen/bookv_' in a['href']]
    links = list(dict.fromkeys(links))
    if len(links) != 33:
        raise ValueError('Expected 33 gushiwen chapter links')
    jobs = []
    for c, guwen_url in zip(chapters, links):
        for kind, url in [('classic', f'https://www.chineseclassic.com/ChungTzu/ChungTzu{c["number"]:02d}.htm'),
                          ('gushiwen', guwen_url),
                          ('sixarts', f'https://www.sixarts.info/chongjg/chongx{c["number"]}.html')]:
            jobs.append((c, kind, url))

    def collect(job: tuple) -> dict:
        c, kind, url = job
        row = {'number': c['number'], 'title': c['title'], 'path': c['path'], 'source': kind, 'url': url}
        try:
            result = parse(fetch(url, args.cache_dir, args.offline), kind, url)
            body = (ROOT / c['path']).read_text().split('---', 2)[2]
            row.update(result)
            row['local_sha256'] = sha((ROOT / c['path']).read_bytes())
            row['differences'] = differences(normalize(body), result['normalized']) if result['status'] == 'complete_page' else []
            if not args.include_text:
                row.pop('text')
                row.pop('normalized')
        except Exception as exc:
            row.update({'status': 'unavailable', 'error': str(exc)})
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(collect, jobs))
    output = {'normalization': 'OpenCC t2s; Unicode letters and unresolved-image □ only; punctuation/whitespace excluded',
              'interpretation': 'Differences require editorial review; source gaps and edition variants are not automatic local errors.',
              'index': {'url': INDEX, 'response_sha256': sha(raw_index)}, 'comparisons': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    for kind in ('classic', 'gushiwen', 'sixarts'):
        selected = [r for r in rows if r['source'] == kind]
        print(kind, {status: sum(r['status'] == status for r in selected) for status in ('complete_page', 'incomplete_page', 'unavailable')},
              'source glyph images:', sum(len(r.get('glyph_images', [])) for r in selected), flush=True)
    if any(r['status'] != 'complete_page' for r in rows if r['source'] in ('classic', 'gushiwen')):
        raise SystemExit('Incomplete core comparison: inspect saved report')


if __name__ == '__main__':
    main()
