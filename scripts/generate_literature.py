#!/usr/bin/env python3
"""Generate 集部 (literature collections) content from Wikisource.

Usage:
    python scripts/generate_literature.py --all          # Generate all texts
    python scripts/generate_literature.py --text renjian-cihua  # Single text
    python scripts/generate_literature.py --phase 2      # Phase 2 texts
    python scripts/generate_literature.py --list         # List available texts
    python scripts/generate_literature.py --dry-run --all
"""

from __future__ import annotations

import argparse, json, re, sys, time, urllib.request, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext


def final_clean(text: str) -> str:
    """Post-process cleaned wikitext to remove remaining artifacts."""
    # Remove <onlyinclude>/</onlyinclude> tags
    text = re.sub(r'</?onlyinclude>', '', text)
    # Remove <poem>/</poem> tags
    text = re.sub(r'</?poem>', '', text)
    # Remove Category: links left behind by wikilink processing
    text = re.sub(r'^Category:.*$', '', text, flags=re.M)
    # Remove unprocessed inline templates
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    # Remove stray template braces
    text = text.replace('{{', '')
    text = text.replace('}}', '')
    # Normalize blank lines after removals
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

ROOT = Path(__file__).resolve().parents[1]
LIT_DIR = ROOT / "content" / "posts" / "literature"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"


# ── Text metadata ───────────────────────────────────────────────────

TEXTS: dict[str, dict] = {
    "renjian-cihua": {
        "slug": "ren-jian-ci-hua",
        "title": "人间词话",
        "wiki_title": "人間詞話",
        "category": "shiwenping",
        "phase": 2,
        "summary": "人间词话，王国维撰，中国近代词学批评经典。",
        "tags": ["人间词话", "词话", "王国维"],
    },
    "shi-pin": {
        "slug": "shi-pin",
        "title": "诗品",
        "wiki_title": "詩品",
        "category": "shiwenping",
        "phase": 2,
        "summary": "诗品，南朝梁钟嵘撰，品评汉魏至南朝梁一百二十余家五言诗。",
        "tags": ["诗品", "诗文评", "钟嵘"],
    },
    "wenxin-diaolong": {
        "slug": "wenxin-diaolong",
        "title": "文心雕龙",
        "wiki_title": "文心雕龍",
        "category": "shiwenping",
        "phase": 2,
        "summary": "文心雕龙，南朝梁刘勰撰，中国第一部系统文学理论专著。",
        "tags": ["文心雕龙", "诗文评", "刘勰"],
    },
    "chu-ci": {
        "slug": "chu-ci",
        "title": "楚辞",
        "wiki_title": "楚辭",
        "category": "chuci",
        "phase": 2,
        "summary": "楚辞，西汉刘向辑录屈原、宋玉等人作品而成。",
        "tags": ["楚辞", "屈原", "宋玉"],
    },
    "guwen-guanzhi": {
        "slug": "gu-wen-guan-zhi",
        "title": "古文观止",
        "wiki_title": "古文觀止",
        "category": "zongji",
        "phase": 3,
        "vol_pattern": r'卷0*(\d+)',
        "total_volumes": 12,
        "summary": "古文观止，清吴楚材、吴调侯编选，历代古文精华总集。",
        "tags": ["古文观止", "总集", "吴楚材"],
    },
    "yu-tai-xin-yong": {
        "slug": "yu-tai-xin-yong",
        "title": "玉台新咏",
        "wiki_title": "玉臺新詠",
        "category": "zongji",
        "phase": 3,
        "vol_pattern": r'0*(\d+)卷',
        "total_volumes": 10,
        "summary": "玉台新咏，南朝陈徐陵编，收录汉至南朝梁诗歌。",
        "tags": ["玉台新咏", "总集", "徐陵"],
    },
    "sui-yuan-shi-hua": {
        "slug": "sui-yuan-shi-hua",
        "title": "随园诗话",
        "wiki_title": "隨園詩話",
        "category": "shiwenping",
        "phase": 3,
        "vol_pattern": r'0*(\d+)$',
        "total_volumes": 16,
        "summary": "随园诗话，清袁枚撰，清代重要诗话著作。",
        "tags": ["随园诗话", "诗文评", "袁枚"],
    },
    "hua-jian-ji": {
        "slug": "hua-jian-ji",
        "title": "花间集",
        "wiki_title": "花間集",
        "category": "ciqu",
        "phase": 3,
        "summary": "花间集，五代后蜀赵崇祚编，中国最早的词总集。",
        "tags": ["花间集", "词", "赵崇祚"],
    },
    "wen-xuan": {
        "slug": "wen-xuan",
        "title": "文选",
        "wiki_title": "昭明文選",
        "category": "zongji",
        "phase": 3,
        "vol_pattern": r'卷0*(\d+)',
        "total_volumes": 60,
        "summary": "文选，南朝梁萧统编，中国现存最早的诗文总集。",
        "tags": ["文选", "总集", "萧统"],
    },
    "yue-fu-shi-ji": {
        "slug": "yue-fu-shi-ji",
        "title": "乐府诗集",
        "wiki_title": "樂府詩集",
        "category": "zongji",
        "phase": 3,
        "vol_pattern": r'0*(\d+)卷',
        "total_volumes": 100,
        "summary": "乐府诗集，宋郭茂倩编，收录上古至唐五代乐府诗。",
        "tags": ["乐府诗集", "总集", "郭茂倩"],
    },
    "du-fu": {
        "slug": "du-fu",
        "title": "杜工部集",
        "wiki_title": "分门集註杜工部詩",
        "category": "bieji",
        "phase": 4,
        "total_volumes": 25,
        "summary": "分门集註杜工部詩，唐杜甫撰，宋王洙集注。四部丛刊本。",
        "tags": ["杜工部集", "杜甫", "别集"],
    },
    "li-bai": {
        "slug": "li-bai",
        "title": "李太白文集",
        "wiki_title": "李太白文集",
        "category": "bieji",
        "phase": 4,
        "total_volumes": 31,
        "summary": "李太白文集三十卷，唐李白撰。四库全书文渊阁本。",
        "tags": ["李太白文集", "李白", "别集"],
    },
}

# 楚辞 chapter mapping: (vol, slug, wiki_title)
CHUCI_CHAPTERS: list[tuple[int, str, str]] = [
    (1, "离骚", "離騷"),
    (2, "九歌", "九歌"),
    (3, "天问", "天問"),
    (4, "九章", "楚辭/九章"),
    (5, "远游", "楚辭/遠遊"),
    (6, "卜居", "卜居 (屈原)"),
    (7, "渔父", "漁父"),
    (8, "九辩", "九辯"),
    (9, "招魂", "楚辭/招䰟"),
    (10, "大招", "楚辭/大招"),
    (11, "惜誓", "楚辭/惜誓"),
    (12, "招隐士", "招隱士"),
    (13, "七谏", "楚辭/七諫"),
    (14, "哀时命", "楚辭/哀時命"),
    (15, "九怀", "九懷"),
    (16, "九叹", "九歎"),
    (17, "九思", "九思"),
]


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


def discover_subpages(prefix: str) -> list[tuple[str, str]]:
    """Return [(page_title, base_name)] for subpages under the given title prefix.

    Sorted by their appearance in the API.
    """
    pages: list[tuple[str, str]] = []
    params = {
        "action": "query",
        "list": "allpages",
        "apprefix": prefix + "/",
        "aplimit": 500,
    }

    while True:
        data = api_query(params)
        for p in data.get("query", {}).get("allpages", []):
            title = p["title"]
            # Extract base name after the prefix/
            base = title[len(prefix) + 1:]
            pages.append((title, base))

        if "continue" in data:
            params.update(data["continue"])
        else:
            break

    return pages


CHINESE_DIGITS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def chinese_vol_to_int(s: str) -> int:
    """Convert Chinese volume number to int. Handles 三十, 二十二, etc."""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in CHINESE_DIGITS:
        return CHINESE_DIGITS[s]
    if "十" in s:
        parts = s.split("十")
        tens = CHINESE_DIGITS.get(parts[0], 1) * 10 if parts[0] else 10
        ones = CHINESE_DIGITS.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens + ones
    return 1  # fallback


def discover_volume_pages(wiki_title: str, vol_pattern: str | None = None) -> dict[int, list[str]]:
    """Return {volume_number: [page_titles]} for multi-volume works.

    vol_pattern: regex pattern for the volume suffix after wiki_title/.
                 The first capture group is the volume number (int or Chinese).
    """
    pages: dict[int, list[str]] = {}
    if vol_pattern is None:
        vol_pattern = r'卷0*(\d+)'

    params = {
        "action": "query",
        "list": "allpages",
        "apprefix": wiki_title + "/",
        "aplimit": 500,
    }

    while True:
        data = api_query(params)
        for p in data.get("query", {}).get("allpages", []):
            title = p["title"]
            m = re.match(r'.+?/' + vol_pattern + r'$', title)
            if m:
                raw_vol = m.group(1)
                try:
                    vol = chinese_vol_to_int(raw_vol)
                except (ValueError, KeyError):
                    continue
                pages.setdefault(vol, []).append(title)

        if "continue" in data:
            params.update(data["continue"])
        else:
            break

    return pages


# ── Output helpers ─────────────────────────────────────────────────

def volume_group_dir(vol: int, total: int, chunk: int = 30) -> str:
    start = ((vol - 1) // chunk) * chunk + 1
    end = min(start + chunk - 1, total)
    return f"{start:03d}-{end:03d}"


def front_matter(title: str, summary: str, weight: int,
                 tags: list[str] | None = None,
                 categories: list[str] | None = None) -> str:
    tags = tags or ["集部"]
    categories = categories or ["集部"]
    tags_str = json.dumps(tags, ensure_ascii=False)
    cats_str = json.dumps(categories, ensure_ascii=False)
    return f"""---
title: "{title}"
date: 2026-05-20
weight: {weight}
tags: {tags_str}
categories: {cats_str}
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
    fm = front_matter(title, summary, weight, tags, categories=["集部"])
    (directory / "_index.md").write_text(fm, encoding="utf-8")


def write_page(path: Path, title: str, summary: str, weight: int,
               body: str, tags: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = front_matter(title, summary, weight, tags, categories=["集部"])
    content = fm + body + "\n"
    path.write_text(content, encoding="utf-8")


# ── Kanripo (GitHub) helpers ─────────────────────────────────────

KANRIPO_BASE = "https://raw.githubusercontent.com/kanripo"


def fetch_kanripo(repo: str, file_id: str) -> str:
    """Fetch a text file from a Kanripo GitHub repo."""
    url = f"{KANRIPO_BASE}/{repo}/master/{file_id}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def remove_balanced_parens(text: str) -> str:
    """Remove balanced (...) pairs, including content between them."""
    while "(" in text:
        start = text.index("(")
        depth = 0
        end = None
        for i in range(start, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            break
        text = text[:start] + text[end:]
    return text


def clean_kanripo_text(text: str, is_poetry: bool = False) -> str:
    """Clean Kanripo plain text into readable markdown.

    Preserves original line structure. Removes Org-mode metadata,
    page break markers, and paragraph markers.
    For prose: also removes inline annotations in parentheses.
    """
    # First remove Org-mode headers
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        if line.startswith("#"):
            continue
        # Remove page break markers
        line = re.sub(r'<pb:[^>]+>', '', line)
        # Remove stray paragraph markers
        line = line.replace("¶", "")
        cleaned_lines.append(line)

    body = "\n".join(cleaned_lines)

    if not is_poetry:
        # For prose: remove balanced parentheses (annotations)
        body = remove_balanced_parens(body)

    # Collapse runs of empty lines
    body = re.sub(r'\n{4,}', '\n\n\n', body)
    body = re.sub(r'\n{3}', '\n\n', body)

    if is_poetry:
        # Remove full-width indentation spaces from start of lines
        body = re.sub(r'^[　 ]+', '', body, flags=re.M)

    # Clean up full-width parentheses remnants
    body = body.replace("）", "").replace("（", "")
    # Clean up double-width spaces within lines
    body = re.sub(r'　{2,}', '', body)

    # Strip trailing whitespace per line
    body = "\n".join(line.strip() for line in body.splitlines())

    return body.strip()


# ── Kanripo-based generators ──────────────────────────────────────

KANRIPO_DUFU = {
    "repo": "KR4c0018",
    "title": "分门集註杜工部詩",
    "volumes": 25,
    "mapping": {i: f"KR4c0018_{i:03d}" for i in range(25)},
    # Volume 0 = preface/index, volumes 1-24 = content
}

KANRIPO_LIBAI = {
    "repo": "KR4c0012",
    "title": "李太白文集",
    "volumes": 31,  # 0 = 提要, 1-30 = 30 volumes
    "mapping": {i: f"KR4c0012_{i:03d}" for i in range(31)},
}


def generate_dufu_kanripo(dry_run: bool = False) -> tuple[int, int]:
    """Generate 杜工部集 from Kanripo (KR4c0018)."""
    info = TEXTS["du-fu"]
    out_dir = LIT_DIR / info["category"] / info["slug"]
    km = KANRIPO_DUFU

    print(f"\n{'='*60}")
    print(f"Generating {km['title']} from Kanripo ({km['repo']})")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    if not dry_run:
        # Clean out old files
        import shutil
        if out_dir.exists():
            shutil.rmtree(out_dir)
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])

    total = km["volumes"]
    success, fail = 0, 0
    for i in range(total):
        vol = i  # 0 = preface, 1+ = content volumes
        group = volume_group_dir(max(vol, 1), max(total - 1, 1))
        file_id = km["mapping"][i]
        out_file = out_dir / group / f"{info['slug']}-{vol:03d}.md"

        if out_file.exists():
            print(f"  [{vol:03d}/{total - 1}] Skipping (exists)")
            success += 1
            continue

        try:
            raw = fetch_kanripo(km["repo"], file_id + ".txt")
            body = clean_kanripo_text(raw, is_poetry=False)
            if not body.strip():
                print(f"  [{vol:03d}/{total - 1}] EMPTY content")
                fail += 1
                continue

            if vol == 0:
                display_title = f"{info['title']} 提要"
            else:
                display_title = f"{info['title']} 卷{vol}"
            vol_summary = f"{info['title']}卷{vol}。" if vol > 0 else f"{info['title']}提要。"

            if not dry_run:
                out_file.parent.mkdir(parents=True, exist_ok=True)
                write_page(out_file, display_title, vol_summary, max(vol, 1), body, info["tags"])
                if vol == 0:
                    write_index(out_file.parent, f"{info['title']} 提要",
                                display_title, 0, info["tags"])

            label = f"卷{vol}" if vol > 0 else "提要"
            print(f"  [{vol:03d}/{total - 1}] {label} ({len(body)} chars) -> {out_file.relative_to(ROOT)}")
            success += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  [{vol:03d}/{total - 1}] FAILED {file_id}: {e}")
            fail += 1

    print(f"  Done: {success} success, {fail} failed")
    return success, fail


def generate_libai_kanripo(dry_run: bool = False) -> tuple[int, int]:
    """Generate 李太白文集 from Kanripo (KR4c0012)."""
    info = TEXTS["li-bai"]
    out_dir = LIT_DIR / info["category"] / info["slug"]
    km = KANRIPO_LIBAI

    print(f"\n{'='*60}")
    print(f"Generating {km['title']} from Kanripo ({km['repo']})")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    if not dry_run:
        import shutil
        if out_dir.exists():
            shutil.rmtree(out_dir)
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])

    total = km["volumes"]
    total_vols = total - 1  # 30 actual volumes
    success, fail = 0, 0
    for i in range(total):
        vol = i  # 0 = 提要, 1-30 = 30 volumes
        group = volume_group_dir(max(vol, 1), total_vols)
        file_id = km["mapping"][i]
        out_file = out_dir / group / f"{info['slug']}-{vol:03d}.md"

        if out_file.exists():
            print(f"  [{vol:03d}/{total_vols}] Skipping (exists)")
            success += 1
            continue

        try:
            raw = fetch_kanripo(km["repo"], file_id + ".txt")
            # Poetry: preserve line breaks, strip leading spaces
            body = clean_kanripo_text(raw, is_poetry=True)
            if not body.strip():
                print(f"  [{vol:03d}/{total_vols}] EMPTY content")
                fail += 1
                continue

            if vol == 0:
                display_title = f"{info['title']} 提要"
            else:
                display_title = f"{info['title']} 卷{vol}"
            vol_summary = f"{info['title']}卷{vol}。" if vol > 0 else f"{info['title']}提要。"

            if not dry_run:
                out_file.parent.mkdir(parents=True, exist_ok=True)
                write_page(out_file, display_title, vol_summary, max(vol, 1), body, info["tags"])

            label = f"卷{vol}" if vol > 0 else "提要"
            print(f"  [{vol:03d}/{total_vols}] {label} ({len(body)} chars) -> {out_file.relative_to(ROOT)}")
            success += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  [{vol:03d}/{total_vols}] FAILED {file_id}: {e}")
            fail += 1

    print(f"  Done: {success} success, {fail} failed")
    return success, fail

def generate_renjian_cihua(dry_run: bool = False) -> tuple[int, int]:
    """Generate 人间词话. Single page with inline sections."""
    info = TEXTS["renjian-cihua"]
    out_dir = LIT_DIR / info["category"] / info["slug"]

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


def generate_shi_pin(dry_run: bool = False) -> tuple[int, int]:
    """Generate 诗品. Preface on main page + 3 juan sub-pages."""
    info = TEXTS["shi-pin"]
    out_dir = LIT_DIR / info["category"] / info["slug"]

    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']})")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    # Fetch main page and extract preface
    raw = fetch_raw(info["wiki_title"])
    # Keep only content between header and the next link
    # The main page has the 序 content before [[詩品/卷上|卷上]]
    preface_raw = re.sub(r'.*?notes\s*=(.*?)\}\}', r'\1', raw, count=1, flags=re.S)
    # Actually, let's just parse the main page content
    preface = clean_wikitext(raw)
    # Remove category links etc
    preface = preface.strip()

    # Fetch sub-pages
    parts = [f"## 序\n\n{preface}"]
    juan_labels = [(1, "卷上"), (2, "卷中"), (3, "卷下")]
    for vol, label in juan_labels:
        raw = fetch_raw(f"{info['wiki_title']}/{label}")
        clean = clean_wikitext(raw)
        parts.append(f"## {label}\n\n{clean}")
        time.sleep(1)

    body = "\n\n".join(parts)

    out_file = out_dir / f"{info['slug']}.md"
    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])
        write_page(out_file, info["title"], info["summary"], 1, body, info["tags"])
    print(f"  OK ({len(body)} chars) -> {out_file.relative_to(ROOT)}")

    return 1, 0


def generate_wenxin_diaolong(dry_run: bool = False) -> tuple[int, int]:
    """Generate 文心雕龙. 50 chapters on individual sub-pages."""
    info = TEXTS["wenxin-diaolong"]
    out_dir = LIT_DIR / info["category"] / info["slug"]

    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']})")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    # Discover sub-pages
    subpages = discover_subpages(info["wiki_title"])
    # Filter out non-chapter pages (like template pages)
    # Typical titles: 文心雕龍/原道, 文心雕龍/徵聖, etc.
    chapters = [(title, base) for title, base in subpages
                if not base.startswith("Template:") and "卷" not in base.lower()]
    chapters.sort(key=lambda x: x[0])

    print(f"  Found {len(chapters)} chapters")

    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])

    success, fail = 0, 0
    for i, (page_title, chapter_name) in enumerate(chapters, start=1):
        out_file = out_dir / f"{info['slug']}-{i:02d}.md"

        if out_file.exists():
            print(f"  [{i:02d}/{len(chapters)}] Skipping (exists)")
            success += 1
            continue

        try:
            raw = fetch_raw(page_title)
            body = final_clean(clean_wikitext(raw))
            if not body.strip():
                print(f"  [{i:02d}/{len(chapters)}] EMPTY content: {page_title}")
                fail += 1
                continue

            if not dry_run:
                write_page(out_file, chapter_name, f"{info['title']}：{chapter_name}", i,
                           body, info["tags"])
            print(f"  [{i:02d}/{len(chapters)}] OK ({len(body)} chars) -> {out_file.name}")
            success += 1
            time.sleep(1)
        except Exception as e:
            print(f"  [{i:02d}/{len(chapters)}] FAILED {page_title}: {e}")
            fail += 1

    print(f"  Done: {success} success, {fail} failed")
    return success, fail


def generate_chuci(dry_run: bool = False) -> tuple[int, int]:
    """Generate 楚辞. 17 chapters on standalone/semi-standalone pages."""
    info = TEXTS["chu-ci"]
    out_dir = LIT_DIR / info["category"] / info["slug"]

    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']})")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])

    success, fail = 0, 0
    for vol, slug, wiki_title in CHUCI_CHAPTERS:
        out_file = out_dir / f"chu-ci-{vol:02d}-{slug}.md"

        if out_file.exists():
            print(f"  [{vol:02d}/17] {slug} — Skipping (exists)")
            success += 1
            continue

        try:
            raw = fetch_raw(wiki_title)
            body = final_clean(clean_wikitext(raw))
            if not body.strip():
                print(f"  [{vol:02d}/17] {slug}: EMPTY content")
                fail += 1
                continue

            display_title = f"楚辞 {slug}（卷{vol}）"
            chapter_summary = f"楚辞卷第{vol}，{slug}。"
            if not dry_run:
                write_page(out_file, display_title, chapter_summary, vol, body, info["tags"])
            print(f"  [{vol:02d}/17] {slug} ({len(body)} chars) -> {out_file.name}")
            success += 1
            time.sleep(1)
        except Exception as e:
            print(f"  [{vol:02d}/17] {slug}: FAILED ({wiki_title}: {e})")
            fail += 1

    print(f"  Done: {success} success, {fail} failed")
    return success, fail


# ── Generators: Phase 3 ────────────────────────────────────────────

def generate_multi_volume(text_id: str, dry_run: bool = False) -> tuple[int, int]:
    """Generic multi-volume generator for texts with /卷N sub-pages."""
    info = TEXTS[text_id]
    out_dir = LIT_DIR / info["category"] / info["slug"]

    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']})")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    vol_pattern = info.get("vol_pattern", r'卷0*(\d+)')
    total = info.get("total_volumes")

    # Discover volume pages
    print(f"  Discovering volume pages (pattern: {vol_pattern})...")
    pages = discover_volume_pages(info["wiki_title"], vol_pattern)
    found_vols = sorted(pages.keys())
    print(f"  Found {len(found_vols)} volumes on Wikisource")

    if total is None:
        total = max(found_vols) if found_vols else 0

    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])

    success, fail = 0, 0
    for vol in found_vols:
        group = volume_group_dir(vol, total)
        out_file = out_dir / group / f"{info['slug']}-{vol:03d}.md"

        if out_file.exists():
            print(f"  [{vol:03d}/{total}] Skipping (exists)")
            success += 1
            continue

        # Fetch and combine all pages for this volume
        parts = []
        for page_title in pages[vol]:
            try:
                raw = fetch_raw(page_title)
                clean = final_clean(clean_wikitext(raw))
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
            display_title = f"{info['title']} 卷{vol}"
            vol_summary = f"{info['title']}卷{vol}。"

            if not dry_run:
                out_file.parent.mkdir(parents=True, exist_ok=True)
                write_page(out_file, display_title, vol_summary, vol, body, info["tags"])
                # Also write group _index.md
                write_index(out_file.parent, f"{info['title']} 卷{group}",
                            display_title, vol, info["tags"])

            print(f"  [{vol:03d}/{total}] OK ({len(body)} chars) -> {out_file.relative_to(ROOT)}")
            success += 1
            time.sleep(1.5)

    # Check for missing volumes
    missing = set(range(1, total + 1)) - set(found_vols)
    if missing:
        print(f"  Missing volumes on Wikisource: {sorted(missing)[:20]}...")

    print(f"  Done: {success} success, {fail} failed")
    return success, fail


def generate_huajian_ji(dry_run: bool = False) -> tuple[int, int]:
    """Generate 花间集. Single page with poems by 词牌 headings."""
    info = TEXTS["hua-jian-ji"]
    out_dir = LIT_DIR / info["category"] / info["slug"]

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


def chinese_to_int(s: str) -> int:
    """Convert simple Chinese number string to integer (一→1, 十→10)."""
    nums = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if s in nums:
        return nums[s]
    if s.startswith("十"):
        return 10 + nums.get(s[1:], 0)
    return 1  # fallback


# ── Main ───────────────────────────────────────────────────────────

PHASE_FUNCS: dict[int, list[str]] = {
    2: ["renjian-cihua", "shi-pin", "wenxin-diaolong", "chu-ci"],
    3: ["guwen-guanzhi", "yu-tai-xin-yong", "sui-yuan-shi-hua", "hua-jian-ji",
        "wen-xuan", "yue-fu-shi-ji"],
    4: ["du-fu", "li-bai"],
}

GENERATORS = {
    "renjian-cihua": generate_renjian_cihua,
    "shi-pin": generate_shi_pin,
    "wenxin-diaolong": generate_wenxin_diaolong,
    "chu-ci": generate_chuci,
    # Phase 3/4 uses the generic multi-volume generator
    "guwen-guanzhi": lambda dry_run=False: generate_multi_volume("guwen-guanzhi", dry_run=dry_run),
    "yu-tai-xin-yong": lambda dry_run=False: generate_multi_volume("yu-tai-xin-yong", dry_run=dry_run),
    "sui-yuan-shi-hua": lambda dry_run=False: generate_multi_volume("sui-yuan-shi-hua", dry_run=dry_run),
    "hua-jian-ji": generate_huajian_ji,
    "wen-xuan": lambda dry_run=False: generate_multi_volume("wen-xuan", dry_run=dry_run),
    "yue-fu-shi-ji": lambda dry_run=False: generate_multi_volume("yue-fu-shi-ji", dry_run=dry_run),
    "du-fu": generate_dufu_kanripo,
    "li-bai": generate_libai_kanripo,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="Generate a single text by id")
    parser.add_argument("--all", action="store_true", help="Generate all texts")
    parser.add_argument("--phase", type=int, choices=[2, 3, 4], help="Generate by phase")
    parser.add_argument("--list", action="store_true", help="List available texts")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list:
        for phase in sorted(PHASE_FUNCS):
            print(f"\nPhase {phase}:")
            for tid in PHASE_FUNCS[phase]:
                info = TEXTS[tid]
                print(f"  {tid:20s} {info['title']:8s} — {info['summary'][:50]}")
        return

    if args.text:
        if args.text not in GENERATORS:
            print(f"Unknown text: {args.text}")
            print(f"Available: {', '.join(sorted(GENERATORS))}")
            return
        gen = GENERATORS[args.text]
        gen(dry_run=args.dry_run)

    elif args.phase:
        ids = PHASE_FUNCS.get(args.phase, [])
        total_ok, total_fail = 0, 0
        for tid in ids:
            ok, fail = GENERATORS[tid](dry_run=args.dry_run)
            total_ok += ok
            total_fail += fail
        print(f"\n{'='*60}")
        print(f"Phase {args.phase} DONE: {total_ok} success, {total_fail} failed")

    elif args.all:
        total_ok, total_fail = 0, 0
        for phase in sorted(PHASE_FUNCS):
            for tid in PHASE_FUNCS[phase]:
                ok, fail = GENERATORS[tid](dry_run=args.dry_run)
                total_ok += ok
                total_fail += fail
        print(f"\n{'='*60}")
        print(f"ALL DONE: {total_ok} success, {total_fail} failed")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
