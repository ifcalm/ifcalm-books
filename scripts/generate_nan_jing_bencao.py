#!/usr/bin/env python3
"""Generate 《难经》 and 《神农本草经》 content from Wikisource raw pages.

Primary text:
  - https://zh.wikisource.org/wiki/難經
  - https://zh.wikisource.org/wiki/神農本草經
Cross-check sources:
  - CText: https://ctext.org/nan-jing/zh
  - Kanripo KR3e0003: 王翰林集註黃帝八十一難經
  - Kanripo KR3e0004: 難經本義
  - Kanripo KR3e0084: 神農本草經疏
  - Wikisource: 神農本草經 (孫星衍)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEDICINE_DIR = ROOT / "content" / "posts" / "medicine"
CONTENT_DATE = "2026-06-02"
CONTENT_DRAFT = "true"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
WIKISOURCE_RAW = "https://zh.wikisource.org/w/index.php?title={}&action=raw"
FETCH_DELAY = 0.1


@dataclass(frozen=True)
class Page:
    title: str
    body: str


@dataclass(frozen=True)
class Work:
    slug: str
    title: str
    raw_title: str
    tag: str
    weight: int
    expected_pages: int
    summary: str
    index_body: str


WORKS = {
    "nan-jing": Work(
        slug="nan-jing",
        title="难经",
        raw_title="難經",
        tag="难经",
        weight=4,
        expected_pages=81,
        summary="难经，又称黄帝八十一难经，按八十一难收录。",
        index_body="《难经》又称《黄帝八十一难经》，按八十一难分篇收录。",
    ),
    "shen-nong-ben-cao-jing": Work(
        slug="shen-nong-ben-cao-jing",
        title="神农本草经",
        raw_title="神農本草經",
        tag="神农本草经",
        weight=5,
        expected_pages=19,
        summary="神农本草经，按上经、中经、下经三品部类收录。",
        index_body=(
            "《神农本草经》按上经、中经、下经三品及玉石、草、木、果菜、"
            "米谷、虫兽部类收录。\n\n"
            "校勘记：序例载三品三百六十五种；本次按所据底本正文收录，"
            "药名条目按正文标识计为三百五十九。"
        ),
    ),
}


def fetch_raw(title: str) -> str:
    url = WIKISOURCE_RAW.format(urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        time.sleep(FETCH_DELAY)
        return response.read().decode("utf-8")


def remove_balanced(text: str, open_str: str, close_str: str) -> str:
    while open_str in text:
        start = text.index(open_str)
        depth = 0
        end = None
        olen = len(open_str)
        clen = len(close_str)
        for i in range(start, len(text) - clen + 1):
            if text[i:i + olen] == open_str:
                depth += 1
            elif text[i:i + clen] == close_str:
                depth -= 1
                if depth == 0:
                    end = i + clen
                    break
        if end is None:
            break
        text = text[:start] + text[end:]
    return text


def clean_wikisource(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)

    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.S | re.I)
    text = re.sub(r"<ref\b[^>]*/>", "", text, flags=re.I)
    text = re.sub(r"</?[a-zA-Z][^>\n]*>", "", text)
    text = re.sub(r"^Category:.*$", "", text, flags=re.M)

    text = re.sub(r"\[\[File:[^\]]+\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"^Category:.*$", "", text, flags=re.M)
    text = remove_balanced(text, "{{", "}}")
    text = re.sub(r"^\[\d+\].*$", "", text, flags=re.M)
    text = re.sub(r"\[\d+\]", "", text)

    def convert_heading(match: re.Match[str]) -> str:
        marks, title = match.group(1), match.group(2).strip()
        level = min(len(marks), 6)
        return "#" * level + " " + title

    text = re.sub(r"^(={2,6})\s*(.+?)\s*\1\s*$", convert_heading, text, flags=re.M)
    text = re.sub(r"'''([^']+)'''", r"\1 ", text)
    text = re.sub(r"'''?", "", text)
    text = text.replace("　", " ")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"^__[^_\n]+__$", "", text, flags=re.M)

    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_nan_jing(markdown: str) -> list[Page]:
    pages: list[Page] = []
    current_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if not current_title:
            return
        body = "\n".join(current_lines).strip()
        if not body:
            raise ValueError(f"Empty body for {current_title}")
        pages.append(Page(current_title, body))
        current_title = ""
        current_lines = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            current_lines = [line]
            continue
        if current_title:
            current_lines.append(line)

    flush()
    return pages


def split_bencao(markdown: str) -> list[Page]:
    pages: list[Page] = []
    current_classic = ""
    current_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if not current_title:
            return
        body = "\n".join(current_lines).strip()
        if not body:
            raise ValueError(f"Empty body for {current_classic} {current_title}")
        title = f"{current_classic} {current_title}".strip()
        pages.append(Page(title, body))
        current_title = ""
        current_lines = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            current_classic = line[3:].strip()
            continue
        if line.startswith("### "):
            flush()
            current_title = line[4:].strip()
            heading = f"{current_classic} {current_title}".strip()
            current_lines = [f"## {heading}"]
            continue
        if current_title:
            current_lines.append(line)

    flush()
    return pages


def parse_work(work: Work, markdown: str) -> list[Page]:
    if work.slug == "nan-jing":
        return split_nan_jing(markdown)
    if work.slug == "shen-nong-ben-cao-jing":
        return split_bencao(markdown)
    raise ValueError(f"Unknown work: {work.slug}")


def dump_yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(title: str, summary: str, weight: int, tag: str) -> str:
    return f"""---
title: {dump_yaml_string(title)}
date: {CONTENT_DATE}
weight: {weight}
tags: {json.dumps([tag], ensure_ascii=False)}
draft: {CONTENT_DRAFT}
summary: {dump_yaml_string(summary)}
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def write_page(path: Path, title: str, summary: str, weight: int, tag: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(front_matter(title, summary, weight, tag) + body.rstrip() + "\n", encoding="utf-8")


def write_medicine_index() -> None:
    if (MEDICINE_DIR / "_index.md").exists():
        return
    write_page(
        MEDICINE_DIR / "_index.md",
        "医家",
        "医家典籍收录。",
        4,
        "医家",
        "医家典籍按书目分目录收录。",
    )


def generate_work(work: Work, clean: bool = False) -> int:
    out_dir = MEDICINE_DIR / work.slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    raw = fetch_raw(work.raw_title)
    markdown = clean_wikisource(raw)
    pages = parse_work(work, markdown)
    if len(pages) != work.expected_pages:
        raise ValueError(f"Expected {work.expected_pages} {work.title} pages, found {len(pages)}")

    write_page(out_dir / "_index.md", work.title, work.summary, work.weight, work.tag, work.index_body)
    for index, page in enumerate(pages, start=1):
        out_file = out_dir / f"{work.slug}-{index:03d}.md"
        page_title = f"{work.title} {page.title}"
        summary = f"{work.title}{page.title}"
        write_page(out_file, page_title, summary, index, work.tag, page.body)
        print(f"  {work.title}: wrote {index:03d}/{len(pages)} {page.title}", flush=True)

    return len(pages)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", choices=sorted(WORKS), help="Generate one text")
    parser.add_argument("--all", action="store_true", help="Generate both texts")
    parser.add_argument("--clean", action="store_true", help="Remove existing generated text directories first")
    args = parser.parse_args()

    if not args.text and not args.all:
        parser.print_help()
        return 0

    write_medicine_index()

    total = 0
    selected = WORKS.values() if args.all else [WORKS[args.text]]
    for work in selected:
        total += generate_work(work, clean=args.clean)

    print(f"Generated Nan Jing and Bencao texts: {total} content pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
