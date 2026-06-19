#!/usr/bin/env python3
"""Close out the core Jingbu texts.

This script does three scoped jobs:

* add the five standalone Yi Zhuan pieces missing from the local Yi Jing tree;
* rebuild Lun Yu and Mengzi from Kanripo正文 repositories;
* rebuild Da Xue from the clean Wikisource Li Ji witness.

Zhong Yong already has a dedicated generator and is checked separately.
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
CONFUCIUS_DIR = ROOT / "content" / "posts" / "confucius"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CONTENT_DATE = "2026-06-19"
INDEX_DRAFT = "true"
DEFAULT_PAGE_DRAFT = "true"
PUBLISHED_PAGE_DRAFT = "false"
FETCH_DELAY = 0.05

RAW_GITHUB = "https://raw.githubusercontent.com"
WIKISOURCE_RAW = "https://zh.wikisource.org/w/index.php"


@dataclass(frozen=True)
class SimpleWork:
    slug: str
    title: str
    summary: str
    weight: int
    index_body: str


@dataclass(frozen=True)
class YiAppendix:
    title: str
    slug: str
    wiki_title: str
    weight: int


@dataclass(frozen=True)
class MengziBook:
    title: str
    slug: str
    weight: int
    kanripo_indexes: tuple[int, int]
    summary: str


YI_APPENDICES = [
    YiAppendix("繫辭上傳", "xi-ci-shang", "易傳/繫辭上", 65),
    YiAppendix("繫辭下傳", "xi-ci-xia", "易傳/繫辭下", 66),
    YiAppendix("說卦傳", "shuo-gua", "易傳/說卦", 67),
    YiAppendix("序卦傳", "xu-gua", "易傳/序卦", 68),
    YiAppendix("雜卦傳", "za-gua", "易傳/雜卦", 69),
]

YI_LOWER_WEIGHTS = {
    "xian": 31,
    "heng": 32,
    "dun": 33,
    "dazhuang": 34,
    "jin": 35,
    "mingyi": 36,
    "jiaren": 37,
    "kui": 38,
    "jian": 39,
    "xie": 40,
    "sun": 41,
    "yi-increase": 42,
    "guai": 43,
    "gou": 44,
    "cui": 45,
    "sheng": 46,
    "kun-exhaustion": 47,
    "jing": 48,
    "ge": 49,
    "ding": 50,
    "zhen": 51,
    "gen": 52,
    "jian-gradual": 53,
    "guimei": 54,
    "feng": 55,
    "lv-travel": 56,
    "xun": 57,
    "dui": 58,
    "huan": 59,
    "jie": 60,
    "zhongfu": 61,
    "xiaoguo": 62,
    "jiji": 63,
    "weiji": 64,
}

LUNYU_CHAPTERS = [
    "學而", "為政", "八佾", "里仁", "公冶長",
    "雍也", "述而", "泰伯", "子罕", "鄉黨",
    "先進", "顏淵", "子路", "憲問", "衛靈公",
    "季氏", "陽貨", "微子", "子張", "堯曰",
]

MENGZI_BOOKS = [
    MengziBook("梁惠王", "lianghuiwang", 1, (1, 2), "孟子：梁惠王"),
    MengziBook("公孫丑", "gongsunchou", 2, (3, 4), "孟子：公孫丑"),
    MengziBook("滕文公", "tenwengong", 3, (5, 6), "孟子：滕文公"),
    MengziBook("離婁", "lilou", 4, (7, 8), "孟子：離婁"),
    MengziBook("萬章", "wanzhang", 5, (9, 10), "孟子：萬章"),
    MengziBook("告子", "gaozi", 6, (11, 12), "孟子：告子"),
    MengziBook("盡心", "jingxin", 7, (13, 14), "孟子：盡心"),
]

LUNYU_COLLATIONS = {
    "孝弟也者，其為人之本與": "孝弟也者，其為仁之本與",
    "汎愛眾，而親人": "汎愛眾，而親仁",
}

WORKS = {
    "yi-jing": SimpleWork(
        "yi-jing",
        "易经",
        "天行健，君子以自強不息；地勢坤，君子以厚德載物。",
        1,
        "《易经》按传统次序收录上经三十卦、下经三十四卦，并补入独立易传五篇。",
    ),
    "lun-yu": SimpleWork(
        "lun-yu",
        "论语",
        "学而时习之，不亦说乎。",
        30,
        "《论语》按二十篇收录正文。",
    ),
    "mengzi": SimpleWork(
        "mengzi",
        "孟子",
        "孟子七篇，战国孟轲撰。",
        50,
        "《孟子》按七篇收录正文，各篇含上、下两章。",
    ),
    "da-xue": SimpleWork(
        "da-xue",
        "大学",
        "大学之道，在明明德。",
        20,
        "《大学》据《礼记》传世篇目收录正文。",
    ),
}


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_kanripo(repo: str, index: int) -> str:
    url = f"{RAW_GITHUB}/kanripo/{repo}/master/{repo}_{index:03d}.txt"
    return fetch_text(url)


def fetch_wikisource_raw(title: str, follow_redirects: int = 3) -> str:
    current = title
    for _ in range(follow_redirects + 1):
        query = urllib.parse.urlencode({"title": current, "action": "raw"})
        raw = fetch_text(f"{WIKISOURCE_RAW}?{query}")
        redirect = re.search(r"^#(?:重定向|redirect)\s*\[\[([^]]+)\]\]", raw, flags=re.I)
        if not redirect:
            return raw
        current = redirect.group(1)
    raise ValueError(f"Too many Wikisource redirects for {title}")


def dump_yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(
    title: str,
    summary: str,
    weight: int,
    tag: str,
    *,
    draft: str,
    show_toc: bool = False,
) -> str:
    show_toc_text = "true" if show_toc else "false"
    return f"""---
title: {dump_yaml_string(title)}
date: {CONTENT_DATE}
weight: {weight}
tags: {json.dumps([tag], ensure_ascii=False)}
draft: {draft}
summary: {dump_yaml_string(summary)}
showToc: {show_toc_text}
tocOpen: false
ShowShareButtons: false
---

"""


def write_index(work: SimpleWork) -> None:
    out_dir = CONFUCIUS_DIR / work.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_index.md").write_text(
        front_matter(work.title, work.summary, work.weight, work.title, draft=INDEX_DRAFT) + work.index_body + "\n",
        encoding="utf-8",
    )


def page_draft_value(publish_pages: bool) -> str:
    return PUBLISHED_PAGE_DRAFT if publish_pages else DEFAULT_PAGE_DRAFT


def write_page(
    path: Path,
    title: str,
    summary: str,
    weight: int,
    tag: str,
    body: str,
    *,
    draft: str = DEFAULT_PAGE_DRAFT,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(title, summary, weight, tag, draft=draft) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def normalize_yijing_hexagram_metadata() -> None:
    """Keep the existing 64 hexagrams in whole-book order."""
    yijing_dir = CONFUCIUS_DIR / "yi-jing"
    for path in sorted((yijing_dir / "upper").glob("*.md")) + sorted((yijing_dir / "lower").glob("*.md")):
        if path.name == "_index.md" or not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        text = re.sub(r'^(summary:\s*")(?:(?:alt|alr)=\S+\s*)', r"\1", original, count=1, flags=re.M)

        if path.parent.name != "lower":
            if text != original:
                path.write_text(text, encoding="utf-8")
            continue

        weight = YI_LOWER_WEIGHTS.get(path.stem)
        if weight is not None:
            text = re.sub(r"^weight:\s*\d+\s*$", f"weight: {weight}", text, count=1, flags=re.M)
        if text != original:
            path.write_text(text, encoding="utf-8")


def strip_wikisource_markup(raw: str, *, drop_after: str | None = None) -> str:
    text = clean_wikitext(raw)
    if drop_after and drop_after in text:
        text = text.split(drop_after, 1)[0].rstrip()
    text = re.sub(r"</?onlyinclude\b[^>]*>", "", text)
    text = re.sub(r"</?poem\b[^>]*>", "", text)
    text = re.sub(r"</?[a-zA-Z][^>\n]*>", "", text)
    text = re.sub(r"^Category:.*$", "", text, flags=re.M)
    text = re.sub(r"^[a-z][a-z-]{1,12}:[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"^\|[A-Za-z_-]+=[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"\{\{[^}]+\}\}", "", text)
    text = text.replace("{{", "").replace("}}", "")
    text = re.sub(r"周易/([\u3400-\u9fff]+)", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_wikisource_lines(text: str) -> str:
    output: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if output and output[-1] != "":
                output.append("")
            continue

        heading = re.match(r"^(###\s+(?:第[一二三四五六七八九十百]+章|[上下一]篇))\s+(.+)$", line)
        if heading:
            output.extend([heading.group(1), "", strip_leading_list_markers(heading.group(2))])
            continue

        if line.startswith("### "):
            output.append(line)
            continue

        output.append(strip_leading_list_markers(line))

    return "\n".join(output).strip()


def strip_leading_list_markers(line: str) -> str:
    while line.startswith((':', '#', '*')):
        line = line[1:].lstrip()
    return line


def clean_yi_appendix(raw: str, appendix: YiAppendix) -> str:
    drop_after = "### 校詁版" if appendix.slug == "za-gua" else None
    text = strip_wikisource_markup(raw, drop_after=drop_after)
    text = normalize_wikisource_lines(text)
    if "#重定向" in text or "校詁版" in text:
        raise ValueError(f"Unexpected residual text in {appendix.title}")
    return text


def clean_daxue(raw: str) -> str:
    text = strip_wikisource_markup(raw)
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    if len(paragraphs) < 8 or not paragraphs[0].startswith("大學之道"):
        raise ValueError("Unexpected Da Xue text from Wikisource")
    return "\n\n".join(paragraphs)


def preprocess_kanripo(raw: str) -> list[str]:
    text = re.sub(r"# src:.*?# dating:\s*\d+\s*", "", raw)
    text = re.sub(r"# src:[^¶\n<]*", "", text)
    text = re.sub(r"<pb:[^>]+>", "\n", text)
    text = text.replace("¶", "\n")

    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def parse_kanripo_numbered(raw: str) -> tuple[str, list[str]]:
    title = ""
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        paragraph = "".join(current)
        paragraph = re.sub(r"\s+", "", paragraph).strip()
        current.clear()
        if paragraph:
            paragraphs.append(paragraph)

    for line in preprocess_kanripo(raw):
        heading = re.match(r"^\*\*\s+\d+\s+《(.+?)》\s*(.*)$", line)
        if heading:
            title = heading.group(1)
            line = heading.group(2).strip()
            if not line:
                continue

        numbered = re.match(r"^\d+\.\d+\s*(.*)$", line)
        if numbered:
            flush()
            current.append(numbered.group(1))
            continue

        if line.startswith("** "):
            continue
        current.append(line)

    flush()
    if not title or not paragraphs:
        raise ValueError("Could not parse Kanripo numbered file")
    return title, paragraphs


def title_without_piece_number(title: str) -> str:
    return re.sub(r"篇第[一二三四五六七八九十]+$", "", title)


def render_numbered_section(title: str, paragraphs: list[str]) -> str:
    return f"### {title}\n\n" + "\n\n".join(paragraphs)


def apply_lunyu_collations(text: str) -> str:
    for source, replacement in LUNYU_COLLATIONS.items():
        text = text.replace(source, replacement)
    return text


def generate_yijing(clean: bool = False, publish_pages: bool = False) -> None:
    work = WORKS["yi-jing"]
    draft = page_draft_value(publish_pages)
    write_index(work)

    appendix_dir = CONFUCIUS_DIR / "yi-jing" / "appendix"
    if clean and appendix_dir.exists():
        shutil.rmtree(appendix_dir)
    appendix_dir.mkdir(parents=True, exist_ok=True)
    (appendix_dir / "_index.md").write_text(
        front_matter("易经-易传", "《易经》独立传文。", 3, "易经", draft=INDEX_DRAFT)
        + "《易传》此处收录未并入六十四卦正文的五篇传文。",
        encoding="utf-8",
    )

    for appendix in YI_APPENDICES:
        body = clean_yi_appendix(fetch_wikisource_raw(appendix.wiki_title), appendix)
        write_page(
            appendix_dir / f"{appendix.slug}.md",
            f"易经-{appendix.title}",
            f"易经：{appendix.title}",
            appendix.weight,
            "易经",
            body,
            draft=draft,
        )
        time.sleep(FETCH_DELAY)

    for path in (CONFUCIUS_DIR / "yi-jing").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        expected_draft = INDEX_DRAFT if path.name == "_index.md" else draft
        text = re.sub(r"^draft:\s*(?:true|false)\s*$", f"draft: {expected_draft}", text, flags=re.M)
        path.write_text(text, encoding="utf-8")
    normalize_yijing_hexagram_metadata()


def generate_lunyu(clean: bool = False, publish_pages: bool = False) -> None:
    work = WORKS["lun-yu"]
    out_dir = CONFUCIUS_DIR / work.slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    write_index(work)

    sections: list[str] = []
    for index, expected_title in enumerate(LUNYU_CHAPTERS, start=1):
        raw = fetch_kanripo("KR1h0004", index)
        title, paragraphs = parse_kanripo_numbered(raw)
        title = title_without_piece_number(title)
        if title != expected_title:
            raise ValueError(f"Expected Lun Yu chapter {expected_title}, found {title}")
        sections.append(render_numbered_section(title, paragraphs))
        time.sleep(FETCH_DELAY)

    body = apply_lunyu_collations("\n\n".join(sections))
    write_page(out_dir / "lun-yu.md", "论语", work.summary, 1, "论语", body, draft=page_draft_value(publish_pages))


def generate_mengzi(clean: bool = False, publish_pages: bool = False) -> None:
    work = WORKS["mengzi"]
    out_dir = CONFUCIUS_DIR / work.slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    write_index(work)

    for book in MENGZI_BOOKS:
        sections: list[str] = []
        for index in book.kanripo_indexes:
            raw = fetch_kanripo("KR1h0001", index)
            title, paragraphs = parse_kanripo_numbered(raw)
            if not title.startswith(book.title):
                raise ValueError(f"Expected Mengzi chapter {book.title}, found {title}")
            sections.append(render_numbered_section(title, paragraphs))
            time.sleep(FETCH_DELAY)
        write_page(
            out_dir / f"mengzi-{book.slug}.md",
            f"孟子-{book.title}",
            book.summary,
            book.weight,
            "孟子",
            "\n\n".join(sections),
            draft=page_draft_value(publish_pages),
        )


def generate_daxue(clean: bool = False, publish_pages: bool = False) -> None:
    work = WORKS["da-xue"]
    out_dir = CONFUCIUS_DIR / work.slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    write_index(work)
    body = clean_daxue(fetch_wikisource_raw("禮記/大學"))
    write_page(out_dir / "da-xue.md", "大学", work.summary, 1, "大学", body, draft=page_draft_value(publish_pages))


def generated_paths() -> list[Path]:
    paths = [
        CONFUCIUS_DIR / "yi-jing" / "appendix" / "_index.md",
        *(CONFUCIUS_DIR / "yi-jing" / "appendix" / f"{item.slug}.md" for item in YI_APPENDICES),
        CONFUCIUS_DIR / "lun-yu" / "_index.md",
        CONFUCIUS_DIR / "lun-yu" / "lun-yu.md",
        CONFUCIUS_DIR / "mengzi" / "_index.md",
        *(CONFUCIUS_DIR / "mengzi" / f"mengzi-{book.slug}.md" for book in MENGZI_BOOKS),
        CONFUCIUS_DIR / "da-xue" / "_index.md",
        CONFUCIUS_DIR / "da-xue" / "da-xue.md",
    ]
    return list(paths)


def validate_no_artifacts(paths: list[Path], *, publish_pages: bool = False) -> None:
    artifact = re.compile(
        r"\{\{|\}\}|\[\[|\]\]|<[^>]+>|Category:|顯示相似段落|"
        r"打開字典|dictionary\.pl|text\.pl|href=|ERR_|�|[\ue000-\uf8ff]|"
        r"^[a-z][a-z-]{1,12}:",
        flags=re.M,
    )
    forbidden_front = re.compile(r"^(categories|source|source_url|source_license):", flags=re.M)

    for path in paths:
        content = path.read_text(encoding="utf-8")
        front_match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.S)
        if not front_match:
            raise ValueError(f"Missing front matter: {path}")
        front = front_match.group(1)
        body = content[front_match.end():].strip()
        if forbidden_front.search(front):
            raise ValueError(f"Forbidden front matter in {path}")
        expected_draft = INDEX_DRAFT if path.name == "_index.md" else page_draft_value(publish_pages)
        if f"draft: {expected_draft}" not in front:
            raise ValueError(f"Expected draft: {expected_draft} in {path}")
        if artifact.search(body):
            raise ValueError(f"Source artifact found in {path}")
        if not body:
            raise ValueError(f"Empty body in {path}")


def check_local(*, publish_pages: bool = False) -> None:
    paths = generated_paths()
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise SystemExit("Missing generated files:\n" + "\n".join(str(path) for path in missing))
    validate_no_artifacts(paths, publish_pages=publish_pages)
    counts = {
        "yi-jing": len([p for p in (CONFUCIUS_DIR / "yi-jing").rglob("*.md") if p.name != "_index.md"]),
        "lun-yu": len([p for p in (CONFUCIUS_DIR / "lun-yu").glob("*.md") if p.name != "_index.md"]),
        "mengzi": len([p for p in (CONFUCIUS_DIR / "mengzi").glob("*.md") if p.name != "_index.md"]),
        "da-xue": len([p for p in (CONFUCIUS_DIR / "da-xue").glob("*.md") if p.name != "_index.md"]),
    }
    expected = {"yi-jing": 69, "lun-yu": 1, "mengzi": 7, "da-xue": 1}
    if counts != expected:
        raise ValueError(f"Unexpected content counts: {counts}")

    lunyu_body = (CONFUCIUS_DIR / "lun-yu" / "lun-yu.md").read_text(encoding="utf-8")
    if lunyu_body.count("\n### ") != 20:
        raise ValueError("Expected 20 Lun Yu headings")
    mengzi_headings = sum(
        path.read_text(encoding="utf-8").count("\n### ")
        for path in (CONFUCIUS_DIR / "mengzi").glob("mengzi-*.md")
    )
    if mengzi_headings != 14:
        raise ValueError("Expected 14 Mengzi upper/lower headings")
    print("Jingbu closure local check passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Generate Yi Jing appendices and the three rebuilt works")
    parser.add_argument("--text", choices=["yi-jing", "lun-yu", "mengzi", "da-xue"], help="Generate one work")
    parser.add_argument("--clean", action="store_true", help="Remove generated target directories before writing")
    parser.add_argument("--check", action="store_true", help="Check local generated output")
    parser.add_argument(
        "--publish-pages",
        action="store_true",
        help="Generate or check non-index pages as published while keeping _index.md draft",
    )
    args = parser.parse_args()

    if args.check:
        check_local(publish_pages=args.publish_pages)
        return 0

    if not args.all and not args.text:
        parser.print_help()
        return 0

    if args.all or args.text == "yi-jing":
        generate_yijing(clean=args.clean, publish_pages=args.publish_pages)
        print("Generated Yi Jing appendices: 5 files")
    if args.all or args.text == "lun-yu":
        generate_lunyu(clean=args.clean, publish_pages=args.publish_pages)
        print("Generated Lun Yu: 20 chapters in 1 file")
    if args.all or args.text == "mengzi":
        generate_mengzi(clean=args.clean, publish_pages=args.publish_pages)
        print("Generated Mengzi: 7 files with 14 sections")
    if args.all or args.text == "da-xue":
        generate_daxue(clean=args.clean, publish_pages=args.publish_pages)
        print("Generated Da Xue: 1 file")

    return 0


if __name__ == "__main__":
    sys.exit(main())
