#!/usr/bin/env python3
"""Generate the next priority 子部 works from Wikisource.

This batch collects:

* 管子: the 76 extant chapters from the received 86-chapter order.
* 吕氏春秋: 26 received juan, containing 160 internal sections.

Wikisource is used as the structured primary source; CText pages are retained as
proofreading references for chapter order and completeness.
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
from wikitext_cleaner import clean_wikitext, remove_balanced


ROOT = Path(__file__).resolve().parents[1]
MASTERS_DIR = ROOT / "content" / "posts" / "masters"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CONTENT_DATE = "2026-06-19"
FETCH_DELAY = 0.05


@dataclass(frozen=True)
class Chapter:
    number: int
    wiki_suffix: str
    title: str


@dataclass(frozen=True)
class Work:
    key: str
    title: str
    slug: str
    summary: str
    wiki_base: str
    primary_url: str
    proofreading_url: str
    weight: int
    chapters: tuple[Chapter, ...]
    expected_section_headings: int | None = None


GUANZI_CHAPTERS = (
    Chapter(1, "第01篇牧民", "牧民"),
    Chapter(2, "第02篇形勢", "形勢"),
    Chapter(3, "第03篇權脩", "權脩"),
    Chapter(4, "第04篇立政", "立政"),
    Chapter(5, "第05篇乘馬", "乘馬"),
    Chapter(6, "第06篇七法", "七法"),
    Chapter(7, "第07篇版法", "版法"),
    Chapter(8, "第08篇幼官", "幼官"),
    Chapter(9, "第09篇幼官圖", "幼官圖"),
    Chapter(10, "第10篇五輔", "五輔"),
    Chapter(11, "第11篇宙合", "宙合"),
    Chapter(12, "第12篇樞言", "樞言"),
    Chapter(13, "第13篇八觀", "八觀"),
    Chapter(14, "第14篇法禁", "法禁"),
    Chapter(15, "第15篇重令", "重令"),
    Chapter(16, "第16篇法法", "法法"),
    Chapter(17, "第17篇兵法", "兵法"),
    Chapter(18, "第18篇大匡", "大匡"),
    Chapter(19, "第19篇中匡", "中匡"),
    Chapter(20, "第20篇小匡", "小匡"),
    Chapter(22, "第22篇霸形", "霸形"),
    Chapter(23, "第23篇霸言", "霸言"),
    Chapter(24, "第24篇問", "問"),
    Chapter(26, "第26篇戒", "戒"),
    Chapter(27, "第27篇地圖", "地圖"),
    Chapter(28, "第28篇參患", "參患"),
    Chapter(29, "第29篇制分", "制分"),
    Chapter(30, "第30篇君臣上", "君臣上"),
    Chapter(31, "第31篇君臣下", "君臣下"),
    Chapter(32, "第32篇小稱", "小稱"),
    Chapter(33, "第33篇四稱", "四稱"),
    Chapter(35, "第35篇侈靡", "侈靡"),
    Chapter(36, "第36篇心術上", "心術上"),
    Chapter(37, "第37篇心術下", "心術下"),
    Chapter(38, "第38篇白心", "白心"),
    Chapter(39, "第39篇水地", "水地"),
    Chapter(40, "第40篇四時", "四時"),
    Chapter(41, "第41篇五行", "五行"),
    Chapter(42, "第42篇勢", "勢"),
    Chapter(43, "第43篇正", "正"),
    Chapter(44, "第44篇九變", "九變"),
    Chapter(45, "第45篇任法", "任法"),
    Chapter(46, "第46篇明法", "明法"),
    Chapter(47, "第47篇正世", "正世"),
    Chapter(48, "第48篇治國", "治國"),
    Chapter(49, "第49篇內業", "內業"),
    Chapter(50, "第50篇封禪", "封禪"),
    Chapter(51, "第51篇小問", "小問"),
    Chapter(52, "第52篇七主七臣", "七主七臣"),
    Chapter(53, "第53篇禁藏", "禁藏"),
    Chapter(54, "第54篇入國", "入國"),
    Chapter(55, "第55篇九守", "九守"),
    Chapter(56, "第56篇桓公問", "桓公問"),
    Chapter(57, "第57篇度地", "度地"),
    Chapter(58, "第58篇地員", "地員"),
    Chapter(59, "第59篇弟子職", "弟子職"),
    Chapter(64, "第64篇形勢解", "形勢解"),
    Chapter(65, "第65篇立政九敗解", "立政九敗解"),
    Chapter(66, "第66篇版法解", "版法解"),
    Chapter(67, "第67篇明法解", "明法解"),
    Chapter(68, "第68篇巨乘馬", "巨乘馬"),
    Chapter(69, "第69篇乘馬數", "乘馬數"),
    Chapter(71, "第71篇事語", "事語"),
    Chapter(72, "第72篇海王", "海王"),
    Chapter(73, "第73篇國蓄", "國蓄"),
    Chapter(74, "第74篇山國軌", "山國軌"),
    Chapter(75, "第75篇山權數", "山權數"),
    Chapter(76, "第76篇山至數", "山至數"),
    Chapter(77, "第77篇地數", "地數"),
    Chapter(78, "第78篇揆度", "揆度"),
    Chapter(79, "第79篇國準", "國準"),
    Chapter(80, "第80篇輕重甲", "輕重甲"),
    Chapter(81, "第81篇輕重乙", "輕重乙"),
    Chapter(83, "第83篇輕重丁", "輕重丁"),
    Chapter(84, "第84篇輕重戊", "輕重戊"),
    Chapter(85, "第85篇輕重己", "輕重己"),
)


LVSHI_CHUNQIU_CHAPTERS = (
    Chapter(1, "卷一", "卷一·孟春紀"),
    Chapter(2, "卷二", "卷二·仲春紀"),
    Chapter(3, "卷三", "卷三·季春紀"),
    Chapter(4, "卷四", "卷四·孟夏紀"),
    Chapter(5, "卷五", "卷五·仲夏紀"),
    Chapter(6, "卷六", "卷六·季夏紀"),
    Chapter(7, "卷七", "卷七·孟秋紀"),
    Chapter(8, "卷八", "卷八·仲秋紀"),
    Chapter(9, "卷九", "卷九·季秋紀"),
    Chapter(10, "卷十", "卷十·孟冬紀"),
    Chapter(11, "卷十一", "卷十一·仲冬紀"),
    Chapter(12, "卷十二", "卷十二·季冬紀"),
    Chapter(13, "卷十三", "卷十三·有始覽"),
    Chapter(14, "卷十四", "卷十四·孝行覽"),
    Chapter(15, "卷十五", "卷十五·愼大覽"),
    Chapter(16, "卷十六", "卷十六·先識覽"),
    Chapter(17, "卷十七", "卷十七·審分覽"),
    Chapter(18, "卷十八", "卷十八·審應覽"),
    Chapter(19, "卷十九", "卷十九·離俗覽"),
    Chapter(20, "卷二十", "卷二十·恃君覽"),
    Chapter(21, "卷二十一", "卷二十一·開春論"),
    Chapter(22, "卷二十二", "卷二十二·愼行論"),
    Chapter(23, "卷二十三", "卷二十三·貴直論"),
    Chapter(24, "卷二十四", "卷二十四·不苟論"),
    Chapter(25, "卷二十五", "卷二十五·似順論"),
    Chapter(26, "卷二十六", "卷二十六·士容論"),
)


WORKS = {
    "guanzi": Work(
        "guanzi",
        "管子",
        "guanzi",
        "管子今本八十六篇，其中十篇亡佚，本次收录现存七十六篇。",
        "管子",
        "https://zh.wikisource.org/wiki/管子",
        "https://ctext.org/guanzi/zh",
        4,
        GUANZI_CHAPTERS,
    ),
    "lvshi-chunqiu": Work(
        "lvshi-chunqiu",
        "吕氏春秋",
        "lvshi-chunqiu",
        "吕氏春秋二十六卷，秦吕不韦门客集成，杂家代表作。",
        "呂氏春秋",
        "https://zh.wikisource.org/wiki/呂氏春秋",
        "https://ctext.org/lv-shi-chun-qiu/zh",
        5,
        LVSHI_CHUNQIU_CHAPTERS,
        expected_section_headings=160,
    ),
}


EXPECTED_COUNTS = {"guanzi": 76, "lvshi-chunqiu": 26}
GUANZI_MISSING_NUMBERS = {21, 25, 34, 60, 61, 62, 63, 70, 82, 86}


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


def strip_notes(raw: str) -> str:
    text = raw
    text = re.sub(r"\{\{[Tt]extquality\|[^{}]*\}\}", "", text)
    text = re.sub(r"\{\{[Gg]ototop\}\}", "", text)
    while "{{*|" in text:
        next_text = remove_balanced(text, "{{*|", "}}")
        if next_text == text:
            break
        text = next_text
    for name in ("header2", "Header2", "header", "Header", "footer", "Footer"):
        while "{{" + name in text:
            next_text = remove_balanced(text, "{{" + name, "}}")
            if next_text == text:
                break
            text = next_text
    text = re.sub(r"^\[\[Category:[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"^\[\[[a-z][a-z-]{1,12}:[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"\{\{另\|([^|}]+)\|[^}]+\}\}", r"\1", text)
    return text


def clean_body(raw: str) -> str:
    text = strip_notes(raw)
    text = clean_wikitext(text)
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"</?poem>", "", text)
    text = re.sub(r"</?[a-zA-Z][^>\n]*>", "", text)
    text = re.sub(r"（[^（）\n]{1,30}）〔([^〔〕\n]+)〕", r"\1", text)
    text = re.sub(r"〔([^〔〕\n]+)〕", r"\1", text)
    text = re.sub(r"（[^（）\n]{1,30}）", "", text)
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
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


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
        front_matter(title, summary, weight, tag, draft=False) + body.rstrip() + "\n",
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

    for chapter in work.chapters:
        raw = fetch_raw(f"{work.wiki_base}/{chapter.wiki_suffix}")
        body = clean_body(raw)
        if not body:
            raise ValueError(f"Empty body for {work.title}/{chapter.title}")
        write_page(
            out_dir / page_filename(work, chapter),
            f"{work.title}-{chapter.title}",
            f"{work.title}：{chapter.title}",
            chapter.number,
            work.title,
            body,
        )
        time.sleep(FETCH_DELAY)
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
        r"\{\{|\}\}|\[\[|\]\]|<[^>]+>|Category:|textquality|Textquality|"
        r"Gototop|gototop|Header|Footer|onlyinclude|href=|�|[\ue000-\uf8ff]|"
        r"^[a-z][a-z-]{1,12}:|^:|（[^）\n]{1,30}）|〔|〕",
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
        expected_draft = "true" if path.name == "_index.md" else "false"
        if f"draft: {expected_draft}" not in front:
            raise ValueError(f"Unexpected draft state in {path}")
        if forbidden_front.search(front):
            raise ValueError(f"Forbidden front matter in {path}")
        if path.name != "_index.md" and not body:
            raise ValueError(f"Empty body in {path}")
        if artifact.search(body):
            raise ValueError(f"Source artifact in {path}")

    for key, expected in EXPECTED_COUNTS.items():
        work = WORKS[key]
        count = len([path for path in (MASTERS_DIR / work.slug).glob("*.md") if path.name != "_index.md"])
        if count != expected:
            raise ValueError(f"Unexpected count for {key}: {count}, expected {expected}")

    guanzi_numbers = {chapter.number for chapter in GUANZI_CHAPTERS}
    if guanzi_numbers | GUANZI_MISSING_NUMBERS != set(range(1, 87)):
        raise ValueError("Guanzi extant/missing chapter numbers do not cover 1-86")
    if guanzi_numbers & GUANZI_MISSING_NUMBERS:
        raise ValueError("Guanzi missing chapter numbers overlap extant chapters")

    lvshi_dir = MASTERS_DIR / WORKS["lvshi-chunqiu"].slug
    lvshi_heading_count = 0
    for path in lvshi_dir.glob("*.md"):
        if path.name != "_index.md":
            lvshi_heading_count += len(re.findall(r"^### ", path.read_text(encoding="utf-8"), flags=re.M))
    expected_headings = WORKS["lvshi-chunqiu"].expected_section_headings
    if expected_headings is not None and lvshi_heading_count != expected_headings:
        raise ValueError(
            f"Unexpected 吕氏春秋 internal heading count: {lvshi_heading_count}, expected {expected_headings}"
        )

    print("Masters second priority local check passed.")


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
