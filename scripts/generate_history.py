#!/usr/bin/env python3
"""Unified generator for 二十四史 from Wikisource.

Usage:
    python scripts/generate_history.py --all          # Generate all histories
    python scripts/generate_history.py --history shi-ji  # Single history
    python scripts/generate_history.py --list            # List available histories
    python scripts/generate_history.py --discover han-shu  # Discover volume pages
"""

from __future__ import annotations

import argparse, json, re, sys, time, urllib.request, urllib.parse
from pathlib import Path
from collections import OrderedDict

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext

ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "content" / "posts" / "history"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"


# ── History metadata ──────────────────────────────────────────────

HISTORIES: dict[str, dict] = {
    "shi-ji": {
        "slug": "shi-ji", "title": "史记", "wiki_title": "史記",
        "total_volumes": 130, "author": "司马迁", "dynasty": "西汉",
        "summary": "史记一百三十卷，汉司马迁撰。",
        "tags": ["史记", "西汉", "司马迁"],
    },
    "han-shu": {
        "slug": "han-shu", "title": "汉书", "wiki_title": "漢書",
        "total_volumes": 100, "author": "班固", "dynasty": "东汉",
        "summary": "汉书一百卷，汉班固撰。",
        "tags": ["汉书", "东汉", "班固"],
    },
    "hou-han-shu": {
        "slug": "hou-han-shu", "title": "后汉书", "wiki_title": "後漢書",
        "total_volumes": 120, "author": "范晔", "dynasty": "南朝宋",
        "summary": "后汉书一百二十卷，南朝宋范晔撰。",
        "tags": ["后汉书", "南朝宋", "范晔"],
    },
    "san-guo-zhi": {
        "slug": "san-guo-zhi", "title": "三国志", "wiki_title": "三國志",
        "total_volumes": 65, "author": "陈寿", "dynasty": "西晋",
        "summary": "三国志六十五卷，晋陈寿撰。",
        "tags": ["三国志", "西晋", "陈寿"],
    },
    "jin-shu": {
        "slug": "jin-shu", "title": "晋书", "wiki_title": "晉書",
        "total_volumes": 130, "author": "房玄龄等", "dynasty": "唐",
        "summary": "晋书一百三十卷，唐房玄龄等奉敕撰。",
        "tags": ["晋书", "唐", "房玄龄"],
    },
    "song-shu": {
        "slug": "song-shu", "title": "宋书", "wiki_title": "宋書",
        "total_volumes": 100, "author": "沈约", "dynasty": "南朝梁",
        "summary": "宋书一百卷，南朝梁沈约撰。",
        "tags": ["宋书", "南朝梁", "沈约"],
    },
    "nan-qi-shu": {
        "slug": "nan-qi-shu", "title": "南齐书", "wiki_title": "南齊書",
        "total_volumes": 59, "author": "萧子显", "dynasty": "南朝梁",
        "summary": "南齐书五十九卷，南朝梁萧子显撰。",
        "tags": ["南齐书", "南朝梁", "萧子显"],
    },
    "liang-shu": {
        "slug": "liang-shu", "title": "梁书", "wiki_title": "梁書",
        "total_volumes": 56, "author": "姚思廉", "dynasty": "唐",
        "summary": "梁书五十六卷，唐姚思廉撰。",
        "tags": ["梁书", "唐", "姚思廉"],
    },
    "chen-shu": {
        "slug": "chen-shu", "title": "陈书", "wiki_title": "陳書",
        "total_volumes": 36, "author": "姚思廉", "dynasty": "唐",
        "summary": "陈书三十六卷，唐姚思廉撰。",
        "tags": ["陈书", "唐", "姚思廉"],
    },
    "wei-shu": {
        "slug": "wei-shu", "title": "魏书", "wiki_title": "魏書",
        "total_volumes": 114, "author": "魏收", "dynasty": "北齐",
        "summary": "魏书一百一十四卷，北齐魏收撰。",
        "tags": ["魏书", "北齐", "魏收"],
    },
    "bei-qi-shu": {
        "slug": "bei-qi-shu", "title": "北齐书", "wiki_title": "北齊書",
        "total_volumes": 50, "author": "李百药", "dynasty": "唐",
        "summary": "北齐书五十卷，唐李百药撰。",
        "tags": ["北齐书", "唐", "李百药"],
    },
    "zhou-shu": {
        "slug": "zhou-shu", "title": "周书", "wiki_title": "周書",
        "total_volumes": 50, "author": "令狐德棻等", "dynasty": "唐",
        "summary": "周书五十卷，唐令狐德棻等撰。",
        "tags": ["周书", "唐", "令狐德棻"],
    },
    "sui-shu": {
        "slug": "sui-shu", "title": "隋书", "wiki_title": "隋書",
        "total_volumes": 85, "author": "魏徵等", "dynasty": "唐",
        "summary": "隋书八十五卷，唐魏徵等撰。",
        "tags": ["隋书", "唐", "魏徵"],
    },
    "nan-shi": {
        "slug": "nan-shi", "title": "南史", "wiki_title": "南史",
        "total_volumes": 80, "author": "李延寿", "dynasty": "唐",
        "summary": "南史八十卷，唐李延寿撰。",
        "tags": ["南史", "唐", "李延寿"],
    },
    "bei-shi": {
        "slug": "bei-shi", "title": "北史", "wiki_title": "北史",
        "total_volumes": 100, "author": "李延寿", "dynasty": "唐",
        "summary": "北史一百卷，唐李延寿撰。",
        "tags": ["北史", "唐", "李延寿"],
    },
    "jiu-tang-shu": {
        "slug": "jiu-tang-shu", "title": "旧唐书", "wiki_title": "舊唐書",
        "total_volumes": 200, "author": "刘昫等", "dynasty": "后晋",
        "summary": "旧唐书二百卷，后晋刘昫等撰。",
        "tags": ["旧唐书", "后晋", "刘昫"],
    },
    "xin-tang-shu": {
        "slug": "xin-tang-shu", "title": "新唐书", "wiki_title": "新唐書",
        "total_volumes": 225, "author": "欧阳修、宋祁", "dynasty": "北宋",
        "summary": "新唐书二百二十五卷，宋欧阳修、宋祁等撰。",
        "tags": ["新唐书", "北宋", "欧阳修"],
    },
    "jiu-wu-dai-shi": {
        "slug": "jiu-wu-dai-shi", "title": "旧五代史", "wiki_title": "舊五代史",
        "total_volumes": 150, "author": "薛居正等", "dynasty": "北宋",
        "summary": "旧五代史一百五十卷，宋薛居正等撰。",
        "tags": ["旧五代史", "北宋", "薛居正"],
    },
    "xin-wu-dai-shi": {
        "slug": "xin-wu-dai-shi", "title": "新五代史", "wiki_title": "新五代史",
        "total_volumes": 74, "author": "欧阳修", "dynasty": "北宋",
        "summary": "新五代史七十四卷，宋欧阳修撰。",
        "tags": ["新五代史", "北宋", "欧阳修"],
    },
    "song-shi": {
        "slug": "song-shi", "title": "宋史", "wiki_title": "宋史",
        "total_volumes": 496, "author": "脱脱等", "dynasty": "元",
        "summary": "宋史四百九十六卷，元脱脱等撰。",
        "tags": ["宋史", "元", "脱脱"],
    },
    "liao-shi": {
        "slug": "liao-shi", "title": "辽史", "wiki_title": "遼史",
        "total_volumes": 116, "author": "脱脱等", "dynasty": "元",
        "summary": "辽史一百一十六卷，元脱脱等撰。",
        "tags": ["辽史", "元", "脱脱"],
    },
    "jin-shi": {
        "slug": "jin-shi", "title": "金史", "wiki_title": "金史",
        "total_volumes": 135, "author": "脱脱等", "dynasty": "元",
        "summary": "金史一百三十五卷，元脱脱等撰。",
        "tags": ["金史", "元", "脱脱"],
    },
    "yuan-shi": {
        "slug": "yuan-shi", "title": "元史", "wiki_title": "元史",
        "total_volumes": 210, "author": "宋濂等", "dynasty": "明",
        "summary": "元史二百一十卷，明宋濂等撰。",
        "tags": ["元史", "明", "宋濂"],
    },
    "ming-shi": {
        "slug": "ming-shi", "title": "明史", "wiki_title": "明史",
        "total_volumes": 332, "author": "张廷玉等", "dynasty": "清",
        "summary": "明史三百三十二卷，清张廷玉等撰。",
        "tags": ["明史", "清", "张廷玉"],
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


def discover_pages(wiki_title: str) -> dict[int, list[str]]:
    """Return {volume_number: [page_titles]} using the API."""
    prefix = f"{wiki_title}/卷"
    pages: dict[int, list[str]] = OrderedDict()

    params = {
        "action": "query",
        "list": "allpages",
        "apprefix": prefix,
        "aplimit": 500,
    }

    while True:
        data = api_query(params)
        for p in data.get("query", {}).get("allpages", []):
            title = p["title"]
            # Extract volume number: 漢書/卷001上 → vol 1
            m = re.match(r'.+/卷0*(\d+)([上下中甲乙丙丁])?$', title)
            if m:
                vol = int(m.group(1))
                pages.setdefault(vol, []).append(title)

        if "continue" in data:
            params.update(data["continue"])
        else:
            break

    return pages


# ── Output helpers ────────────────────────────────────────────────

def volume_group_dir(vol: int, total: int, chunk: int = 30) -> str:
    start = ((vol - 1) // chunk) * chunk + 1
    end = min(start + chunk - 1, total)
    return f"{start:03d}-{end:03d}"


def front_matter(title: str, summary: str, weight: int, tags: list[str]) -> str:
    tags_str = json.dumps(tags, ensure_ascii=False)
    return f"""---
title: "{title}"
date: 2026-05-19
weight: {weight}
tags: {tags_str}
categories: ["史部"]
draft: false
summary: "{summary}"
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


# ── Main logic ────────────────────────────────────────────────────

def generate_history(hist_id: str, dry_run: bool = False) -> tuple[int, int]:
    """Generate one history. Returns (success_count, fail_count)."""
    if hist_id not in HISTORIES:
        print(f"Unknown history: {hist_id}")
        return 0, 0

    h = HISTORIES[hist_id]
    slug, title, wiki_title = h["slug"], h["title"], h["wiki_title"]
    total = h["total_volumes"]
    out_dir = OUT_BASE / slug

    print(f"\n{'='*60}")
    print(f"Generating {title} ({wiki_title}): {total} volumes")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    # Discover volume pages
    print("Discovering volume pages via API...")
    pages = discover_pages(wiki_title)
    print(f"  Found {len(pages)} volume groups on Wikisource")

    success, fail = 0, 0

    for vol in sorted(pages.keys()):
        vol_pages = pages[vol]
        group = volume_group_dir(vol, total)
        out_file = out_dir / group / f"{slug}-{vol:03d}.md"

        if out_file.exists():
            print(f"  [{vol:03d}/{total}] Skipping (exists)")
            success += 1
            continue

        # Fetch and combine all pages for this volume
        parts = []
        for page_title in vol_pages:
            try:
                raw = fetch_raw(page_title)
                clean = clean_wikitext(raw)
                if clean:
                    parts.append(clean)
            except Exception as e:
                print(f"  [{vol:03d}/{total}] FAILED {page_title}: {e}")
                fail += 1
                break
        else:
            if not parts:
                print(f"  [{vol:03d}/{total}] EMPTY content")
                fail += 1
                continue

            body = "\n\n".join(parts)
            suffix = "上" if len(vol_pages) > 1 else ""
            display_title = f"{title} 卷{vol}{suffix}"
            summary = f"{title}卷{vol}。{h['summary'][:30]}..."
            fm = front_matter(display_title, summary, vol, h["tags"])
            content = fm + body + "\n"

            if not dry_run:
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(content, encoding="utf-8")

            print(f"  [{vol:03d}/{total}] OK ({len(body)} chars) -> {out_file.relative_to(ROOT)}")
            success += 1
            time.sleep(1.5)  # be polite to Wikisource, avoid 429

    print(f"\n  Done: {success} success, {fail} failed")

    # Check for missing volumes
    missing = set(range(1, total + 1)) - set(pages.keys())
    if missing:
        print(f"  Missing volumes on Wikisource: {sorted(missing)[:20]}...")

    return success, fail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", help="Generate a single history by slug")
    parser.add_argument("--all", action="store_true", help="Generate all histories")
    parser.add_argument("--list", action="store_true", help="List available histories")
    parser.add_argument("--discover", help="Show discovered volumes for a history")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list:
        for hid, h in HISTORIES.items():
            print(f"  {hid:20s} {h['title']:8s} ({h['total_volumes']:3d}卷) — {h['author']} ({h['dynasty']})")
        return

    if args.discover:
        if args.discover not in HISTORIES:
            print(f"Unknown history: {args.discover}")
            return
        h = HISTORIES[args.discover]
        pages = discover_pages(h["wiki_title"])
        print(f"{h['title']} ({h['wiki_title']}): {len(pages)} volumes found")
        for vol, pts in sorted(pages.items())[:10]:
            print(f"  Vol {vol}: {pts}")
        if len(pages) > 10:
            print(f"  ... and {len(pages) - 10} more")
        print(f"  Expected: {h['total_volumes']}, Found: {len(pages)}, Missing: {h['total_volumes'] - len(pages)}")
        return

    if args.history:
        generate_history(args.history, dry_run=args.dry_run)
    elif args.all:
        total_ok, total_fail = 0, 0
        for hid in HISTORIES:
            ok, fail = generate_history(hid, dry_run=args.dry_run)
            total_ok += ok
            total_fail += fail
        print(f"\n{'='*60}")
        print(f"ALL DONE: {total_ok} success, {total_fail} failed")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
