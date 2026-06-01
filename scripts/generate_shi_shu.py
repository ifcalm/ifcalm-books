#!/usr/bin/env python3
"""Generate clean 《诗经》 and 《尚书》 content pages from CText API."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFUCIUS_DIR = ROOT / "content" / "posts" / "confucius"
CONTENT_DATE = "2026-05-31"
CONTENT_DRAFT = "true"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CTEXT_API = "https://api.ctext.org/gettext"
CTEXT_SHANGSHU_PAGE = "https://ctext.org/shang-shu/zh"
API_DELAY = 0.05


class CTextLimitError(RuntimeError):
    pass


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_ctext_json(urn: str) -> dict:
    query = urllib.parse.urlencode({"urn": urn, "if": "zh"})
    text = fetch_text(f"{CTEXT_API}?{query}")
    data = json.loads(text)
    if "error" in data:
        code = data["error"].get("code") if isinstance(data["error"], dict) else ""
        if code == "ERR_REQUEST_LIMIT":
            raise CTextLimitError(f"CText request limit reached for {urn}")
        raise ValueError(f"CText API error for {urn}: {data['error']}")
    time.sleep(API_DELAY)
    return data


def fetch_ctext_html_fulltext(urn: str) -> list[str]:
    path = urn.removeprefix("ctp:")
    page_html = fetch_text(f"https://ctext.org/{path}/zh")
    cells = re.findall(r'<td class="ctext">\s*(.*?)</td>', page_html, flags=re.S)
    fulltext: list[str] = []

    for cell in cells:
        text = re.sub(r"<br\s*/?>", "\n", cell)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        if text:
            fulltext.append(text)

    if not fulltext:
        raise ValueError(f"Could not parse CText HTML text for {urn}")

    time.sleep(API_DELAY)
    return fulltext


def dump_yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(title: str, summary: str, weight: int, tags: list[str]) -> str:
    return f"""---
title: {dump_yaml_string(title)}
date: {CONTENT_DATE}
weight: {weight}
tags: {json.dumps(tags, ensure_ascii=False)}
draft: {CONTENT_DRAFT}
summary: {dump_yaml_string(summary)}
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def write_index(out_dir: Path, title: str, summary: str, weight: int, tag: str, body: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_index.md").write_text(
        front_matter(title, summary, weight, [tag]) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def write_page(out_file: Path, title: str, summary: str, weight: int, tag: str, body: str) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        front_matter(title, summary, weight, [tag]) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def clean_output_dir(out_dir: Path, clean: bool) -> None:
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)


def iter_ctext_leaf_pages(urn: str, parents: list[str] | None = None):
    parents = parents or []
    data = fetch_ctext_json(urn)
    title = data.get("title") or ""
    subsections = data.get("subsections") or []

    if subsections:
        next_parents = parents + ([title] if title else [])
        for subsection in subsections:
            yield from iter_ctext_leaf_pages(subsection, next_parents)
        return

    fulltext = [str(line).strip() for line in data.get("fulltext", []) if str(line).strip()]
    yield {"urn": urn, "title": title, "parents": parents, "fulltext": fulltext}


def body_from_fulltext(fulltext: list[str]) -> str:
    if not fulltext:
        raise ValueError("Empty CText fulltext")
    return "\n\n".join(html.unescape(line).strip() for line in fulltext if line.strip())


def generate_shijing(clean: bool = False) -> int:
    out_dir = CONFUCIUS_DIR / "shi-jing"
    clean_output_dir(out_dir, clean)

    write_index(
        out_dir,
        "诗经",
        "诗经，中国最早的诗歌总集，收诗305篇，儒家五经之一。",
        10,
        "诗经",
        "《诗经》按国风、小雅、大雅、颂的传统次序收录正文三百零五篇。",
    )

    count = 0
    for index, item in enumerate(iter_ctext_leaf_pages("ctp:book-of-poetry"), start=1):
        count = index
        parents = item["parents"]
        chapter = parents[-2] if len(parents) >= 2 else "诗经"
        section = parents[-1] if parents else "诗经"
        title = item["title"]
        page_title = f"诗经-{section}-{title}"
        body = f"## {chapter} / {section}\n\n{body_from_fulltext(item['fulltext'])}"
        out_file = out_dir / f"shi-jing-{index:03d}.md"
        write_page(out_file, page_title, f"{section}：{title}", index, "诗经", body)
        if index % 25 == 0:
            print(f"  诗经: wrote {index} pages", flush=True)

    if count != 305:
        raise ValueError(f"Expected 305 Shijing poems, found {count}")

    return count


def parse_shangshu_catalog(page_html: str) -> list[tuple[int, str, str]]:
    entries: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    skip_titles = {"尚書", "虞書", "夏書", "商書", "周書"}
    pattern = re.compile(r'<a class="menuitem" id="m\d+" href="(shang-shu/[^"]+)/zh" >([^<]+)</a>')

    for path, raw_title in pattern.findall(page_html):
        title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
        urn = f"ctp:{path}"
        if title in skip_titles or urn in seen:
            continue
        seen.add(urn)
        entries.append((len(entries) + 1, urn, title))

    if len(entries) != 58:
        raise ValueError(f"Expected 58 Shangshu entries, found {len(entries)}")

    return entries


def generate_shangshu(clean: bool = False) -> int:
    out_dir = CONFUCIUS_DIR / "shang-shu"
    clean_output_dir(out_dir, clean)

    entries = parse_shangshu_catalog(fetch_text(CTEXT_SHANGSHU_PAGE))

    write_index(
        out_dir,
        "尚书",
        "尚书，中国最早的历史文献汇编，儒家五经之一。",
        11,
        "尚书",
        "《尚书》按传世篇目次序收录五十八篇。",
    )

    for number, urn, title in entries:
        out_file = out_dir / f"shang-shu-{number:03d}.md"
        if out_file.exists() and not clean:
            continue

        try:
            data = fetch_ctext_json(urn)
            fulltext = data.get("fulltext", [])
        except CTextLimitError:
            fulltext = fetch_ctext_html_fulltext(urn)

        body = body_from_fulltext(fulltext)
        write_page(out_file, f"尚书-{title}", f"尚书：{title}", number, "尚书", body)
        if number % 10 == 0:
            print(f"  尚书: wrote {number} pages", flush=True)

    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", choices=["shi-jing", "shang-shu"], help="Generate one text")
    parser.add_argument("--all", action="store_true", help="Generate both texts")
    parser.add_argument("--clean", action="store_true", help="Remove old generated output first")
    args = parser.parse_args()

    if not args.text and not args.all:
        parser.print_help()
        return 0

    if args.all or args.text == "shi-jing":
        count = generate_shijing(clean=args.clean)
        print(f"Generated 诗经: {count} content pages")

    if args.all or args.text == "shang-shu":
        count = generate_shangshu(clean=args.clean)
        print(f"Generated 尚书: {count} content pages")

    return 0


if __name__ == "__main__":
    sys.exit(main())
