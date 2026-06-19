#!/usr/bin/env python3
"""Generate the next priority 子部 historical and political classics.

This batch collects:

* 国语: 21 juan.
* 战国策: 33 juan.
* 晏子春秋: 8 juan.
* 盐铁论: 10 juan, 60篇.
* 说苑: 20 juan.

Wikisource is used as the structured primary source because it exposes stable
raw wikitext for each juan. CText is retained as the proofreading reference for
work boundaries, order, and received chapter counts.
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
class Volume:
    number: int
    wiki_title: str
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
    volumes: tuple[Volume, ...]
    expected_count: int
    expected_heading_count: int | None = None


GUOYU_TITLES = (
    "周语上",
    "周语中",
    "周语下",
    "鲁语上",
    "鲁语下",
    "齐语",
    "晋语一",
    "晋语二",
    "晋语三",
    "晋语四",
    "晋语五",
    "晋语六",
    "晋语七",
    "晋语八",
    "晋语九",
    "郑语",
    "楚语上",
    "楚语下",
    "吴语",
    "越语上",
    "越语下",
)

ZHANGUOCE_TITLES = (
    "东周",
    "西周",
    "秦一",
    "秦二",
    "秦三",
    "秦四",
    "秦五",
    "齐一",
    "齐二",
    "齐三",
    "齐四",
    "齐五",
    "齐六",
    "楚一",
    "楚二",
    "楚三",
    "楚四",
    "赵一",
    "赵二",
    "赵三",
    "赵四",
    "魏一",
    "魏二",
    "魏三",
    "魏四",
    "韩一",
    "韩二",
    "韩三",
    "燕一",
    "燕二",
    "燕三",
    "宋卫",
    "中山",
)

YANZI_TITLES = (
    "内篇谏上",
    "内篇谏下",
    "内篇问上",
    "内篇问下",
    "内篇杂上",
    "内篇杂下",
    "外篇上",
    "外篇下",
)

SHUOYUAN_TITLES = (
    "君道",
    "臣术",
    "建本",
    "立节",
    "贵德",
    "复恩",
    "政理",
    "尊贤",
    "正谏",
    "敬慎",
    "善说",
    "奉使",
    "权谋",
    "至公",
    "指武",
    "谈丛",
    "杂言",
    "辨物",
    "修文",
    "反质",
)

CN_NUMERALS = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")


WORKS = {
    "guoyu": Work(
        "guoyu",
        "国语",
        "guoyu",
        "国语二十一卷，按国别记述西周至春秋史事与言论。",
        "https://zh.wikisource.org/wiki/國語",
        "https://ctext.org/guo-yu/zh",
        11,
        tuple(
            Volume(number, f"國語/卷{number:02d}", title)
            for number, title in enumerate(GUOYU_TITLES, 1)
        ),
        21,
    ),
    "zhanguoce": Work(
        "zhanguoce",
        "战国策",
        "zhanguoce",
        "战国策三十三卷，西汉刘向校录，辑战国游说策谋之文。",
        "https://zh.wikisource.org/wiki/戰國策",
        "https://ctext.org/zhan-guo-ce/zh",
        12,
        tuple(
            Volume(number, f"戰國策/卷{number:02d}", title)
            for number, title in enumerate(ZHANGUOCE_TITLES, 1)
        ),
        33,
    ),
    "yanzi-chunqiu": Work(
        "yanzi-chunqiu",
        "晏子春秋",
        "yanzi-chunqiu",
        "晏子春秋八卷，记齐相晏婴言行与谏议故事。",
        "https://zh.wikisource.org/wiki/晏子春秋",
        "https://ctext.org/yanzi-chunqiu/zh",
        13,
        tuple(
            Volume(number, f"晏子春秋/卷{CN_NUMERALS[number - 1]}", title)
            for number, title in enumerate(YANZI_TITLES, 1)
        ),
        8,
    ),
    "yantielun": Work(
        "yantielun",
        "盐铁论",
        "yantielun",
        "盐铁论十卷，西汉桓宽撰，记录盐铁会议政论。",
        "https://zh.wikisource.org/wiki/鹽鐵論",
        "https://ctext.org/yan-tie-lun/zh",
        14,
        tuple(
            Volume(number, f"鹽鐵論/卷{number:02d}", f"卷{CN_NUMERALS[number - 1]}")
            for number in range(1, 11)
        ),
        10,
        expected_heading_count=60,
    ),
    "shuoyuan": Work(
        "shuoyuan",
        "说苑",
        "shuoyuan",
        "说苑二十卷，西汉刘向编撰，采辑先秦至汉初说理故事。",
        "https://zh.wikisource.org/wiki/說苑",
        "https://ctext.org/shuo-yuan/zh",
        15,
        tuple(
            Volume(number, f"說苑/卷{number:02d}", title)
            for number, title in enumerate(SHUOYUAN_TITLES, 1)
        ),
        20,
    ),
}


SOURCE_REPLACEMENTS = {
    # Source glyph placeholders checked against Wikisource apparatus and the
    # alternate Siku Quanshu Wikisource transcription where available.
    "<上股下目>": "股",
    "\uea25": "鎁",
    "\uefe5": "牽",
    "\ue32c": "旤",
    "\uf099": "魚",
    "\uf0a8": "鼃",
    "\uf1c0": "嶇",
    "\uf24b": "祲",
    "\uf3e4": "鴥",
    "\uf3f6": "旆",
    "\uf504": "脆",
    "\uf659": "期",
    "其���有德": "其有德",
}


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
    text = raw.replace("\r\n", "\n")
    text = re.sub(r"\{\{[Tt]extquality\|[^{}]*\}\}", "", text)
    text = re.sub(r"\{\{[Gg]ototop\}\}", "", text)
    for opener in ("{{*|", "{{zhwp|", "{{lang|"):
        text = remove_template(text, opener)
    for name in (
        "album header",
        "Album header",
        "header2",
        "Header2",
        "header",
        "Header",
        "footer",
        "Footer",
        "reflist",
        "Reflist",
    ):
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
    depth = 0
    while index < len(line):
        char = line[index]
        if char in "「『":
            depth += 1
            index += 1
            continue
        if char in "」』":
            depth = max(0, depth - 1)
            index += 1
            continue
        if char not in "。！？":
            index += 1
            continue

        end = index + 1
        projected_depth = depth
        while end < len(line) and line[end] in "」』”’）〕】》":
            if line[end] in "」』":
                projected_depth = max(0, projected_depth - 1)
            end += 1
        if (projected_depth == 0 or end - start >= LONG_PARAGRAPH_SOFT_MAX) and end - start >= LONG_PARAGRAPH_TARGET:
            chunks.append(line[start:end].strip())
            start = end
        index = end
        depth = projected_depth

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
    for line in lines:
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
    text = re.sub(r"(?<!\n)(#{2,6}\s+)", r"\n\n\1", text)
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
        if re.fullmatch(r"#{1,6}", line):
            continue
        if re.fullmatch(r">\s*回目录", line):
            continue
        kept.append(line)
    return markdown_paragraphs(kept)


def page_filename(work: Work, volume: Volume) -> str:
    return f"{work.slug}-{volume.number:03d}.md"


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

    for volume in work.volumes:
        raw = fetch_raw(volume.wiki_title)
        body = clean_body(raw)
        if not body:
            raise ValueError(f"Empty body for {work.title}/{volume.display_title}")
        write_page(
            out_dir / page_filename(work, volume),
            f"{work.title}-{volume.display_title}",
            f"{work.title}：{volume.display_title}",
            volume.number,
            work.title,
            body,
        )
        time.sleep(FETCH_DELAY)
    print(f"Generated {work.title}: {len(work.volumes)} files")


def generated_paths() -> list[Path]:
    paths = [MASTERS_DIR / "_index.md"]
    for work in WORKS.values():
        paths.append(MASTERS_DIR / work.slug / "_index.md")
        paths.extend(MASTERS_DIR / work.slug / page_filename(work, volume) for volume in work.volumes)
    return paths


def validate_front_matter(path: Path, work: Work | None, volume: Volume | None) -> None:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.S)
    if not match:
        raise ValueError(f"Missing front matter: {path}")
    front = match.group(1)
    forbidden_front = re.compile(r"^(categories|source|source_url|source_license):", flags=re.M)
    if forbidden_front.search(front):
        raise ValueError(f"Forbidden front matter in {path}")
    if "draft: true" not in front:
        raise ValueError(f"Unexpected draft state in {path}")
    if "showToc: false" not in front:
        raise ValueError(f"Unexpected showToc state in {path}")
    if work and f'tags: ["{work.title}"]' not in front:
        raise ValueError(f"Unexpected tags in {path}")
    if work and volume:
        expected_title = f'title: "{work.title}-{volume.display_title}"'
        expected_weight = f"weight: {volume.number}"
        if expected_title not in front:
            raise ValueError(f"Unexpected title in {path}")
        if expected_weight not in front:
            raise ValueError(f"Unexpected weight in {path}")


def validate() -> None:
    missing = [path for path in generated_paths() if not path.exists()]
    if missing:
        raise ValueError("Missing generated files:\n" + "\n".join(str(path) for path in missing))

    artifact = re.compile(
        r"\{\{|\}\}|\[\[|\]\]|[<>]|Category:|textquality|Textquality|"
        r"Gototop|gototop|Header|Footer|album header|onlyinclude|href=|�|[\ue000-\uf8ff]|"
        r"[A-Za-z]|^[a-z][a-z-]{1,12}:|^:|（[^）\n]{1,50}）|〔|〕|"
        r"〈|〉|○案|\[[^\]\n]+\]|__TOC__|PD-old|先秦作品|西漢作品",
        flags=re.M,
    )

    validate_front_matter(MASTERS_DIR / "_index.md", None, None)
    for work in WORKS.values():
        out_dir = MASTERS_DIR / work.slug
        validate_front_matter(out_dir / "_index.md", work, None)
        content_files = sorted(path for path in out_dir.glob("*.md") if path.name != "_index.md")
        if len(content_files) != work.expected_count:
            raise ValueError(f"Unexpected count for {work.key}: {len(content_files)}, expected {work.expected_count}")

        expected_files = [out_dir / page_filename(work, volume) for volume in work.volumes]
        if content_files != expected_files:
            raise ValueError(f"Unexpected file order for {work.key}")

        heading_count = 0
        for path, volume in zip(expected_files, work.volumes, strict=True):
            content = path.read_text(encoding="utf-8")
            match = re.match(r"^---\n.*?\n---\n", content, flags=re.S)
            assert match is not None
            body = content[match.end():].strip()
            validate_front_matter(path, work, volume)
            if not body:
                raise ValueError(f"Empty body in {path}")
            if artifact.search(body):
                raise ValueError(f"Source artifact in {path}")
            heading_count += len(re.findall(r"^#{2,6}\s+", body, flags=re.M))
            for line_number, line in enumerate(body.splitlines(), 1):
                if len(line) > MAX_RENDERED_PARAGRAPH:
                    raise ValueError(
                        f"Overlong rendered paragraph in {path}:{line_number} "
                        f"({len(line)} chars)"
                    )

        if work.expected_heading_count is not None and heading_count != work.expected_heading_count:
            raise ValueError(
                f"Unexpected heading count for {work.key}: "
                f"{heading_count}, expected {work.expected_heading_count}"
            )

    print("Masters history priority local check passed.")


def selected_works(args: argparse.Namespace) -> list[Work]:
    if args.all:
        return list(WORKS.values())
    if args.text:
        return [WORKS[args.text]]
    return []


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

    works = selected_works(args)
    if not works:
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
    for work in works:
        generate_work(work, clean=args.clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
