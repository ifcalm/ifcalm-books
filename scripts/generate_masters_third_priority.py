#!/usr/bin/env python3
"""Generate the next priority 子部 works from Wikisource.

This batch collects:

* 孙子兵法: the canonical 13 chapters. Wikisource also includes "答话";
  it is not part of the received 13-chapter text and is intentionally skipped.
* 商君书: 24 extant chapters. Chapter 16 刑约 and chapter 21 御盗 are
  recorded as lost/目存 but are not generated as body pages.
* 鬼谷子: 15 extant received sections, including 本经阴符七术、持枢、中经.
* 公孙龙子: 原序 plus the 6 extant chapters.

Wikisource is used as the structured primary source; CText pages are retained as
proofreading references for order, lost chapters, and completeness.
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


@dataclass(frozen=True)
class Chapter:
    number: int
    wiki_title: str
    source_heading: str | None
    display_title: str


@dataclass(frozen=True)
class Work:
    key: str
    title: str
    slug: str
    summary: str
    primary_url: str
    proofreading_url: str
    weight: int
    chapters: tuple[Chapter, ...]
    expected_count: int


SUNZI_CHAPTERS = (
    Chapter(1, "孫子兵法", "始計第一", "始计"),
    Chapter(2, "孫子兵法", "作戰第二", "作战"),
    Chapter(3, "孫子兵法", "謀攻第三", "谋攻"),
    Chapter(4, "孫子兵法", "軍形第四", "军形"),
    Chapter(5, "孫子兵法", "兵勢第五", "兵势"),
    Chapter(6, "孫子兵法", "虛實第六", "虚实"),
    Chapter(7, "孫子兵法", "軍爭第七", "军争"),
    Chapter(8, "孫子兵法", "九變第八", "九变"),
    Chapter(9, "孫子兵法", "行軍第九", "行军"),
    Chapter(10, "孫子兵法", "地形第十", "地形"),
    Chapter(11, "孫子兵法", "九地第十一", "九地"),
    Chapter(12, "孫子兵法", "火攻第十二", "火攻"),
    Chapter(13, "孫子兵法", "用間第十三", "用间"),
)


SHANGJUN_CHAPTERS = (
    Chapter(1, "商君書/卷一", "更法第一", "更法"),
    Chapter(2, "商君書/卷一", "墾令第二", "垦令"),
    Chapter(3, "商君書/卷一", "農戰第三", "农战"),
    Chapter(4, "商君書/卷一", "去彊第四", "去强"),
    Chapter(5, "商君書/卷二", "說民第五", "说民"),
    Chapter(6, "商君書/卷二", "算地第六", "算地"),
    Chapter(7, "商君書/卷二", "開塞第七", "开塞"),
    Chapter(8, "商君書/卷三", "壹言第八", "壹言"),
    Chapter(9, "商君書/卷三", "錯法第九", "错法"),
    Chapter(10, "商君書/卷三", "戰法第十", "战法"),
    Chapter(11, "商君書/卷三", "立本第十一", "立本"),
    Chapter(12, "商君書/卷三", "兵守第十二", "兵守"),
    Chapter(13, "商君書/卷三", "靳令第十三", "靳令"),
    Chapter(14, "商君書/卷三", "修權第十四", "修权"),
    Chapter(15, "商君書/卷四", "徠民第十五", "徕民"),
    Chapter(17, "商君書/卷四", "賞刑第十七", "赏刑"),
    Chapter(18, "商君書/卷四", "畫策第十八", "画策"),
    Chapter(19, "商君書/卷五", "境內第十九", "境内"),
    Chapter(20, "商君書/卷五", "弱民第二十", "弱民"),
    Chapter(22, "商君書/卷五", "外內第二十二", "外内"),
    Chapter(23, "商君書/卷五", "君臣第二十三", "君臣"),
    Chapter(24, "商君書/卷五", "禁使第二十四", "禁使"),
    Chapter(25, "商君書/卷五", "慎法第二十五", "慎法"),
    Chapter(26, "商君書/卷五", "定分第二十六", "定分"),
)


GUIGUZI_CHAPTERS = (
    Chapter(1, "鬼谷子/卷01", "捭闔第一", "捭阖"),
    Chapter(2, "鬼谷子/卷01", "反應第二", "反应"),
    Chapter(3, "鬼谷子/卷01", "內揵第三", "内揵"),
    Chapter(4, "鬼谷子/卷01", "抵巇第四", "抵巇"),
    Chapter(5, "鬼谷子/卷02", "飛箝第五", "飞箝"),
    Chapter(6, "鬼谷子/卷02", "忤合第六", "忤合"),
    Chapter(7, "鬼谷子/卷02", "揣篇第七", "揣篇"),
    Chapter(8, "鬼谷子/卷02", "摩篇第八", "摩篇"),
    Chapter(9, "鬼谷子/卷02", "權篇第九", "权篇"),
    Chapter(10, "鬼谷子/卷02", "謀篇第十", "谋篇"),
    Chapter(11, "鬼谷子/卷02", "決篇第十一", "决篇"),
    Chapter(12, "鬼谷子/卷02", "符言第十二", "符言"),
    Chapter(13, "鬼谷子/卷03", "夲經隂符七術", "本经阴符七术"),
    Chapter(14, "鬼谷子/卷03", "持樞", "持枢"),
    Chapter(15, "鬼谷子/卷03", "中經", "中经"),
)


GONGSUN_LONGZI_CHAPTERS = (
    Chapter(1, "公孫龍子/原序", None, "原序"),
    Chapter(2, "公孫龍子/1", None, "迹府"),
    Chapter(3, "公孫龍子/2", None, "白马论"),
    Chapter(4, "公孫龍子/3", None, "指物论"),
    Chapter(5, "公孫龍子/4", None, "通变论"),
    Chapter(6, "公孫龍子/5", None, "坚白论"),
    Chapter(7, "公孫龍子/6", None, "名实论"),
)


WORKS = {
    "sunzi-bingfa": Work(
        "sunzi-bingfa",
        "孙子兵法",
        "sunzi-bingfa",
        "孙子兵法十三篇，兵家代表经典。",
        "https://zh.wikisource.org/wiki/孫子兵法",
        "https://ctext.org/art-of-war/zh",
        6,
        SUNZI_CHAPTERS,
        13,
    ),
    "shangjun-shu": Work(
        "shangjun-shu",
        "商君书",
        "shangjun-shu",
        "商君书现存二十四篇，第十六《刑约》、第二十一《御盗》仅存篇目。",
        "https://zh.wikisource.org/wiki/商君書",
        "https://ctext.org/shang-jun-shu/zh",
        7,
        SHANGJUN_CHAPTERS,
        24,
    ),
    "guiguzi": Work(
        "guiguzi",
        "鬼谷子",
        "guiguzi",
        "鬼谷子今本正文十五篇，含本经阴符七术、持枢、中经。",
        "https://zh.wikisource.org/wiki/鬼谷子",
        "https://ctext.org/gui-gu-zi/zh",
        8,
        GUIGUZI_CHAPTERS,
        15,
    ),
    "gongsun-longzi": Work(
        "gongsun-longzi",
        "公孙龙子",
        "gongsun-longzi",
        "公孙龙子收录原序及今存六篇，名家代表典籍。",
        "https://zh.wikisource.org/wiki/公孫龍子",
        "https://ctext.org/gongsunlongzi/zh",
        9,
        GONGSUN_LONGZI_CHAPTERS,
        7,
    ),
}


SHANGJUN_MISSING_NUMBERS = {16, 21}
GUIGUZI_LOST_TITLES = {"轉丸", "胠亂"}


def dump_yaml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(title: str, summary: str, weight: int, tag: str, *, draft: bool) -> str:
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
    for name in ("header2", "Header2", "header", "Header", "footer", "Footer"):
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


def clean_body(raw: str) -> str:
    text = strip_notes(raw)
    text = clean_wikitext(text)
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
        if line == "轉丸、胠亂二篇皆亡。":
            continue
        if re.fullmatch(r"鬼谷子卷[上中下]", line):
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def split_heading_sections(raw: str) -> dict[str, str]:
    text = strip_notes(raw).replace("\r\n", "\n")
    heading_re = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", flags=re.M)
    matches = list(heading_re.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[heading] = text[start:end].strip()
    return sections


def page_filename(work: Work, chapter: Chapter) -> str:
    return f"{work.slug}-{chapter.number:03d}.md"


def write_index(path: Path, title: str, summary: str, weight: int, tag: str, body: str = "") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "_index.md").write_text(
        front_matter(title, summary, weight, tag, draft=True) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def write_page(path: Path, title: str, summary: str, weight: int, tag: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(title, summary, weight, tag, draft=CONTENT_DRAFT) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def clean_generated_files(path: Path) -> None:
    if not path.exists():
        return
    for child in path.glob("*.md"):
        if child.name != "_index.md":
            child.unlink()


def generate_work(work: Work, *, clean: bool = False) -> None:
    out_dir = MASTERS_DIR / work.slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    write_index(out_dir, work.title, work.summary, work.weight, work.title)
    clean_generated_files(out_dir)

    raw_cache: dict[str, str] = {}
    section_cache: dict[str, dict[str, str]] = {}
    for chapter in work.chapters:
        if chapter.wiki_title not in raw_cache:
            raw_cache[chapter.wiki_title] = fetch_raw(chapter.wiki_title)
            time.sleep(FETCH_DELAY)
        if chapter.source_heading is None:
            body = clean_body(raw_cache[chapter.wiki_title])
        else:
            if chapter.wiki_title not in section_cache:
                section_cache[chapter.wiki_title] = split_heading_sections(raw_cache[chapter.wiki_title])
            sections = section_cache[chapter.wiki_title]
            if chapter.source_heading not in sections:
                available = ", ".join(sections)
                raise ValueError(
                    f"Missing heading {chapter.source_heading} in {chapter.wiki_title}; available: {available}"
                )
            body = clean_body(sections[chapter.source_heading])
        if not body:
            raise ValueError(f"Empty body for {work.title}/{chapter.display_title}")
        write_page(
            out_dir / page_filename(work, chapter),
            f"{work.title}：{chapter.display_title}",
            f"{work.title}：{chapter.display_title}",
            chapter.number,
            work.title,
            body,
        )
    print(f"Generated {work.title}: {len(work.chapters)} files")


def generated_paths() -> list[Path]:
    paths = [MASTERS_DIR / "_index.md"]
    for work in WORKS.values():
        paths.append(MASTERS_DIR / work.slug / "_index.md")
        paths.extend(MASTERS_DIR / work.slug / page_filename(work, chapter) for chapter in work.chapters)
    return paths


def validate() -> None:
    missing = [path for path in generated_paths() if not path.exists()]
    if missing:
        raise ValueError("Missing generated files:\n" + "\n".join(str(path) for path in missing))

    artifact = re.compile(
        r"\{\{|\}\}|\[\[|\]\]|[<>]|Category:|textquality|Textquality|"
        r"Gototop|gototop|Header|Footer|onlyinclude|href=|�|[\ue000-\uf8ff]|"
        r"^[a-z][a-z-]{1,12}:|^:|（[^）\n]{1,50}）|〔|〕|"
        r"〈|〉|○案|內容及篇目俱亡|内容及篇目俱亡|答話|\[[^\]\n]+\]",
        flags=re.M,
    )
    forbidden_front = re.compile(r"^(categories|source|source_url|source_license):", flags=re.M)

    for path in generated_paths():
        content = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.S)
        if not match:
            raise ValueError(f"Missing front matter: {path}")
        front = match.group(1)
        body = content[match.end():].strip()
        expected_draft = "true"
        if f"draft: {expected_draft}" not in front:
            raise ValueError(f"Unexpected draft state in {path}")
        if forbidden_front.search(front):
            raise ValueError(f"Forbidden front matter in {path}")
        if path.name != "_index.md" and not body:
            raise ValueError(f"Empty body in {path}")
        if artifact.search(body):
            raise ValueError(f"Source artifact in {path}")

    for work in WORKS.values():
        count = len([path for path in (MASTERS_DIR / work.slug).glob("*.md") if path.name != "_index.md"])
        if count != work.expected_count:
            raise ValueError(f"Unexpected count for {work.key}: {count}, expected {work.expected_count}")

    shangjun_numbers = {chapter.number for chapter in SHANGJUN_CHAPTERS}
    if shangjun_numbers | SHANGJUN_MISSING_NUMBERS != set(range(1, 27)):
        raise ValueError("商君书 extant/missing chapter numbers do not cover 1-26")
    if shangjun_numbers & SHANGJUN_MISSING_NUMBERS:
        raise ValueError("商君书 missing chapter numbers overlap extant chapters")

    guiguzi_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (MASTERS_DIR / "guiguzi").glob("*.md")
    )
    for title in GUIGUZI_LOST_TITLES:
        if title in guiguzi_text:
            raise ValueError(f"Unexpected lost 鬼谷子 title in generated text: {title}")

    print("Masters third priority local check passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Generate all works in this batch")
    parser.add_argument("--text", choices=sorted(WORKS), help="Generate one work")
    parser.add_argument("--clean", action="store_true", help="Remove target work directory before writing")
    parser.add_argument("--check", action="store_true", help="Check generated output")
    args = parser.parse_args()

    if args.check:
        validate()
        return 0

    if not args.all and not args.text:
        parser.print_help()
        return 0

    write_index(
        MASTERS_DIR,
        "子部",
        "子部，收录诸子百家、兵家、杂家等先秦两汉诸子典籍。",
        6,
        "子部",
        "子部先收诸子百家代表性典籍。",
    )

    if args.all:
        for work in WORKS.values():
            generate_work(work, clean=args.clean)
        return 0

    generate_work(WORKS[args.text], clean=args.clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
