#!/usr/bin/env python3
"""Generate 经部 (Confucian classics / 十三经) content from Wikisource.

Usage:
    python scripts/generate_jingbu.py --all
    python scripts/generate_jingbu.py --text zhou-yi
    python scripts/generate_jingbu.py --list
    python scripts/generate_jingbu.py --dry-run --all
"""

from __future__ import annotations

import argparse, json, re, sys, time, urllib.request, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext

ROOT = Path(__file__).resolve().parents[1]
JING_DIR = ROOT / "content" / "posts" / "confucius"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"


# ── Text metadata ───────────────────────────────────────────────────

TEXTS: dict[str, dict] = {
    "zhou-yi": {
        "slug": "zhou-yi", "title": "周易", "wiki_title": "周易",
        "type": "subpages", "wiki_prefix": "周易/",
        "summary": "周易，又称易经，中国最古老的文献之一，儒家五经之首。",
        "tags": ["周易", "易经", "经部"],
    },
    "shang-shu": {
        "slug": "shang-shu", "title": "尚书", "wiki_title": "尚書",
        "type": "subpages", "wiki_prefix": "尚書/",
        "summary": "尚书，中国最早的历史文献汇编，儒家五经之一。",
        "tags": ["尚书", "经部"],
    },
    "shi-jing": {
        "slug": "shi-jing", "title": "诗经", "wiki_title": "詩經",
        "type": "subpages", "wiki_prefix": "詩經/",
        "summary": "诗经，中国最早的诗歌总集，收诗305首，儒家五经之一。",
        "tags": ["诗经", "经部"],
    },
    "zhou-li": {
        "slug": "zhou-li", "title": "周礼", "wiki_title": "周禮",
        "type": "subpages", "wiki_prefix": "周禮/",
        "summary": "周礼，中国古代官制典籍，记载周代官制体系。",
        "tags": ["周礼", "经部"],
    },
    "yi-li": {
        "slug": "yi-li", "title": "仪礼", "wiki_title": "儀禮",
        "type": "subpages", "wiki_prefix": "儀禮/",
        "summary": "仪礼，记载周代礼仪制度，现存十七篇。",
        "tags": ["仪礼", "经部"],
    },
    "li-ji": {
        "slug": "li-ji", "title": "礼记", "wiki_title": "禮記",
        "type": "subpages", "wiki_prefix": "禮記/",
        "summary": "礼记，儒家礼学文献汇编，四十九篇。",
        "tags": ["礼记", "经部"],
    },
    "chun-qiu-zuo-zhuan": {
        "slug": "chun-qiu-zuo-zhuan", "title": "春秋左传", "wiki_title": "春秋左氏傳",
        "type": "subpages", "wiki_prefix": "春秋左氏傳/",
        "summary": "春秋左传，简称左传，左丘明撰，春秋三传之一。",
        "tags": ["左传", "春秋", "经部"],
    },
    "chun-qiu-gong-yang": {
        "slug": "chun-qiu-gong-yang", "title": "春秋公羊传", "wiki_title": "春秋公羊傳",
        "type": "single",
        "summary": "春秋公羊传，公羊高撰，以阐发春秋微言大义为主。",
        "tags": ["公羊传", "春秋", "经部"],
    },
    "chun-qiu-gu-liang": {
        "slug": "chun-qiu-gu-liang", "title": "春秋谷梁传", "wiki_title": "春秋穀梁傳",
        "type": "subpages", "wiki_prefix": "春秋穀梁傳/",
        "summary": "春秋谷梁传，谷梁赤撰，春秋三传之一。",
        "tags": ["谷梁传", "春秋", "经部"],
    },
    "xiao-jing": {
        "slug": "xiao-jing", "title": "孝经", "wiki_title": "今文孝經",
        "type": "single",
        "summary": "孝经，儒家论孝道经典，传为孔子所作。",
        "tags": ["孝经", "经部"],
    },
    "er-ya": {
        "slug": "er-ya", "title": "尔雅", "wiki_title": "爾雅",
        "type": "single",
        "summary": "尔雅，中国最早的辞书，十三经之一。",
        "tags": ["尔雅", "经部"],
    },
}


# ── Wikisource API helpers ────────────────────────────────────────

def api_query(params: dict) -> dict:
    base = "https://zh.wikisource.org/w/api.php?format=json&"
    url = base + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_raw(title: str, retries: int = 3) -> str:
    url = "https://zh.wikisource.org/w/index.php?title={}&action=raw".format(
        urllib.parse.quote(title))
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise


def discover_subpages(prefix: str) -> list[str]:
    """Return sorted list of sub-page titles under the given prefix."""
    pages: list[str] = []
    params = {
        "action": "query",
        "list": "allpages",
        "apprefix": prefix,
        "aplimit": 500,
    }
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
    """Post-process cleaned wikitext."""
    text = re.sub(r'</?onlyinclude>', '', text)
    text = re.sub(r'</?poem>', '', text)
    text = re.sub(r'^Category:.*$', '', text, flags=re.M)
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    text = text.replace('{{', '')
    text = text.replace('}}', '')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Output helpers ─────────────────────────────────────────────────

def front_matter(title: str, summary: str, weight: int,
                 tags: list[str] | None = None,
                 categories: list[str] | None = None) -> str:
    tags = tags or ["经部"]
    categories = categories or ["经部"]
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
    fm = front_matter(title, summary, weight, tags, categories=["经部"])
    (directory / "_index.md").write_text(fm, encoding="utf-8")


def write_page(path: Path, title: str, summary: str, weight: int,
               body: str, tags: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = front_matter(title, summary, weight, tags, categories=["经部"])
    path.write_text(fm + body + "\n", encoding="utf-8")


# ── Generators ─────────────────────────────────────────────────────

def generate_subpages(text_id: str, dry_run: bool = False) -> tuple[int, int]:
    """Generate a text from Api-discovered sub-pages."""
    info = TEXTS[text_id]
    out_dir = JING_DIR / info["slug"]
    prefix = info["wiki_prefix"]

    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']})")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    pages = discover_subpages(prefix)
    print(f"  Found {len(pages)} sub-pages")

    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])

    success, fail = 0, 0
    for i, page_title in enumerate(pages, start=1):
        # Derive chapter name from page title
        chapter_name = page_title.replace(prefix, "")
        out_file = out_dir / f"{info['slug']}-{i:03d}.md"

        if out_file.exists():
            print(f"  [{i:03d}/{len(pages)}] {chapter_name} — Skipping (exists)")
            success += 1
            continue

        try:
            raw = fetch_raw(page_title)
            body = final_clean(clean_wikitext(raw))
            if not body.strip():
                print(f"  [{i:03d}/{len(pages)}] {chapter_name}: EMPTY")
                fail += 1
                continue

            if not dry_run:
                write_page(out_file, chapter_name, f"{info['title']}：{chapter_name}", i, body, info["tags"])
            print(f"  [{i:03d}/{len(pages)}] {chapter_name} ({len(body)} chars)")
            success += 1
            time.sleep(1)
        except Exception as e:
            print(f"  [{i:03d}/{len(pages)}] {chapter_name}: FAILED ({e})")
            fail += 1

    print(f"  Done: {success} success, {fail} failed")
    return success, fail


def generate_single(text_id: str, dry_run: bool = False) -> tuple[int, int]:
    """Generate a text from a single Wikisource page."""
    info = TEXTS[text_id]
    out_dir = JING_DIR / info["slug"]

    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']})")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    raw = fetch_raw(info["wiki_title"])
    body = final_clean(clean_wikitext(raw))

    out_file = out_dir / f"{info['slug']}.md"
    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])
        write_page(out_file, info["title"], info["summary"], 1, body, info["tags"])
    print(f"  OK ({len(body)} chars) -> {out_file.relative_to(ROOT)}")

    return 1, 0


# ── Main ───────────────────────────────────────────────────────────

GENERATORS = {
    "zhou-yi": lambda dry_run=False: generate_subpages("zhou-yi", dry_run),
    "shang-shu": lambda dry_run=False: generate_subpages("shang-shu", dry_run),
    "shi-jing": lambda dry_run=False: generate_subpages("shi-jing", dry_run),
    "zhou-li": lambda dry_run=False: generate_subpages("zhou-li", dry_run),
    "yi-li": lambda dry_run=False: generate_subpages("yi-li", dry_run),
    "li-ji": lambda dry_run=False: generate_subpages("li-ji", dry_run),
    "chun-qiu-zuo-zhuan": lambda dry_run=False: generate_subpages("chun-qiu-zuo-zhuan", dry_run),
    "chun-qiu-gong-yang": lambda dry_run=False: generate_single("chun-qiu-gong-yang", dry_run),
    "chun-qiu-gu-liang": lambda dry_run=False: generate_subpages("chun-qiu-gu-liang", dry_run),
    "xiao-jing": lambda dry_run=False: generate_single("xiao-jing", dry_run),
    "er-ya": lambda dry_run=False: generate_single("er-ya", dry_run),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="Generate a single text by id")
    parser.add_argument("--all", action="store_true", help="Generate all texts")
    parser.add_argument("--list", action="store_true", help="List available texts")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list:
        for tid in GENERATORS:
            info = TEXTS[tid]
            print(f"  {tid:24s} {info['title']:8s} [{info['type']:10s}] — {info['summary'][:60]}")
        return

    if args.text:
        if args.text not in GENERATORS:
            print(f"Unknown text: {args.text}")
            print(f"Available: {', '.join(sorted(GENERATORS))}")
            return
        GENERATORS[args.text](dry_run=args.dry_run)
    elif args.all:
        total_ok, total_fail = 0, 0
        for tid in GENERATORS:
            ok, fail = GENERATORS[tid](dry_run=args.dry_run)
            total_ok += ok
            total_fail += fail
        print(f"\n{'='*60}")
        print(f"ALL DONE: {total_ok} success, {total_fail} failed")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
