#!/usr/bin/env python3
"""Generate 《伤寒论》 and 《金匮要略》 content from Wikisource raw pages.

Primary text:
  - https://zh.wikisource.org/wiki/傷寒論
  - https://zh.wikisource.org/wiki/金匱要略
Cross-check sources:
  - CText: https://ctext.org/shang-han-lun/zh
  - CText: https://ctext.org/jinkui-yaolue/zh
  - Kanripo KR3e0007: 新編金匱要略方論, SBCK, 3 juan
  - Kanripo KR3e0008: 注解傷寒論, SBCK, 10 juan
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
CONTENT_DATE = "2026-06-01"
CONTENT_DRAFT = "true"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
WIKISOURCE_RAW = "https://zh.wikisource.org/w/index.php?title={}&action=raw"
FETCH_DELAY = 0.1
HEADING_CORRECTIONS = {
    "辨脉法第一": "辨脈法第一",
    "平脉法第二": "平脈法第二",
    "伤寒例第三": "傷寒例第三",
    "辨太陽病脈證並治（上）第五": "辨太陽病脈證並治法上第五",
    "辨太陽病脈證並治（中）第六": "辨太陽病脈證並治第六",
    "辨太陽病脈證並治（下）第七": "辨太陽脈證並治下第七",
    "辨陽明病脈證並治第八": "辨陽明脈證並治第八",
    "辨太陰病脈證並治第十": "辨太陰脈證並治第十",
    "辨可發汗脈證並治第十六": "辨可發汗證並治第十六",
    "痙濕暍病脈證並治第二": "痙濕暍病脈證治第二",
    "百合病狐惑陰陽毒病脈證並治第三": "百合狐惑陰陽毒病脈證治第三",
    "肺痿肺癰咳嗽上氣病脈證並治第七": "肺痿肺癰咳嗽上氣病脈證治第七",
    "奔豚氣病脈證並治第八": "奔豚氣病脈證治第八",
    "胸痹心痛短氣病脈證並治第九": "胸痹心痛短氣病脈證治第九",
    "腹滿寒疝宿食病脈證並治第十": "腹滿寒疝宿食病脈證治第十",
    "驚悸吐衄下血胸滿瘀血病脈證並治第十六": "驚悸吐衄下血胸滿瘀血病脈證治第十六",
    "嘔吐噦下利病脈證並治第十七": "嘔吐噦下利病脈證治第十七",
    "跗蹶手指臂腫轉筋陰狐疝蚘蟲病脈證並治第十九": "趺蹶手指臂腫轉筋陰狐疝蚘蟲病證治第十九",
    "婦人產後病脈證並治第二十一": "婦人產後病脈證治第二十一",
}


@dataclass(frozen=True)
class Page:
    title: str
    body: str
    volume: str = ""


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
    "shang-han-lun": Work(
        slug="shang-han-lun",
        title="伤寒论",
        raw_title="傷寒論",
        tag="伤寒论",
        weight=2,
        expected_pages=24,
        summary="伤寒论，东汉张仲景撰，晋王叔和编次。",
        index_body="《伤寒论》按序文与篇章收录。",
    ),
    "jin-kui-yao-lue": Work(
        slug="jin-kui-yao-lue",
        title="金匮要略",
        raw_title="金匱要略",
        tag="金匮要略",
        weight=3,
        expected_pages=25,
        summary="金匮要略，东汉张仲景撰，杂病方论经典。",
        index_body="《金匮要略》按二十五篇收录。",
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

    def convert_heading(match: re.Match[str]) -> str:
        marks, title = match.group(1), match.group(2).strip()
        title = HEADING_CORRECTIONS.get(title, title)
        level = min(len(marks), 6)
        return "#" * level + " " + title

    text = re.sub(r"^(={2,6})\s*(.+?)\s*\1\s*$", convert_heading, text, flags=re.M)
    text = re.sub(r"'''?", "", text)
    text = text.replace("　", "")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"^__[^_\n]+__$", "", text, flags=re.M)

    lines = [re.sub(r"^:+;?", "", line.rstrip()) for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_shang_han_lun(markdown: str) -> list[Page]:
    pages: list[Page] = []
    current_title = ""
    current_volume = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_volume, current_lines
        if not current_title:
            return
        body = "\n".join(current_lines).strip()
        if not body:
            raise ValueError(f"Empty body for {current_title}")
        pages.append(Page(current_title, body, current_volume))
        current_title = ""
        current_volume = ""
        current_lines = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading.startswith("卷第"):
                flush()
                current_volume = heading
                continue
            flush()
            current_title = heading
            current_lines = [f"## {heading}"]
            continue

        if line.startswith("### "):
            heading = line[4:].strip()
            flush()
            current_title = heading
            current_lines = [f"## {heading}"]
            continue

        if current_title:
            current_lines.append(line)

    flush()
    return pages


def split_jin_kui_yao_lue(markdown: str) -> list[Page]:
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
    write_page(
        MEDICINE_DIR / "_index.md",
        "医家",
        "医家典籍收录。",
        4,
        "医家",
        "医家典籍按书目分目录收录。",
    )


def parse_work(work: Work, markdown: str) -> list[Page]:
    if work.slug == "shang-han-lun":
        return split_shang_han_lun(markdown)
    if work.slug == "jin-kui-yao-lue":
        return split_jin_kui_yao_lue(markdown)
    raise ValueError(f"Unknown work: {work.slug}")


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

    print(f"Generated Zhongjing texts: {total} content pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
