#!/usr/bin/env python3
"""Collect the Zhong Yong text and arrange it as the received 33 chapters.

Primary text:
    Chinese Text Project, ctp:liji/zhong-yong
Chapter-boundary reference:
    Wikisource, 四書章句集註/中庸章句
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "content" / "posts" / "confucius" / "zhong-yong"
CTEXT_URL = "https://api.ctext.org/gettext?urn=ctp:liji/zhong-yong"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CONTENT_DATE = "2026-06-15"

CHAPTER_NUMERALS = [
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八",
    "十九", "二十", "二十一", "二十二", "二十三", "二十四",
    "二十五", "二十六", "二十七", "二十八", "二十九", "三十",
    "三十一", "三十二", "三十三",
]
PROOFREADING_CORRECTIONS = {
    "今夫山，一拳石之多": "今夫山，一卷石之多",
    "威儀三千，待其人然後行": "威儀三千，待其人而後行",
    "極高明而中庸": "極高明而道中庸",
    "君子所不可及者": "君子之所不可及者",
}


def fetch_ctext() -> list[str]:
    request = urllib.request.Request(CTEXT_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)

    paragraphs = data.get("fulltext")
    if not isinstance(paragraphs, list) or len(paragraphs) != 39:
        raise ValueError(
            "Expected 39 CText paragraphs for ctp:liji/zhong-yong, "
            f"found {len(paragraphs) if isinstance(paragraphs, list) else 'none'}"
        )
    return [str(paragraph).strip() for paragraph in paragraphs]


def split_at(text: str, marker: str) -> tuple[str, str]:
    if text.count(marker) != 1:
        raise ValueError(f"Expected one split marker {marker!r}")
    before, after = text.split(marker, 1)
    return before.strip(), (marker + after).strip()


def arrange_chapters(paragraphs: list[str]) -> list[str]:
    chapters = paragraphs[:13]
    chapters[10] = chapters[10].rstrip() + "」"
    chapters[11] = chapters[11].removesuffix("」")

    chapter_14 = paragraphs[13].removesuffix("」")
    shooting, chapter_15 = split_at(paragraphs[14], "君子之道")
    shooting += "」"
    chapter_15 = chapter_15.replace("樂爾妻帑。』」子曰", "樂爾妻帑。』子曰")
    chapters.extend([f"{chapter_14}{shooting}", chapter_15])

    chapters.extend(paragraphs[15:19])
    chapters.append("\n\n".join(paragraphs[19:22]))

    chapter_21, chapter_22 = split_at(paragraphs[22], "唯天下至誠")
    chapters.extend([chapter_21, chapter_22])
    chapters.extend(paragraphs[23:25])

    chapter_25, chapter_26_start = split_at(paragraphs[25], "故至誠無息")
    chapters.append(chapter_25)
    chapters.append(f"{chapter_26_start}\n\n{paragraphs[26]}")
    chapters.append(paragraphs[27])

    chapter_28_end, chapter_29 = split_at(paragraphs[29], "王天下有三重焉")
    chapters.append(f"{paragraphs[28]}{chapter_28_end}")
    chapters.append(chapter_29)

    chapters.extend(paragraphs[30:33])
    chapters.append("\n\n".join(paragraphs[33:39]))

    chapters[12] = chapters[12].rstrip() + "」"

    if len(chapters) != 33:
        raise ValueError(f"Expected 33 arranged chapters, found {len(chapters)}")
    if not chapters[0].startswith("天命之謂性"):
        raise ValueError("Unexpected opening text")
    if "上天之載，無聲無臭" not in chapters[-1]:
        raise ValueError("Unexpected closing text")
    source_characters = re.sub(r"[^\u3400-\u9fff]", "", "".join(paragraphs))
    chapter_characters = re.sub(r"[^\u3400-\u9fff]", "", "".join(chapters))
    if chapter_characters != source_characters:
        raise ValueError("The 33-chapter arrangement changed the source character sequence")

    for source_text, corrected_text in PROOFREADING_CORRECTIONS.items():
        matches = sum(chapter.count(source_text) for chapter in chapters)
        if matches != 1:
            raise ValueError(
                f"Expected one occurrence of proofreading text {source_text!r}, "
                f"found {matches}"
            )
        chapters = [
            chapter.replace(source_text, corrected_text)
            for chapter in chapters
        ]

    for number, chapter in enumerate(chapters, start=1):
        for opening, closing in (("「", "」"), ("『", "』")):
            if chapter.count(opening) != chapter.count(closing):
                raise ValueError(
                    f"Chapter {number} has unbalanced {opening}{closing} quotes"
                )
    return chapters


def index_markdown() -> str:
    return f"""---
title: "中庸"
date: {CONTENT_DATE}
weight: 40
tags: ["中庸"]
draft: true
summary: "天命之谓性，率性之谓道，修道之谓教。"
showToc: false
tocOpen: false
ShowShareButtons: false
---
"""


def page_markdown(chapters: list[str]) -> str:
    body = "\n\n".join(
        f"### 第{numeral}章\n\n{chapter}"
        for numeral, chapter in zip(CHAPTER_NUMERALS, chapters, strict=True)
    )
    return f"""---
title: "中庸"
date: {CONTENT_DATE}
weight: 1
tags: ["中庸"]
draft: true
summary: "天命之谓性，率性之谓道，修道之谓教。"
showToc: false
tocOpen: false
ShowShareButtons: false
---

{body}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the remote source and fail if local files are out of date",
    )
    args = parser.parse_args()

    chapters = arrange_chapters(fetch_ctext())
    expected = {
        OUTPUT_DIR / "_index.md": index_markdown(),
        OUTPUT_DIR / "zhong-yong.md": page_markdown(chapters),
    }

    if args.check:
        stale = [
            path.relative_to(ROOT)
            for path, content in expected.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            raise SystemExit(
                "Outdated Zhong Yong files:\n"
                + "\n".join(f"- {path}" for path in stale)
            )
        print("Zhong Yong collection is up to date: 33 chapters.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8")
    print("Collected Zhong Yong: 33 chapters in 1 content file.")


if __name__ == "__main__":
    main()
