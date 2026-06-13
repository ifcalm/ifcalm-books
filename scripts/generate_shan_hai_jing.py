#!/usr/bin/env python3
"""Generate the 18 received chapters of the Shanhai jing.

Textual policy:
* Chapter order follows the received Guo Pu edition.
* Punctuation and paragraphing come from the standalone Wikisource pages.
* Commentary, editorial notes, galleries, and modern rearrangements are removed.
* Every chapter is compared with both the Sibu Congkan and Siku Kanripo texts.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MYTHOLOGY_DIR = ROOT / "content" / "posts" / "mythology"
OUTPUT_DIR = MYTHOLOGY_DIR / "ancient" / "shan-hai-jing"
DATE = "2026-06-13"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"

WIKISOURCE_RAW = "https://zh.wikisource.org/w/index.php?title={}&action=raw"
KANRIPO_SBCK = (
    "https://raw.githubusercontent.com/kanripo/KR5d0054/"
    "SBCK/KR5d0054_{volume:03d}.txt"
)
KANRIPO_WYG = (
    "https://raw.githubusercontent.com/kanripo/KR3l0090/"
    "WYG/KR3l0090_{volume:03d}.txt"
)


@dataclass(frozen=True)
class Chapter:
    number: int
    title: str
    traditional_title: str


CHAPTERS = (
    Chapter(1, "南山经", "南山經"),
    Chapter(2, "西山经", "西山經"),
    Chapter(3, "北山经", "北山經"),
    Chapter(4, "东山经", "東山經"),
    Chapter(5, "中山经", "中山經"),
    Chapter(6, "海外南经", "海外南經"),
    Chapter(7, "海外西经", "海外西經"),
    Chapter(8, "海外北经", "海外北經"),
    Chapter(9, "海外东经", "海外東經"),
    Chapter(10, "海内南经", "海內南經"),
    Chapter(11, "海内西经", "海內西經"),
    Chapter(12, "海内北经", "海內北經"),
    Chapter(13, "海内东经", "海內東經"),
    Chapter(14, "大荒东经", "大荒東經"),
    Chapter(15, "大荒南经", "大荒南經"),
    Chapter(16, "大荒西经", "大荒西經"),
    Chapter(17, "大荒北经", "大荒北經"),
    Chapter(18, "海内经", "海內經"),
)

# Wikisource exposes some textual variants as two template branches. The first
# five chapters' first branches and the remaining chapters' second branches
# agree most closely with both received editions used for validation.
VARIANT_CHOICES = {
    chapter.number: 1 if chapter.number <= 5 else 2
    for chapter in CHAPTERS
}

VARIANT_TRANSLATION = str.maketrans(
    {
        "髙": "高",
        "摇": "搖",
        "揺": "搖",
        "内": "內",
        "歳": "歲",
        "爲": "為",
        "于": "於",
        "峯": "峰",
        "羣": "群",
        "靣": "面",
        "状": "狀",
        "黒": "黑",
        "産": "產",
        "逺": "遠",
        "淸": "清",
        "説": "說",
        "畵": "畫",
        "吕": "呂",
        "卧": "臥",
        "飢": "饑",
        "栁": "柳",
        "栢": "柏",
        "鷄": "雞",
        "靑": "青",
    }
)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_wikisource(title: str) -> str:
    page = urllib.parse.quote(f"山海經/{title}")
    return fetch(WIKISOURCE_RAW.format(page))


def split_template_parts(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    cursor = 0
    while cursor < len(text):
        if text.startswith("{{", cursor):
            depth += 1
            current.append("{{")
            cursor += 2
        elif text.startswith("}}", cursor):
            depth -= 1
            current.append("}}")
            cursor += 2
        elif text[cursor] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            cursor += 1
        else:
            current.append(text[cursor])
            cursor += 1
    parts.append("".join(current))
    return parts


def transform_templates(text: str, variant_choice: int = 1) -> str:
    """Remove notes while retaining the selected base reading of variant templates."""
    output: list[str] = []
    cursor = 0
    while cursor < len(text):
        start = text.find("{{", cursor)
        if start < 0:
            output.append(text[cursor:])
            break
        output.append(text[cursor:start])
        depth = 0
        scan = start
        while scan < len(text):
            if text.startswith("{{", scan):
                depth += 1
                scan += 2
                continue
            if text.startswith("}}", scan):
                depth -= 1
                scan += 2
                if depth == 0:
                    break
                continue
            scan += 1
        if depth:
            raise ValueError(f"unbalanced template at character {start}")

        parts = split_template_parts(text[start + 2 : scan - 2])
        name = parts[0].strip()
        if name == "另" and len(parts) > 1:
            choice = min(variant_choice, len(parts) - 1)
            output.append(transform_templates(parts[choice], variant_choice))
        elif name in {"另2", "!"} and len(parts) > 1:
            # 另2's later fields are editorial notes; !'s later fields are
            # ideographic descriptions used only when a character cannot render.
            output.append(transform_templates(parts[1], variant_choice))
        cursor = scan
    return "".join(output)


def clean_wikisource(raw: str, variant_choice: int = 1) -> list[str]:
    text = re.sub(r"<!--[\s\S]*?-->", "", raw)
    text = re.sub(
        r"<ref(?:\s[^>]*)?>[\s\S]*?</ref>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"<gallery>[\s\S]*?</gallery>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = transform_templates(text, variant_choice)
    text = re.sub(r"<references\s*/?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"^==+\s*(.*?)\s*==+\s*$", r"\n## \1\n", text, flags=re.MULTILINE)
    text = re.sub(r"^Category:.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^https?://.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"'''?", "", text)
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            lines.append("## " + line[3:].strip())
        else:
            lines.append(re.sub(r"[ \t　]+", "", line))
    text = "\n".join(lines)
    text = text.replace("【】", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return [block.strip() for block in text.split("\n\n") if block.strip()]


def block_starting(blocks: list[str], prefix: str) -> str:
    for block in blocks:
        if block.startswith(prefix):
            return block
    raise ValueError(f"missing paragraph beginning {prefix!r}")


def block_range(blocks: list[str], start: str, end: str) -> list[str]:
    start_index = next(
        (index for index, block in enumerate(blocks) if block.startswith(start)),
        None,
    )
    end_index = next(
        (index for index, block in enumerate(blocks) if block.startswith(end)),
        None,
    )
    if start_index is None or end_index is None or end_index < start_index:
        raise ValueError(f"invalid paragraph range: {start!r} through {end!r}")
    return blocks[start_index : end_index + 1]


def remove_page_heading(blocks: list[str], title: str) -> list[str]:
    return [
        block
        for block in blocks
        if block not in {f"## {title}", "## 註釋"}
        and not block.startswith("Category:")
    ]


def restore_received_order(all_blocks: dict[int, list[str]]) -> dict[int, list[str]]:
    """Undo the modern rearrangement used on Wikisource chapters 11-13."""
    result = dict(all_blocks)

    chapter_11 = remove_page_heading(all_blocks[11], "海內西經")
    snake_index = next(
        index
        for index, block in enumerate(chapter_11)
        if block.startswith("蛇巫之山")
    )
    result[11] = chapter_11[:snake_index]

    chapter_12 = remove_page_heading(all_blocks[12], "海內北經")
    chapter_13_first = clean_wikisource(fetch_wikisource("海內東經"), 1)
    chapter_13_first = remove_page_heading(chapter_13_first, "海內東經")
    chapter_11_all = remove_page_heading(all_blocks[11], "海內西經")

    result[12] = [
        block_starting(chapter_12, "海內西北陬以東者"),
        block_starting(chapter_11_all, "蛇巫之山"),
        block_starting(chapter_11_all, "西王母梯几"),
        *block_range(chapter_12, "有人曰大行伯", "王子夜之尸"),
        block_starting(chapter_12, "舜妻登比氏"),
        block_starting(chapter_13_first, "蓋國在鉅燕南"),
        block_starting(chapter_13_first, "列姑射在海河"),
        *block_range(chapter_13_first, "姑射國在海中", "大人之市在海中"),
    ]

    chapter_13 = remove_page_heading(all_blocks[13], "海內東經")
    result[13] = [
        *block_range(chapter_13, "海內東北陬以南者", "漳水出山陽東"),
        block_starting(chapter_13, "建平元年四月丙戌"),
    ]
    return result


def remove_balanced_parentheses(text: str) -> str:
    output: list[str] = []
    cursor = 0
    while cursor < len(text):
        start = text.find("(", cursor)
        if start < 0:
            output.append(text[cursor:])
            break
        output.append(text[cursor:start])
        depth = 0
        scan = start
        while scan < len(text):
            if text[scan] == "(":
                depth += 1
            elif text[scan] == ")":
                depth -= 1
                if depth == 0:
                    scan += 1
                    break
            scan += 1
        if depth:
            raise ValueError(f"unbalanced annotation at character {start}")
        cursor = scan
    return "".join(output)


def clean_kanripo(raw: str) -> str:
    text = remove_balanced_parentheses(raw)
    text = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("¶", "")
    text = re.sub(r"&KR\d+;|⬤|□|\ufffd", "", text)
    return text


def normalized_characters(text: str) -> str:
    text = text.translate(VARIANT_TRANSLATION)
    text = re.sub(r"^##.*$", "", text, flags=re.MULTILINE)
    return "".join(
        char
        for char in text
        if unicodedata.category(char)[0] in {"L", "N"}
        and not ("A" <= char <= "Z" or "a" <= char <= "z")
    )


def aligned_reference(sample: str, reference: str) -> str:
    """Estimate chapter boundaries inside a reference containing headings."""
    opening = sample[: min(120, len(sample))]
    closing_start = max(0, len(sample) - 120)
    closing = sample[closing_start:]

    start_position: int | None = None
    start_offset = 0
    for width in range(18, 5, -1):
        for offset in range(max(1, len(opening) - width + 1)):
            position = reference.find(opening[offset : offset + width])
            if position >= 0:
                start_position = max(0, position - offset)
                start_offset = offset
                break
        if start_position is not None:
            break

    end_position: int | None = None
    for width in range(18, 5, -1):
        for offset in range(len(closing) - width, -1, -1):
            position = reference.rfind(closing[offset : offset + width])
            if position >= 0:
                remaining = len(closing) - offset - width
                end_position = min(len(reference), position + width + remaining)
                break
        if end_position is not None:
            break

    if start_position is None or end_position is None or end_position <= start_position:
        raise ValueError(
            f"could not align reference (opening offset {start_offset}, "
            f"start {start_position}, end {end_position})"
        )
    return reference[start_position:end_position]


def compare_text(body: str, reference_raw: str) -> tuple[float, float, float]:
    sample = normalized_characters(body)
    reference = normalized_characters(clean_kanripo(reference_raw))
    excerpt = aligned_reference(sample, reference)
    matcher = difflib.SequenceMatcher(None, sample, excerpt)
    matching = sum(block.size for block in matcher.get_matching_blocks())
    return (
        matcher.ratio(),
        matching / len(sample),
        matching / len(excerpt),
    )


def front_matter(title: str, summary: str, weight: int, tag: str) -> str:
    return f"""---
title: {json.dumps(title, ensure_ascii=False)}
date: {DATE}
weight: {weight}
tags: [{json.dumps(tag, ensure_ascii=False)}]
draft: true
summary: {json.dumps(summary, ensure_ascii=False)}
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def write_index(
    path: Path,
    title: str,
    summary: str,
    weight: int,
    tag: str,
    body: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = front_matter(title, summary, weight, tag)
    if body:
        content += body.strip() + "\n"
    path.write_text(content, encoding="utf-8")


def generate(dry_run: bool = False, minimum_coverage: float = 0.85) -> None:
    raw_blocks: dict[int, list[str]] = {}
    for chapter in CHAPTERS:
        variant_choice = VARIANT_CHOICES[chapter.number]
        blocks = clean_wikisource(
            fetch_wikisource(chapter.traditional_title),
            variant_choice,
        )
        raw_blocks[chapter.number] = remove_page_heading(
            blocks,
            chapter.traditional_title,
        )

    ordered = restore_received_order(raw_blocks)
    generated: list[tuple[Chapter, str]] = []

    for chapter in CHAPTERS:
        body = "\n\n".join(ordered[chapter.number]).strip()
        if not body:
            raise ValueError(f"chapter {chapter.number} is empty")
        if re.search(
            r"\{\{|\}\}|<ref|註釋|Category:|https?://|□|\ufffd|&KR\d+;",
            body,
        ):
            raise ValueError(f"chapter {chapter.number} contains source artifacts")

        sbck = compare_text(
            body,
            fetch(KANRIPO_SBCK.format(volume=chapter.number)),
        )
        wyg = compare_text(
            body,
            fetch(KANRIPO_WYG.format(volume=chapter.number)),
        )
        minimum_reference_coverage = min(sbck[2], wyg[2])
        best_output_coverage = max(sbck[1], wyg[1])
        if minimum_reference_coverage < minimum_coverage:
            raise ValueError(
                f"chapter {chapter.number} {chapter.title}: "
                f"minimum reference coverage {minimum_reference_coverage:.2%} below "
                f"{minimum_coverage:.0%}"
            )
        if best_output_coverage < 0.80:
            raise ValueError(
                f"chapter {chapter.number} {chapter.title}: "
                f"best output coverage {best_output_coverage:.2%} below 80%"
            )

        print(
            f"[{chapter.number:02d}/18] {chapter.title}: "
            f"{len(normalized_characters(body))} chars; "
            f"SBCK {sbck[0]:.2%}/{sbck[1]:.2%}/{sbck[2]:.2%}; "
            f"WYG {wyg[0]:.2%}/{wyg[1]:.2%}/{wyg[2]:.2%}"
        )
        generated.append((chapter, body))

    if dry_run:
        print("Validated 18 chapters; no files written.")
        return

    write_index(
        MYTHOLOGY_DIR / "_index.md",
        "神话",
        "神话，收录中国古代神话、神怪地理、神仙传记与志怪典籍。",
        7,
        "神话",
        "中国神话典籍按上古神话、神仙传记、志怪故事等主题逐步收录。",
    )
    write_index(
        MYTHOLOGY_DIR / "ancient" / "_index.md",
        "上古神话",
        "上古神话，收录先秦至两汉形成的神话与神怪地理典籍。",
        10,
        "神话",
    )

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    write_index(
        OUTPUT_DIR / "_index.md",
        "山海经",
        "山海经，按郭璞注本传世次序收录十八篇正文。",
        10,
        "山海经",
        "《山海经》按传世郭璞注本次序分为十八篇，本次仅收经文，不收入郭璞注。",
    )

    for chapter, body in generated:
        output = OUTPUT_DIR / f"shan-hai-jing-{chapter.number:03d}.md"
        output.write_text(
            front_matter(
                f"山海经 {chapter.title}",
                f"《山海经》卷{chapter.number}《{chapter.title}》。",
                chapter.number,
                "山海经",
            )
            + body
            + "\n",
            encoding="utf-8",
        )
    print(f"Wrote 18 chapters to {OUTPUT_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and validate all sources without writing Markdown",
    )
    parser.add_argument(
        "--minimum-coverage",
        type=float,
        default=0.85,
        help="minimum surviving-reference character coverage (default: 0.85)",
    )
    args = parser.parse_args()
    generate(
        dry_run=args.dry_run,
        minimum_coverage=args.minimum_coverage,
    )


if __name__ == "__main__":
    main()
