#!/usr/bin/env python3
"""Generate 《黄帝内经》 content from Wikisource raw pages.

Primary text: https://zh.wikisource.org/wiki/黃帝內經
Cross-check sources:
  - Kanripo KR3e0001: 重廣補注黄帝内經素問, 24 juan
  - Kanripo KR3e0002: 黄帝素問靈樞經, 12 juan
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
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEDICINE_DIR = ROOT / "content" / "posts" / "medicine"
NEIJING_DIR = MEDICINE_DIR / "huangdi-neijing"
CONTENT_DATE = "2026-06-01"
CONTENT_DRAFT = "true"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
WIKISOURCE_RAW = "https://zh.wikisource.org/w/index.php?title={}&action=raw"
FETCH_DELAY = 0.1
HEADING_CORRECTIONS = {
    "玉板論要篇十五": "玉版論要篇十五",
    "刺腰論痛四十一": "刺腰痛論四十一",
    "壽天剛柔第六": "壽夭剛柔第六",
    "五癃精液別第三十六": "五癃津液別第三十六",
    "血絡第三十九": "血絡論第三十九",
    "背輸第五十一": "背腧第五十一",
    "論疾詮尺第七十四": "論疾診尺第七十四",
}
SUWEN_VERSION_NOTE = """《素问》二十四卷。

校勘记：第七十二《刺法论》、第七十三《本病论》，Kanripo 四部丛刊本《重广补注黄帝内经素问》目录标作“亡”；本收录随通行八十一篇本保留正文。"""


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


def convert_wiki_tables(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.startswith("{|"):
            output.append(line)
            i += 1
            continue

        caption = ""
        rows: list[list[str]] = []
        row: list[str] = []
        i += 1

        while i < len(lines) and not lines[i].startswith("|}"):
            current = lines[i].strip()
            if current.startswith("|+"):
                caption = current[2:].strip()
            elif current.startswith("|-"):
                if row:
                    rows.append(row)
                    row = []
            elif current.startswith(("|", "!")):
                separator = "||" if current.startswith("|") else "!!"
                cells = [cell.strip() for cell in current[1:].split(separator)]
                row.extend(cell for cell in cells if cell)
            i += 1

        if row:
            rows.append(row)
        if caption:
            output.append(caption)
        output.extend("  ".join(row) for row in rows)

        if i < len(lines) and lines[i].startswith("|}"):
            i += 1

    return "\n".join(output)


def clean_wikisource(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)

    for template in ("header2", "header", "Textquality", "textquality", "wikipedia", "檢索"):
        text = remove_balanced(text, "{{" + template, "}}")

    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.S | re.I)
    text = re.sub(r"<ref\b[^>]*/>", "", text, flags=re.I)
    text = re.sub(r"</?[a-zA-Z][^>\n]*>", "", text)
    text = re.sub(r"^Category:.*$", "", text, flags=re.M)

    text = convert_wiki_tables(text)
    text = re.sub(r"\[\[File:[^\]]+\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = remove_balanced(text, "{{", "}}")

    def convert_heading(match: re.Match[str]) -> str:
        marks, title = match.group(1), match.group(2).strip()
        level = min(len(marks), 6)
        return "#" * level + " " + title

    text = re.sub(r"^(={2,6})\s*(.+?)\s*\1\s*$", convert_heading, text, flags=re.M)
    text = re.sub(r"'''?", "", text)
    text = text.replace("　", "")
    text = text.replace("&nbsp;", " ")

    lines = [line.rstrip() for line in text.splitlines()]
    lines = [
        "## " + HEADING_CORRECTIONS.get(line[3:].strip(), line[3:].strip())
        if line.startswith("## ")
        else line
        for line in lines
    ]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n+##\s*附[註注]\s*(?:\n.*)?\Z", "", text, flags=re.S)
    return text.strip()


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


def discover_volumes(section: str) -> list[tuple[str, str]]:
    raw = fetch_raw("黃帝內經")
    if section == "素問":
        body = raw.split("==素問==", 1)[1].split("==靈樞==", 1)[0]
    elif section == "靈樞":
        body = raw.split("==靈樞==", 1)[1]
    else:
        raise ValueError(f"Unknown section: {section}")

    volumes = []
    for rel_title, display in re.findall(r"\[\[(/[^]|]+)\|([^]]+)\]\]", body):
        volumes.append((f"黃帝內經{rel_title}", display))
    return volumes


def write_indexes() -> None:
    write_page(
        MEDICINE_DIR / "_index.md",
        "医家",
        "医家典籍收录。",
        4,
        "医家",
        "医家典籍按书目分目录收录。",
    )
    write_page(
        NEIJING_DIR / "_index.md",
        "黄帝内经",
        "黄帝内经，中医理论经典，分《素问》《灵枢》两部。",
        1,
        "黄帝内经",
        "《黄帝内经》按《素问》《灵枢》分卷收录。",
    )
    write_page(
        NEIJING_DIR / "su-wen" / "_index.md",
        "黄帝内经-素问",
        "黄帝内经素问二十四卷。",
        1,
        "黄帝内经",
        SUWEN_VERSION_NOTE,
    )
    write_page(
        NEIJING_DIR / "ling-shu" / "_index.md",
        "黄帝内经-灵枢",
        "黄帝内经灵枢十二卷。",
        2,
        "黄帝内经",
        "《灵枢》十二卷。",
    )


def generate_section(section: str, slug: str, title: str, expected: int) -> int:
    volumes = discover_volumes(section)
    if len(volumes) != expected:
        raise ValueError(f"Expected {expected} {section} volumes, found {len(volumes)}")

    for index, (source_title, display) in enumerate(volumes, start=1):
        raw = fetch_raw(source_title)
        body = clean_wikisource(raw)
        if not body:
            raise ValueError(f"Empty body after cleaning: {source_title}")

        out_file = NEIJING_DIR / slug / f"{slug}-{index:03d}.md"
        page_title = f"黄帝内经-{title} {display}"
        summary = f"黄帝内经{title}{display}"
        write_page(out_file, page_title, summary, index, "黄帝内经", body)
        print(f"  {title}: wrote {index:03d}/{len(volumes)} {display}", flush=True)

    return len(volumes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", choices=["su-wen", "ling-shu"], help="Generate one part")
    parser.add_argument("--all", action="store_true", help="Generate both parts")
    parser.add_argument("--clean", action="store_true", help="Remove existing medicine/huangdi-neijing first")
    args = parser.parse_args()

    if not args.text and not args.all:
        parser.print_help()
        return 0

    if args.clean and NEIJING_DIR.exists():
        shutil.rmtree(NEIJING_DIR)

    write_indexes()

    total = 0
    if args.all or args.text == "su-wen":
        total += generate_section("素問", "su-wen", "素问", 24)
    if args.all or args.text == "ling-shu":
        total += generate_section("靈樞", "ling-shu", "灵枢", 12)

    print(f"Generated 黄帝内经: {total} content pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
