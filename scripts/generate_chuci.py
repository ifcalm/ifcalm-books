#!/usr/bin/env python3
"""Generate the 17-volume Chuci text with source cross-checks.

Primary character source:
    Kanripo KR4a0002, Chuci zhangju, Sibu Congkan edition.

Punctuation and paragraph source:
    Chinese Wikisource, Chuci buzhu, volumes 1-17.

The Wikisource pages are used only after all commentary templates and
prefatory material have been removed. Each extracted volume is normalized
and compared with the Kanripo base text before any Markdown is written.
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
LITERATURE_DIR = ROOT / "content" / "posts" / "literature"
OUTPUT_DIR = LITERATURE_DIR / "chuci" / "chu-ci"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
DATE = "2026-06-11"

WIKISOURCE_RAW = "https://zh.wikisource.org/w/index.php?title={}&action=raw"
KANRIPO_RAW = (
    "https://raw.githubusercontent.com/kanripo/KR4a0002/"
    "master/KR4a0002_{volume:03d}.txt"
)


@dataclass(frozen=True)
class Volume:
    number: int
    title: str
    traditional_title: str
    sections: tuple[str, ...] = ()


VOLUMES = (
    Volume(1, "离骚", "離騷"),
    Volume(
        2,
        "九歌",
        "九歌",
        (
            "東皇太一",
            "雲中君",
            "湘君",
            "湘夫人",
            "大司命",
            "少司命",
            "東君",
            "河伯",
            "山鬼",
            "國殤",
            "禮魂",
        ),
    ),
    Volume(3, "天问", "天問"),
    Volume(
        4,
        "九章",
        "九章",
        (
            "惜誦",
            "涉江",
            "哀郢",
            "抽思",
            "懷沙",
            "思美人",
            "惜往日",
            "橘頌",
            "悲回風",
        ),
    ),
    Volume(5, "远游", "遠遊"),
    Volume(6, "卜居", "卜居"),
    Volume(7, "渔父", "漁父"),
    Volume(8, "九辩", "九辯"),
    Volume(9, "招魂", "招魂"),
    Volume(10, "大招", "大招"),
    Volume(11, "惜誓", "惜誓"),
    Volume(12, "招隐士", "招隱士"),
    Volume(
        13,
        "七谏",
        "七諫",
        ("初放", "沈江", "怨世", "怨思", "自悲", "哀命", "謬諫"),
    ),
    Volume(14, "哀时命", "哀時命"),
    Volume(
        15,
        "九怀",
        "九懷",
        ("匡機", "通路", "危俊", "昭世", "尊嘉", "蓄英", "思忠", "陶壅", "株昭"),
    ),
    Volume(
        16,
        "九叹",
        "九歎",
        ("逢紛", "離世", "怨思", "遠逝", "惜賢", "憂苦", "愍命", "思古", "遠遊"),
    ),
    Volume(
        17,
        "九思",
        "九思",
        ("逢尤", "怨上", "疾世", "憫上", "遭厄", "悼亂", "傷時", "哀歲", "守志"),
    ),
)

CHINESE_VOLUME_NUMBERS = (
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
    "十一",
    "十二",
    "十三",
    "十四",
    "十五",
    "十六",
    "十七",
)

VARIANT_TRANSLATION = str.maketrans(
    {
        "髙": "高",
        "逺": "遠",
        "淸": "清",
        "妬": "妒",
        "皷": "鼓",
        "羣": "群",
        "爲": "為",
        "於": "于",
    }
)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_wikisource(volume: int) -> str:
    title = f"楚辭補註/卷第{CHINESE_VOLUME_NUMBERS[volume - 1]}"
    return fetch(WIKISOURCE_RAW.format(urllib.parse.quote(title)))


def fetch_kanripo(volume: int) -> str:
    return fetch(KANRIPO_RAW.format(volume=volume))


def remove_balanced(text: str, opener: str, closer: str) -> str:
    """Remove all balanced blocks, including nested blocks."""
    output: list[str] = []
    cursor = 0
    while cursor < len(text):
        start = text.find(opener, cursor)
        if start < 0:
            output.append(text[cursor:])
            break
        output.append(text[cursor:start])
        depth = 0
        scan = start
        while scan < len(text):
            if text.startswith(opener, scan):
                depth += 1
                scan += len(opener)
                continue
            if text.startswith(closer, scan):
                depth -= 1
                scan += len(closer)
                if depth == 0:
                    break
                continue
            scan += 1
        if depth:
            raise ValueError(f"unbalanced block beginning at character {start}")
        cursor = scan
    return "".join(output)


def clean_wikisource_lines(raw: str) -> list[str]:
    """Remove headers, commentary templates, navigation, and markup."""
    text = remove_balanced(raw, "{{", "}}")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_marker(line: str) -> str:
    return line.lstrip(":　 ").strip()


def find_introduction(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        normalized = normalize_marker(line)
        if line.startswith(":") and "者" in normalized:
            return index
    raise ValueError("could not locate Wang Yi's introduction")


def extract_volume(
    volume: Volume, lines: list[str]
) -> tuple[list[tuple[str | None, list[str]]], str]:
    """Return ordered sections and unformatted source text."""
    introduction = find_introduction(lines)
    body_lines = lines[introduction + 1 :]

    if not volume.sections:
        selected: list[str] = []
        for line in body_lines:
            if line.startswith(":"):
                break
            selected.append(line)
        if not selected:
            raise ValueError("no body text found")
        return [(None, selected)], "\n".join(selected)

    blocks: list[tuple[str | None, list[str]]] = []
    accumulated: list[str] = []
    section_index = 0

    for line in body_lines:
        marker = normalize_marker(line)
        if section_index < len(volume.sections) and marker == volume.sections[section_index]:
            if not accumulated:
                raise ValueError(f"empty section before {marker}")
            blocks.append((marker, accumulated))
            accumulated = []
            section_index += 1
            continue
        if line.startswith(":"):
            break
        accumulated.append(line)

    if section_index != len(volume.sections):
        missing = volume.sections[section_index:]
        raise ValueError(f"missing section markers: {', '.join(missing)}")

    # Some volumes place a collection-wide luan after the final title marker.
    if accumulated:
        blocks[-1][1].extend(accumulated)

    plain_text = "\n".join(
        line for _section, section_lines in blocks for line in section_lines
    )
    return blocks, plain_text


def sentence_paragraphs(lines: list[str]) -> str:
    text = "".join(lines).strip()
    text = re.sub(r"[ \t　]+", "", text)
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[。！？])", text)
        if part.strip()
    ]
    return "\n\n".join(sentences)


def markdown_body(blocks: list[tuple[str | None, list[str]]]) -> str:
    rendered: list[str] = []
    for section, lines in blocks:
        if section:
            rendered.append(f"## {section}")
        rendered.append(sentence_paragraphs(lines))
    return "\n\n".join(rendered).strip()


def clean_kanripo(raw: str) -> str:
    text = remove_balanced(raw, "(", ")")
    text = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"<pb:[^>]+>", "", text)
    text = text.replace("¶", "")
    return text


def normalized_characters(text: str) -> str:
    text = re.sub(r"&KR\d+;", "", text)
    text = text.translate(VARIANT_TRANSLATION)
    return "".join(
        char
        for char in text
        if unicodedata.category(char)[0] in {"L", "N"}
        and not ("A" <= char <= "Z" or "a" <= char <= "z")
    )


def locate_anchor(reference: str, sample: str, from_end: bool = False) -> int:
    """Locate a stable short substring near either end of sample."""
    edge = sample[-100:] if from_end else sample[:100]
    for width in range(14, 5, -1):
        starts = range(len(edge) - width, -1, -1) if from_end else range(len(edge) - width + 1)
        for start in starts:
            fragment = edge[start : start + width]
            position = reference.rfind(fragment) if from_end else reference.find(fragment)
            if position >= 0:
                return position + (width if from_end else 0)
    side = "ending" if from_end else "opening"
    raise ValueError(f"could not locate {side} anchor in Kanripo text")


def compare_with_kanripo(volume: int, body: str, kanripo_raw: str) -> tuple[float, float]:
    sample = normalized_characters(body)
    reference = normalized_characters(clean_kanripo(kanripo_raw))
    start = locate_anchor(reference, sample)
    end = locate_anchor(reference, sample, from_end=True)
    if end <= start:
        raise ValueError("invalid Kanripo comparison range")
    reference_excerpt = reference[start:end]
    matcher = difflib.SequenceMatcher(None, sample, reference_excerpt)
    matching_characters = sum(block.size for block in matcher.get_matching_blocks())
    reference_coverage = matching_characters / len(reference_excerpt)
    return matcher.ratio(), reference_coverage


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


def write_index(path: Path, title: str, summary: str, weight: int, tag: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = front_matter(title, summary, weight, tag)
    if body:
        content += body.strip() + "\n"
    path.write_text(content, encoding="utf-8")


def generate(dry_run: bool = False, minimum_coverage: float = 0.94) -> tuple[int, int]:
    results: list[tuple[Volume, str, float, float]] = []
    total_sections = 0

    for volume in VOLUMES:
        wikisource_raw = fetch_wikisource(volume.number)
        blocks, plain_text = extract_volume(
            volume, clean_wikisource_lines(wikisource_raw)
        )
        similarity, coverage = compare_with_kanripo(
            volume.number, plain_text, fetch_kanripo(volume.number)
        )
        if coverage < minimum_coverage:
            raise ValueError(
                f"volume {volume.number} {volume.title}: "
                f"Kanripo coverage {coverage:.2%} below {minimum_coverage:.0%}"
            )
        body = markdown_body(blocks)
        if any(marker in body for marker in ("{{", "}}", "□", "\ufffd")):
            raise ValueError(f"volume {volume.number} contains unresolved text artifacts")
        total_sections += len(volume.sections) or 1
        results.append((volume, body, similarity, coverage))
        print(
            f"[{volume.number:02d}/17] {volume.title}: "
            f"{len(normalized_characters(plain_text))} chars, "
            f"Kanripo coverage {coverage:.2%}, similarity {similarity:.2%}"
        )

    if total_sections != 65:
        raise ValueError(f"expected 65 works/sections, found {total_sections}")

    if dry_run:
        print(f"Validated 17 volumes and {total_sections} works/sections; no files written.")
        return len(results), 0

    write_index(
        LITERATURE_DIR / "_index.md",
        "集部",
        "集部，收录楚辞、别集、总集、诗文评与词曲等中国古代文学典籍。",
        6,
        "集部",
    )
    write_index(
        LITERATURE_DIR / "chuci" / "_index.md",
        "楚辞类",
        "楚辞类，收录《楚辞》及相关作品。",
        10,
        "楚辞",
    )

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    write_index(
        OUTPUT_DIR / "_index.md",
        "楚辞",
        "楚辞，按王逸《楚辞章句》十七卷次序收录。",
        10,
        "楚辞",
        "《楚辞》按王逸《楚辞章句》十七卷次序收录正文。",
    )

    for volume, body, _similarity, _coverage in results:
        title = f"楚辞 {volume.title}"
        summary = f"《楚辞》卷{volume.number}《{volume.title}》。"
        output = OUTPUT_DIR / f"chu-ci-{volume.number:03d}.md"
        output.write_text(
            front_matter(title, summary, volume.number, "楚辞") + body + "\n",
            encoding="utf-8",
        )

    print(f"Wrote 17 volumes and {total_sections} works/sections to {OUTPUT_DIR}")
    return len(results), 0


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
        default=0.94,
        help="minimum normalized Kanripo character coverage (default: 0.94)",
    )
    args = parser.parse_args()
    generate(dry_run=args.dry_run, minimum_coverage=args.minimum_coverage)


if __name__ == "__main__":
    main()
