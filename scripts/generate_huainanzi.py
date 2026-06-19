#!/usr/bin/env python3
"""Generate 淮南子 from Wikisource.

This collects the received 21 juan of 淮南子. Wikisource also has a 敘目 page,
but the corpus page describes 淮南子 as twenty-one juan, and CText lists the
same 21 textual units; 敘目 is therefore not generated as a body page.

Wikisource is used as the structured primary source. CText is retained as a
proofreading reference for chapter order and completeness.
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


sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext


ROOT = Path(__file__).resolve().parents[1]
MASTERS_DIR = ROOT / "content" / "posts" / "masters"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CONTENT_DATE = "2026-06-19"
CONTENT_DRAFT = True
FETCH_DELAY = 0.05
LONG_PARAGRAPH_TARGET = 420
LONG_PARAGRAPH_SOFT_MAX = 700
MAX_RENDERED_PARAGRAPH = 1200


@dataclass(frozen=True)
class Chapter:
    number: int
    wiki_title: str
    display_title: str


TITLE = "淮南子"
SLUG = "huainanzi"
SUMMARY = "淮南子二十一卷，西汉淮南王刘安及门客编撰，杂家代表典籍。"
PRIMARY_URL = "https://zh.wikisource.org/wiki/淮南子"
PROOFREADING_URL = "https://ctext.org/huainanzi/zh"
WEIGHT = 10


CHAPTERS = (
    Chapter(1, "淮南子/原道訓", "原道训"),
    Chapter(2, "淮南子/俶真訓", "俶真训"),
    Chapter(3, "淮南子/天文訓", "天文训"),
    Chapter(4, "淮南子/墜形訓", "坠形训"),
    Chapter(5, "淮南子/時則訓", "时则训"),
    Chapter(6, "淮南子/覽冥訓", "览冥训"),
    Chapter(7, "淮南子/精神訓", "精神训"),
    Chapter(8, "淮南子/本經訓", "本经训"),
    Chapter(9, "淮南子/主術訓", "主术训"),
    Chapter(10, "淮南子/繆稱訓", "缪称训"),
    Chapter(11, "淮南子/齊俗訓", "齐俗训"),
    Chapter(12, "淮南子/道應訓", "道应训"),
    Chapter(13, "淮南子/氾論訓", "泛论训"),
    Chapter(14, "淮南子/詮言訓", "诠言训"),
    Chapter(15, "淮南子/兵略訓", "兵略训"),
    Chapter(16, "淮南子/說山訓", "说山训"),
    Chapter(17, "淮南子/說林訓", "说林训"),
    Chapter(18, "淮南子/人間訓", "人间训"),
    Chapter(19, "淮南子/脩務訓", "修务训"),
    Chapter(20, "淮南子/泰族訓", "泰族训"),
    Chapter(21, "淮南子/要略", "要略"),
)


# Wikisource raw text contains a small number of private-use glyphs and one
# legacy encoding fragment. These forms were checked against CText readings
# where available; empty replacements follow the CText wording at that locus.
SOURCE_REPLACEMENTS = {
    "<月曷>": "𦝲",
    "\uf5cd": "尭",
    "\uf0ef": "𧣈",
    "\ue364": "",
    "\uf659": "期",
    "\uf28c": "",
    "\uefcc": "帚",
    "\ue98c": "轂",
    "\uf1c9": "啼",
    "\ue74e": "蚊",
    "怴A": "者，",
}


def dump_yaml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(title: str, summary: str, weight: int, *, draft: bool, tag: str = TITLE) -> str:
    return f"""---
title: {dump_yaml(title)}
date: {CONTENT_DATE}
weight: {weight}
tags: {json.dumps([tag], ensure_ascii=False)}
draft: {"true" if draft else "false"}
summary: {dump_yaml(summary)}
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def redirect_target(raw: str) -> str | None:
    match = re.match(r"#REDIRECT\s+(?:\[\[)?([^\]\n#]+)", raw.strip(), flags=re.I)
    if not match:
        return None
    return match.group(1).strip()


def fetch_raw(title: str, *, redirects: int = 5) -> str:
    query = urllib.parse.quote(title)
    url = f"https://zh.wikisource.org/w/index.php?title={query}&action=raw"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8")
    target = redirect_target(raw)
    if target and redirects:
        return fetch_raw(target, redirects=redirects - 1)
    return raw


def remove_template(text: str, opener: str) -> str:
    while opener in text:
        start = text.index(opener)
        depth = 0
        index = start
        end = None
        while index < len(text) - 1:
            pair = text[index:index + 2]
            if pair == "{{":
                depth += 1
                index += 2
                continue
            if pair == "}}":
                depth -= 1
                index += 2
                if depth == 0:
                    end = index
                    break
                continue
            index += 1
        if end is None:
            break
        text = text[:start] + text[end:]
    return text


def strip_notes(raw: str) -> str:
    text = raw
    text = re.sub(r"\{\{[Tt]extquality\|[^{}]*\}\}", "", text)
    text = re.sub(r"\{\{[Gg]ototop\}\}", "", text)
    text = remove_template(text, "{{*|")
    for name in ("Novel", "header2", "Header2", "header", "Header", "footer", "Footer"):
        text = remove_template(text, "{{" + name)
    text = re.sub(r"^\[\[Category:[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"^\[\[[a-z][a-z-]{1,12}:[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"\{\{另\|([^|}]+)\|[^}]+\}\}", r"\1", text)
    return text


def remove_angle_notes(text: str) -> str:
    while True:
        next_text = re.sub(r"〈[^〈〉]*〉", "", text)
        if next_text == text:
            return text
        text = next_text


def split_long_paragraph(line: str) -> list[str]:
    if len(line) <= LONG_PARAGRAPH_SOFT_MAX or line.startswith("#"):
        return [line]

    chunks: list[str] = []
    start = 0
    index = 0
    quote_depth = 0
    while index < len(line):
        char = line[index]
        if char in "「『":
            quote_depth += 1
            index += 1
            continue
        if char in "」』":
            quote_depth = max(0, quote_depth - 1)
            index += 1
            continue
        if char not in "。！？":
            index += 1
            continue

        end = index + 1
        projected_depth = quote_depth
        while end < len(line) and line[end] in "」』”’）〕】》":
            if line[end] in "」』":
                projected_depth = max(0, projected_depth - 1)
            end += 1
        if projected_depth == 0 and end - start >= LONG_PARAGRAPH_TARGET:
            chunks.append(line[start:end].strip())
            start = end
        index = end
        quote_depth = projected_depth

    tail = line[start:].strip()
    if tail:
        if chunks and len(tail) < LONG_PARAGRAPH_TARGET // 2:
            chunks[-1] += tail
        else:
            chunks.append(tail)
    return chunks or [line]


def quote_depth(text: str) -> int:
    depth = 0
    for char in text:
        if char in "「『":
            depth += 1
        elif char in "」』":
            depth = max(0, depth - 1)
    return depth


def stitch_open_quote_lines(lines: list[str]) -> list[str]:
    stitched: list[str] = []
    buffer = ""
    for line in lines:
        if not line:
            if buffer and quote_depth(buffer) == 0:
                stitched.append(buffer)
                buffer = ""
            if not buffer and stitched and stitched[-1] != "":
                stitched.append("")
            continue
        buffer = buffer + line if buffer else line
        if buffer.startswith("#") or quote_depth(buffer) == 0:
            stitched.append(buffer)
            buffer = ""
    if buffer:
        stitched.append(buffer)
    return stitched


def markdown_paragraphs(lines: list[str]) -> str:
    paragraphs: list[str] = []
    for line in stitch_open_quote_lines(lines):
        if not line:
            if paragraphs and paragraphs[-1] != "":
                paragraphs.append("")
            continue
        for paragraph in split_long_paragraph(line):
            if paragraphs and paragraphs[-1] != "":
                paragraphs.append("")
            paragraphs.append(paragraph)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(paragraphs)).strip()


def clean_body(raw: str) -> str:
    text = strip_notes(raw)
    text = clean_wikitext(text)
    for source, replacement in SOURCE_REPLACEMENTS.items():
        text = text.replace(source, replacement)
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"</?poem>", "", text)
    text = re.sub(r"</?[a-zA-Z][^>\n]*>", "", text)
    text = remove_angle_notes(text)
    text = re.sub(r"（[^（）\n]{1,50}）〔([^〔〕\n]+)〕", r"\1", text)
    text = re.sub(r"〔([^〔〕\n]+)〕", r"\1", text)
    text = re.sub(r"\[([^\[\]\n]{1,120})\]", r"\1", text)
    text = re.sub(r"（[^（）\n]{1,50}）", "", text)
    text = re.sub(r"^Category:.*$", "", text, flags=re.M)
    text = re.sub(r"^\[\[[a-z][a-z-]{1,12}:.*$", "", text, flags=re.M)
    text = re.sub(r"^[a-z][a-z-]{1,12}:[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"\{\{[^}]+\}\}", "", text)
    text = text.replace("{{", "").replace("}}", "")
    lines = [line.strip() for line in text.splitlines()]
    kept: list[str] = []
    for line in lines:
        line = re.sub(r"^:+", "", line).strip()
        if not line:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if line.startswith(("Gototop", "Footer", "Header", "Textquality", "textquality")):
            continue
        if re.fullmatch(r">\s*回目录", line):
            continue
        if re.fullmatch(r"#{1,6}", line):
            continue
        kept.append(line)
    return markdown_paragraphs(kept)


def page_filename(chapter: Chapter) -> str:
    return f"{SLUG}-{chapter.number:03d}.md"


def write_masters_index() -> None:
    MASTERS_DIR.mkdir(parents=True, exist_ok=True)
    (MASTERS_DIR / "_index.md").write_text(
        front_matter(
            "子部",
            "子部，收录诸子百家、兵家、杂家等先秦两汉诸子典籍。",
            6,
            draft=True,
            tag="子部",
        )
        + "子部先收诸子百家代表性典籍。\n",
        encoding="utf-8",
    )


def write_index(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "_index.md").write_text(
        front_matter(TITLE, SUMMARY, WEIGHT, draft=True),
        encoding="utf-8",
    )


def write_page(path: Path, chapter: Chapter, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(
            f"{TITLE}：{chapter.display_title}",
            f"{TITLE}：{chapter.display_title}",
            chapter.number,
            draft=CONTENT_DRAFT,
        )
        + body.rstrip()
        + "\n",
        encoding="utf-8",
    )


def clean_generated_files(path: Path) -> None:
    if not path.exists():
        return
    for child in path.glob("*.md"):
        if child.name != "_index.md":
            child.unlink()


def generate(*, clean: bool = False) -> None:
    out_dir = MASTERS_DIR / SLUG
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    write_masters_index()
    write_index(out_dir)
    clean_generated_files(out_dir)

    for chapter in CHAPTERS:
        raw = fetch_raw(chapter.wiki_title)
        body = clean_body(raw)
        if not body:
            raise ValueError(f"Empty body for {chapter.display_title}")
        write_page(out_dir / page_filename(chapter), chapter, body)
        time.sleep(FETCH_DELAY)
    print(f"Generated {TITLE}: {len(CHAPTERS)} files")


def generated_paths() -> list[Path]:
    out_dir = MASTERS_DIR / SLUG
    return [MASTERS_DIR / "_index.md", out_dir / "_index.md"] + [
        out_dir / page_filename(chapter) for chapter in CHAPTERS
    ]


def validate() -> None:
    missing = [path for path in generated_paths() if not path.exists()]
    if missing:
        raise ValueError("Missing generated files:\n" + "\n".join(str(path) for path in missing))

    artifact = re.compile(
        r"\{\{|\}\}|\[\[|\]\]|[<>]|Category:|textquality|Textquality|"
        r"Gototop|gototop|Header|Footer|Novel|onlyinclude|href=|�|[\ue000-\uf8ff]|"
        r"[A-Za-z]|^[a-z][a-z-]{1,12}:|^:|（[^）\n]{1,50}）|〔|〕|"
        r"〈|〉|○案|\[[^\]\n]+\]",
        flags=re.M,
    )
    forbidden_front = re.compile(r"^(categories|source|source_url|source_license):", flags=re.M)
    expected_titles = [chapter.display_title for chapter in CHAPTERS]

    for path in generated_paths():
        content = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.S)
        if not match:
            raise ValueError(f"Missing front matter: {path}")
        front = match.group(1)
        body = content[match.end():].strip()
        if "draft: true" not in front:
            raise ValueError(f"Unexpected draft state in {path}")
        if forbidden_front.search(front):
            raise ValueError(f"Forbidden front matter in {path}")
        if path.name != "_index.md" and not body:
            raise ValueError(f"Empty body in {path}")
        if artifact.search(body):
            raise ValueError(f"Source artifact in {path}")
        if path.name != "_index.md":
            for line_number, line in enumerate(body.splitlines(), 1):
                if len(line) > MAX_RENDERED_PARAGRAPH:
                    raise ValueError(
                        f"Overlong rendered paragraph in {path}:{line_number} "
                        f"({len(line)} chars)"
                    )

    out_dir = MASTERS_DIR / SLUG
    count = len([path for path in out_dir.glob("*.md") if path.name != "_index.md"])
    if count != len(CHAPTERS):
        raise ValueError(f"Unexpected count for {SLUG}: {count}, expected {len(CHAPTERS)}")
    weights = []
    titles = []
    for path in sorted(out_dir.glob("*.md")):
        if path.name == "_index.md":
            continue
        front = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), flags=re.S).group(1)
        weight = re.search(r"^weight: (\d+)$", front, flags=re.M)
        title = re.search(r'^title: "淮南子：(.+)"$', front, flags=re.M)
        if not weight or not title:
            raise ValueError(f"Missing weight/title in {path}")
        weights.append(int(weight.group(1)))
        titles.append(title.group(1))
    if weights != list(range(1, len(CHAPTERS) + 1)):
        raise ValueError(f"Unexpected chapter weights: {weights}")
    if titles != expected_titles:
        raise ValueError(f"Unexpected chapter titles: {titles}")

    print("淮南子 local check passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Generate 淮南子")
    parser.add_argument("--clean", action="store_true", help="Remove target work directory before writing")
    parser.add_argument("--check", action="store_true", help="Check generated output")
    args = parser.parse_args()

    if args.check:
        validate()
        return 0

    if not args.all:
        parser.print_help()
        return 0

    generate(clean=args.clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
