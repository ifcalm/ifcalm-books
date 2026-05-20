#!/usr/bin/env python3
"""Generate 诸子百家 content from Wikisource.

Usage:
    python scripts/generate_zhuzi.py --all
    python scripts/generate_zhuzi.py --text xunzi
    python scripts/generate_zhuzi.py --list
"""

from __future__ import annotations

import argparse, json, re, sys, time, urllib.request, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext

ROOT = Path(__file__).resolve().parents[1]
ZHUZI_DIR = ROOT / "content" / "posts" / "zhuzi"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"

TEXTS: dict[str, dict] = {
    "xunzi":         {"slug": "xunzi", "title": "荀子", "wiki_title": "荀子", "type": "subpages", "wiki_prefix": "荀子/", "summary": "荀子三十二篇，战国荀况撰，儒家重要典籍。", "tags": ["荀子", "儒家", "诸子"]},
    "mozi":          {"slug": "mozi", "title": "墨子", "wiki_title": "墨子", "type": "subpages", "wiki_prefix": "墨子/", "summary": "墨子五十三篇，战国墨翟及其弟子撰，墨家经典。", "tags": ["墨子", "墨家", "诸子"]},
    "hanfeizi":      {"slug": "hanfeizi", "title": "韩非子", "wiki_title": "韓非子", "type": "subpages", "wiki_prefix": "韓非子/", "summary": "韩非子五十五篇，战国韩非撰，法家集大成之作。", "tags": ["韩非子", "法家", "诸子"]},
    "sunzi-bingfa":  {"slug": "sunzi-bingfa", "title": "孙子兵法", "wiki_title": "孫子兵法", "type": "single", "summary": "孙子兵法十三篇，春秋孙武撰，兵家经典。", "tags": ["孙子兵法", "兵家", "诸子"]},
    "shangjun-shu":  {"slug": "shangjun-shu", "title": "商君书", "wiki_title": "商君書", "type": "subpages", "wiki_prefix": "商君書/", "summary": "商君书二十六篇，战国商鞅及其后学撰，法家著作。", "tags": ["商君书", "法家", "诸子"]},
    "guiguzi":       {"slug": "guiguzi", "title": "鬼谷子", "wiki_title": "鬼谷子", "type": "subpages", "wiki_prefix": "鬼谷子/", "summary": "鬼谷子十四篇，传为战国鬼谷子撰，纵横家经典。", "tags": ["鬼谷子", "纵横家", "诸子"]},
    "lvshi-chunqiu": {"slug": "lvshi-chunqiu", "title": "吕氏春秋", "wiki_title": "呂氏春秋", "type": "subpages", "wiki_prefix": "呂氏春秋/", "summary": "吕氏春秋二十六卷，秦吕不韦编，杂家代表作。", "tags": ["吕氏春秋", "杂家", "诸子"]},
    "huainanzi":     {"slug": "huainanzi", "title": "淮南子", "wiki_title": "淮南子", "type": "subpages", "wiki_prefix": "淮南子/", "summary": "淮南子二十一卷，汉刘安编，杂家代表作。", "tags": ["淮南子", "杂家", "诸子"]},
    "gongsun-longzi":{"slug": "gongsun-longzi", "title": "公孙龙子", "wiki_title": "公孫龍子", "type": "subpages", "wiki_prefix": "公孫龍子/", "summary": "公孙龙子六篇，战国公孙龙撰，名家经典。", "tags": ["公孙龙子", "名家", "诸子"]},
    "wenzi":         {"slug": "wenzi", "title": "文子", "wiki_title": "文子", "type": "subpages", "wiki_prefix": "文子/", "summary": "文子十二卷，传为战国文子撰，道家经典。", "tags": ["文子", "道家", "诸子"]},
}


def api_query(params: dict) -> dict:
    base = "https://zh.wikisource.org/w/api.php?format=json&"
    url = base + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_raw(title: str, retries: int = 3) -> str:
    url = "https://zh.wikisource.org/w/index.php?title={}&action=raw".format(urllib.parse.quote(title))
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(5 * (attempt + 1))
            else:
                raise


def discover_subpages(prefix: str) -> list[str]:
    pages: list[str] = []
    params = {"action": "query", "list": "allpages", "apprefix": prefix, "aplimit": 500}
    while True:
        data = api_query(params)
        for p in data.get("query", {}).get("allpages", []):
            pages.append(p["title"])
        if "continue" in data:
            params.update(data["continue"])
        else:
            break
    return sorted(pages)


def final_clean(text: str) -> str:
    text = re.sub(r'</?onlyinclude>', '', text)
    text = re.sub(r'</?poem>', '', text)
    text = re.sub(r'^Category:.*$', '', text, flags=re.M)
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    text = text.replace('{{', '')
    text = text.replace('}}', '')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def front_matter(title: str, summary: str, weight: int,
                 tags: list[str] | None = None,
                 categories: list[str] | None = None) -> str:
    tags = tags or ["诸子"]
    categories = categories or ["子部", "诸子"]
    return f"""---
title: "{title}"
date: 2026-05-20
weight: {weight}
tags: {json.dumps(tags, ensure_ascii=False)}
categories: {json.dumps(categories, ensure_ascii=False)}
draft: false
summary: "{summary}"
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def write_index(directory: Path, title: str, summary: str, weight: int,
                tags: list[str] | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "_index.md").write_text(
        front_matter(title, summary, weight, tags, ["子部", "诸子"]), encoding="utf-8")


def write_page(path: Path, title: str, summary: str, weight: int,
               body: str, tags: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = front_matter(title, summary, weight, tags, ["子部", "诸子"])
    path.write_text(fm + body + "\n", encoding="utf-8")


def generate_subpages(text_id: str, dry_run: bool = False) -> tuple[int, int]:
    info = TEXTS[text_id]
    out_dir = ZHUZI_DIR / info["slug"]
    prefix = info["wiki_prefix"]
    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']}) -> {out_dir.relative_to(ROOT)}")
    pages = discover_subpages(prefix)
    print(f"  Found {len(pages)} sub-pages")
    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])
    success, fail = 0, 0
    for i, page_title in enumerate(pages, start=1):
        chapter_name = page_title.replace(prefix, "")
        out_file = out_dir / f"{info['slug']}-{i:03d}.md"
        if out_file.exists():
            success += 1; continue
        try:
            raw = fetch_raw(page_title)
            body = final_clean(clean_wikitext(raw))
            if not body.strip():
                fail += 1; continue
            if not dry_run:
                write_page(out_file, chapter_name, f"{info['title']}：{chapter_name}", i, body, info["tags"])
            print(f"  [{i:03d}/{len(pages)}] {chapter_name} ({len(body)} chars)")
            success += 1; time.sleep(1)
        except Exception as e:
            print(f"  [{i:03d}/{len(pages)}] {chapter_name}: FAILED ({e})")
            fail += 1
    print(f"  Done: {success} ok, {fail} fail")
    return success, fail


def generate_single(text_id: str, dry_run: bool = False) -> tuple[int, int]:
    info = TEXTS[text_id]
    out_dir = ZHUZI_DIR / info["slug"]
    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']}) -> {out_dir.relative_to(ROOT)}")
    raw = fetch_raw(info["wiki_title"])
    body = final_clean(clean_wikitext(raw))
    out_file = out_dir / f"{info['slug']}.md"
    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])
        write_page(out_file, info["title"], info["summary"], 1, body, info["tags"])
    print(f"  OK ({len(body)} chars)")
    return 1, 0


def _make_gen(tid):
    if TEXTS[tid]["type"] == "subpages":
        return lambda dry_run=False: generate_subpages(tid, dry_run)
    return lambda dry_run=False: generate_single(tid, dry_run)

GENERATORS = {k: _make_gen(k) for k in TEXTS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="Single text by id")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.list:
        for tid, info in TEXTS.items():
            print(f"  {tid:20s} {info['title']:8s} [{info['type']:10s}]")
        return
    if args.text:
        gen = GENERATORS.get(args.text)
        if not gen: return print(f"Unknown: {args.text}")
        gen(dry_run=args.dry_run)
    elif args.all:
        ok = fail = 0
        for tid in TEXTS:
            o, f = GENERATORS[tid](dry_run=args.dry_run)
            ok += o; fail += f
        print(f"\n{'='*60}\nALL DONE: {ok} ok, {fail} fail")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
