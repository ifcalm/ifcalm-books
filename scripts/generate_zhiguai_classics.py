#!/usr/bin/env python3
"""Generate Youyang zazu, Taiping guangji, and Liaozhai zhiyi.

Textual policy:
* Youyang zazu follows the received 20-volume first collection and
  10-volume sequel on Wikisource, checked against Kanripo KR3l0125.
* Taiping guangji follows the received 500-volume Wikisource text, checked
  volume by volume against the Siku Kanripo text KR3l0118.
* Liaozhai zhiyi uses Project Gutenberg's clean 12-volume, 496-story text,
  checked against the corresponding Wikisource volumes.
* Modern notes, page furniture, categories, and editorial apparatus are
  removed. Original Taiping guangji source attributions are retained.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import io
import json
import re
import shutil
import statistics
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
MYTHOLOGY_DIR = ROOT / "content" / "posts" / "mythology"
OUTPUT_DIR = MYTHOLOGY_DIR / "zhiguai"
DATE = "2026-06-13"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
SOURCE_CACHE = Path(tempfile.gettempdir()) / "ifcalm-books-zhiguai-sources"
CACHE_MAX_AGE = 6 * 60 * 60

MEDIAWIKI_API = "https://zh.wikisource.org/w/api.php"
GUTENBERG_LIAOZHAI = "https://www.gutenberg.org/files/51828/51828-0.txt"
KANRIPO_TAIPING_ZIP = (
    "https://github.com/kanripo/KR3l0118/archive/refs/heads/master.zip"
)
KANRIPO_YOUYANG_SBCK_ZIP = (
    "https://github.com/kanripo/KR3l0125/archive/refs/heads/SBCK.zip"
)
KANRIPO_YOUYANG_WYG_ZIP = (
    "https://github.com/kanripo/KR3l0125/archive/refs/heads/WYG.zip"
)

YOUYANG_EMENDATIONS = {
    "酉陽雜俎/卷三": {
        "歡喜□蟲": "歡喜蟲",
    },
    "酉陽雜俎/卷十": {
        "闊四尺，赤如□□，每面有六龜子，□□可愛": (
            "闊四寸，赤如琥珀，每面有六龜子，燦耀可愛"
        ),
        "望見庭□忽有異光": "望見庭內忽有異光",
    },
}

TAIPING_RAW_EMENDATIONS = {
    "太平廣記/卷第090": {
        "長-{於}--{臺}-城}}": "長-{於}--{臺}-城",
        "{{ProperNoun|-{志}-}甚篤": "{{ProperNoun|-{志}-}}甚篤",
    },
}

TAIPING_BODY_EMENDATIONS = {
    "太平廣記/卷第104": {
        "日夜一遍。□□□思玄": "日夜一遍。思玄",
    },
    "太平廣記/卷第139": {
        "尋牛人立而行。聘□□□□曰": "尋牛人立而行，復曰",
    },
    "太平廣記/卷第245": {
        "□□□□□劉璋會涪": "蜀先主初與劉璋會涪",
    },
    "太平廣記/卷第247": {
        "淵以□□知名": "淵以文學知名",
    },
    "太平廣記/卷第269": {
        "建中中□李希烈": "建中中李希烈",
    },
    "太平廣記/卷第270": {
        "終身。□按": "終身。按",
    },
    "太平廣記/卷第278": {
        "重族□望": "重族望",
    },
    "太平廣記/卷第321": {
        "□城張闓": "新城張闓",
    },
    "太平廣記/卷第325": {
        "忽見□樹上": "忽見樹上",
    },
    "太平廣記/卷第452": {
        "從此而東，□□陋不□□□□□□□□□□□□□□□□□□□□，"
        "大樹出於棟間者": "從此而東，大樹出於棟間者",
    },
}

TAIPING_SUPPLEMENTED_VOLUMES = {265}

CHINESE_NUMERALS = (
    "",
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
    "十八",
    "十九",
    "二十",
    "二十一",
    "二十二",
    "二十三",
    "二十四",
    "二十五",
    "二十六",
    "二十七",
    "二十八",
    "二十九",
    "三十",
)

VARIANT_TRANSLATION = str.maketrans(
    {
        "爲": "為",
        "云": "雲",
        "内": "內",
        "羣": "群",
        "裏": "里",
        "髙": "高",
        "黄": "黃",
        "黒": "黑",
        "靑": "青",
        "説": "說",
        "毎": "每",
        "巳": "已",
        "于": "於",
        "叚": "段",
        "巻": "卷",
        "𩔖": "類",
        "𧰼": "象",
    }
)


@dataclass(frozen=True)
class Comparison:
    ratio: float
    output_coverage: float
    reference_coverage: float


def fetch_bytes(url: str, data: bytes | None = None) -> bytes:
    cache_key = hashlib.sha256(url.encode("utf-8") + b"\0" + (data or b"")).hexdigest()
    cache_file = SOURCE_CACHE / cache_key
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_MAX_AGE:
        return cache_file.read_bytes()
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read()
    SOURCE_CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(content)
    return content


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8-sig")


def fetch_wikisource_pages(titles: list[str]) -> dict[str, str]:
    pages: dict[str, str] = {}
    for offset in range(0, len(titles), 50):
        batch = titles[offset : offset + 50]
        parameters = urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "titles": "|".join(batch),
            }
        ).encode("utf-8")
        payload = json.loads(fetch_bytes(MEDIAWIKI_API, parameters))
        for page in payload["query"]["pages"]:
            if page.get("missing"):
                raise ValueError(f"missing Wikisource page: {page['title']}")
            pages[page["title"]] = page["revisions"][0]["slots"]["main"]["content"]
        print(
            f"Fetched Wikisource pages {offset + 1}-"
            f"{min(offset + 50, len(titles))}/{len(titles)}"
        )
    missing = sorted(set(titles) - set(pages))
    if missing:
        raise ValueError(f"Wikisource response omitted pages: {missing}")
    return pages


def fetch_zip_texts(url: str, filename_pattern: str) -> dict[int, str]:
    archive = zipfile.ZipFile(io.BytesIO(fetch_bytes(url)))
    result: dict[int, str] = {}
    for name in archive.namelist():
        match = re.search(filename_pattern, name)
        if not match:
            continue
        result[int(match.group(1))] = archive.read(name).decode("utf-8")
    if not result:
        raise ValueError(f"no matching texts found in {url}")
    return result


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


TemplateHandler = Callable[[str, list[str]], str]


def transform_templates(text: str, handler: TemplateHandler) -> str:
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
            # A few old pages contain triple-brace PUA constructs. Keep their
            # visible base character rather than discarding the entire page.
            output.append(text[start : start + 2])
            cursor = start + 2
            continue
        parts = split_template_parts(text[start + 2 : scan - 2])
        name = parts[0].strip()
        output.append(handler(name, parts[1:]))
        cursor = scan
    return "".join(output)


def first_argument(args: list[str], handler: TemplateHandler) -> str:
    if not args:
        return ""
    return transform_templates(args[0], handler)


def youyang_template(name: str, args: list[str]) -> str:
    if name in {"PUA", "YL", "!", "{PUA"}:
        return first_argument(args, youyang_template)
    return ""


TAIPING_BASE_READING_TEMPLATES = {
    "ProperNoun",
    "WavyBookMark",
    "YL",
    "參",
    "!",
    "?",
    "~",
    "另",
    "a",
    "-",
}


def taiping_template(name: str, args: list[str]) -> str:
    if name == "*":
        value = first_argument(args, taiping_template).strip()
        if value.startswith(("出", "（出", "(出")):
            inner = value.strip("（）()")
            inner = re.split(
                r"(?:[，。；]\s*)?(?="
                r"明抄本|明鈔本|陳校本|据談氏|據談氏|"
                r"据谈氏|據谈氏|原缺|按見|今據|並將)",
                inner,
                maxsplit=1,
            )[0].rstrip("，。；")
            if "》" in inner:
                inner = inner[: inner.find("》") + 1]
            return f"（{inner}）"
        return ""
    if name in TAIPING_BASE_READING_TEMPLATES:
        return first_argument(args, taiping_template)
    return ""


def liaozhai_template(name: str, args: list[str]) -> str:
    if name in {"另", "另2", "!", "YL", "ProperNoun"}:
        return first_argument(args, liaozhai_template)
    return ""


def expand_transclusions(raw: str, pages: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        title = match.group(1).strip()
        page = pages.get(title)
        if page is None:
            raise ValueError(f"missing transcluded page: {title}")
        onlyinclude = re.findall(
            r"<onlyinclude>([\s\S]*?)</onlyinclude>",
            page,
            flags=re.IGNORECASE,
        )
        return "\n".join(onlyinclude) if onlyinclude else page

    return re.sub(r"\{\{\s*:([^{}|]+)\s*\}\}", replace, raw)


def clean_wikitext(
    raw: str,
    handler: TemplateHandler,
    transclusions: dict[str, str] | None = None,
) -> str:
    text = raw
    if transclusions:
        text = expand_transclusions(text, transclusions)
    onlyinclude = re.findall(
        r"<onlyinclude>([\s\S]*?)</onlyinclude>",
        text,
        flags=re.IGNORECASE,
    )
    if onlyinclude:
        text = "\n".join(onlyinclude)
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    text = re.sub(
        r"<ref(?:\s[^>]*)?>[\s\S]*?</ref>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<ref(?:\s[^>]*)?/>", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"<gallery>[\s\S]*?</gallery>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Repair the three legacy {{{PUA|字}}描述} constructs before parsing.
    text = re.sub(r"\{\{\{PUA\|([^{}|]+)\}\}[^{}]*\}", r"\1", text)
    text = transform_templates(text, handler)
    text = html.unescape(text)
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(
        r"^={2,5}\s*(.*?)\s*={2,5}\s*$",
        r"\n## \1\n",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"__(?:TOC|NOTOC|NOEDITSECTION)__", "", text)
    text = re.sub(r"'''?", "", text)
    text = text.replace("本書完", "")
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
        elif stripped.startswith("## "):
            lines.append("## " + stripped[3:].strip())
        else:
            lines.append(re.sub(r"[ \t　]+", "", stripped))
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
            output.append(text[start:])
            break
        cursor = scan
    return "".join(output)


def clean_kanripo(raw: str, remove_parentheses: bool = False) -> str:
    text = remove_balanced_parentheses(raw) if remove_parentheses else raw
    text = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("¶", "")
    text = re.sub(r"&KR\d+;|⬤|□|\ufffd", "", text)
    return text


def strip_taiping_apparatus(text: str) -> str:
    text = re.sub(r"（(?!出)[^（）]*）", "", text)
    text = re.sub(r"（出字[^（）]*）", "", text)
    text = re.sub(r"\((?!出)[^()]*\)", "", text)
    text = re.sub(r"〔(?:正文)?原缺[^〕]*〕", "", text)
    text = re.sub(r"[^。！？\n]{1,12}一本作[^。！？\n]*。", "", text)
    text = re.sub(r"字原[闕缺]。據明[鈔抄]本補。", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalized_characters(text: str) -> str:
    return normalized_units(text)[0]


def normalized_units(text: str) -> tuple[str, list[str]]:
    text = re.sub(r"^##.*$", "", text, flags=re.MULTILINE)
    normalized: list[str] = []
    originals: list[str] = []
    for original in text:
        char = original.translate(VARIANT_TRANSLATION)
        if char == "爼":
            char = "俎"
        if (
            unicodedata.category(char)[0] in {"L", "N"}
            and not ("A" <= char <= "Z" or "a" <= char <= "z")
        ):
            normalized.append(char)
            originals.append(original)
    return "".join(normalized), originals


def fill_square_gaps(body: str, reference_raw: str, label: str) -> tuple[str, int, int]:
    reference, original_units = normalized_units(clean_kanripo(reference_raw))
    filled = 0
    marked = 0
    while "□" in body:
        gap = re.search(r"□+", body)
        if gap is None:
            break
        sample = normalized_characters(body)
        boundary = len(normalized_characters(body[: gap.start()]))
        blocks = difflib.SequenceMatcher(
            None,
            sample,
            reference,
            autojunk=False,
        ).get_matching_blocks()
        previous = max(
            (
                block
                for block in blocks
                if block.a + block.size <= boundary
            ),
            key=lambda block: block.a + block.size,
            default=None,
        )
        following = min(
            (block for block in blocks if block.a >= boundary),
            key=lambda block: block.a,
            default=None,
        )

        replacement = "〔闕〕"
        if (
            previous is not None
            and following is not None
            and previous.a + previous.size == boundary
            and following.a == boundary
        ):
            start = previous.b + previous.size
            end = following.b
            candidate = "".join(original_units[start:end])
            if "闕" in normalized_characters(candidate):
                replacement = "〔闕〕"
            elif len(candidate) <= max(20, len(gap.group()) * 4):
                replacement = candidate

        if replacement == "〔闕〕":
            marked += 1
        else:
            filled += 1
        body = body[: gap.start()] + replacement + body[gap.end() :]

    if "□" in body:
        raise ValueError(f"{label}: unresolved missing-character marker")
    return body, filled, marked


def aligned_reference(sample: str, reference: str) -> str:
    opening = sample[: min(160, len(sample))]
    closing = sample[max(0, len(sample) - 160) :]

    start_position: int | None = None
    for width in range(20, 5, -1):
        for offset in range(max(1, len(opening) - width + 1)):
            position = reference.find(opening[offset : offset + width])
            if position >= 0:
                start_position = max(0, position - offset)
                break
        if start_position is not None:
            break

    end_position: int | None = None
    search_end = (
        min(
            len(reference),
            start_position + max(len(sample) * 2, len(sample) + 5000),
        )
        if start_position is not None
        else len(reference)
    )
    for width in range(20, 5, -1):
        for offset in range(len(closing) - width, -1, -1):
            position = reference.rfind(
                closing[offset : offset + width],
                start_position or 0,
                search_end,
            )
            if position >= 0:
                remaining = len(closing) - offset - width
                end_position = min(len(reference), position + width + remaining)
                break
        if end_position is not None:
            break

    if start_position is None or end_position is None or end_position <= start_position:
        raise ValueError(
            f"could not align reference: start {start_position}, end {end_position}"
        )
    return reference[start_position:end_position]


def compare_text(
    body: str,
    reference_raw: str,
    *,
    align: bool = True,
    remove_parentheses: bool = False,
) -> Comparison:
    sample = normalized_characters(body)
    reference = normalized_characters(
        clean_kanripo(reference_raw, remove_parentheses=remove_parentheses)
    )
    excerpt = aligned_reference(sample, reference) if align else reference
    matcher = difflib.SequenceMatcher(None, sample, excerpt, autojunk=False)
    matching = sum(block.size for block in matcher.get_matching_blocks())
    return Comparison(
        matcher.ratio(),
        matching / len(sample),
        matching / len(excerpt),
    )


def validate_body(body: str, label: str) -> None:
    if not body.strip():
        raise ValueError(f"{label} is empty")
    artifacts = re.search(
        r"\{\{|\}\}|<ref|Category:|https?://|□|\ufffd|&KR\d+;|"
        r"__TOC__|__NOEDITSECTION__",
        body,
    )
    if artifacts:
        raise ValueError(f"{label} contains source artifact: {artifacts.group(0)!r}")


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


def parse_liaozhai(text: str) -> list[str]:
    start = text.index("卷一")
    end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"
    end = text.find(end_marker, start)
    if end < 0:
        raise ValueError("Project Gutenberg end marker not found")
    text = text[start:end].strip()
    volume_pattern = re.compile(
        r"(?m)^卷(一|二|三|四|五|六|七|八|九|十|十一|十二)\s*$"
    )
    matches = list(volume_pattern.finditer(text))
    if len(matches) != 12:
        raise ValueError(f"expected 12 Liaozhai volumes, found {len(matches)}")

    volumes: list[str] = []
    for index, match in enumerate(matches):
        volume_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : volume_end]
        lines: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            heading = re.fullmatch(r"〈([^〉]+)〉", stripped)
            if heading:
                lines.extend(["", f"## {heading.group(1)}", ""])
            elif stripped:
                lines.append(re.sub(r"^[　 ]+", "", line).rstrip())
            else:
                lines.append("")
        body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        body = body.translate(
            str.maketrans(
                {
                    "“": "「",
                    "”": "」",
                    "‘": "『",
                    "’": "』",
                }
            )
        )
        validate_body(body, f"Liaozhai volume {index + 1}")
        volumes.append(body)
    story_count = sum(len(re.findall(r"(?m)^## ", body)) for body in volumes)
    if story_count != 496:
        raise ValueError(f"expected 496 Liaozhai stories, found {story_count}")
    return volumes


def generate_youyang(
    pages: dict[str, str],
    sbck: dict[int, str],
    wyg: dict[int, str],
    minimum_coverage: float,
) -> list[str]:
    bodies: list[str] = []
    for number in range(1, 31):
        if number <= 20:
            title = f"酉陽雜俎/卷{CHINESE_NUMERALS[number]}"
        else:
            title = f"酉陽雜俎/續集/卷{CHINESE_NUMERALS[number - 20]}"
        body = clean_wikitext(pages[title], youyang_template)
        for old, new in YOUYANG_EMENDATIONS.get(title, {}).items():
            if old not in body:
                raise ValueError(f"{title}: expected source reading not found: {old!r}")
            body = body.replace(old, new)
        validate_body(body, title)
        comparisons: list[Comparison] = []
        for edition in (sbck, wyg):
            for reference_raw in edition.values():
                try:
                    comparisons.append(
                        compare_text(
                            body,
                            reference_raw,
                            align=True,
                            remove_parentheses=True,
                        )
                    )
                except ValueError:
                    # KR3l0125 has metadata-only placeholders and irregular
                    # volume boundaries. Search each witness file separately.
                    pass
        if not comparisons:
            raise ValueError(f"{title}: no usable Kanripo comparison text")
        best = max(
            comparisons,
            key=lambda item: min(item.output_coverage, item.reference_coverage),
        )
        best_output = best.output_coverage
        best_reference = best.reference_coverage
        if best_output < minimum_coverage or best_reference < 0.60:
            raise ValueError(
                f"{title}: comparison coverage "
                f"{best_output:.2%}/{best_reference:.2%} below "
                f"{minimum_coverage:.0%}/60%"
            )
        print(
            f"[Youyang {number:02d}/30] "
            f"{len(normalized_characters(body))} chars; "
            f"coverage {best_output:.2%}/{best_reference:.2%}"
        )
        bodies.append(body)
    return bodies


def generate_taiping(
    pages: dict[str, str],
    transclusions: dict[str, str],
    references: dict[int, str],
    minimum_coverage: float,
) -> list[str]:
    if sorted(references) != list(range(0, 501)):
        # KR3l0118_000 is the preface/catalogue; 001-500 are the volumes.
        required = set(range(1, 501))
        missing = sorted(required - set(references))
        if missing:
            raise ValueError(f"Kanripo Taiping volumes missing: {missing}")
    bodies: list[str] = []
    coverages: list[float] = []
    filled_gaps = 0
    marked_gaps = 0
    for number in range(1, 501):
        title = f"太平廣記/卷第{number:03d}"
        raw = pages[title]
        for old, new in TAIPING_RAW_EMENDATIONS.get(title, {}).items():
            if old not in raw:
                raise ValueError(f"{title}: expected source reading not found: {old!r}")
            raw = raw.replace(old, new)
        body = clean_wikitext(
            raw,
            taiping_template,
            transclusions=transclusions,
        )
        first_heading = body.find("## ")
        if first_heading > 0:
            body = body[first_heading:]
        body = strip_taiping_apparatus(body)
        for old, new in TAIPING_BODY_EMENDATIONS.get(title, {}).items():
            if old not in body:
                raise ValueError(f"{title}: expected source reading not found: {old!r}")
            body = body.replace(old, new)
        body, filled, marked = fill_square_gaps(
            body,
            references[number],
            title,
        )
        filled_gaps += filled
        marked_gaps += marked
        validate_body(body, title)
        supplemented = number in TAIPING_SUPPLEMENTED_VOLUMES
        try:
            comparison = compare_text(
                body,
                references[number],
                align=not supplemented,
            )
        except ValueError as error:
            raise ValueError(f"{title}: {error}") from error
        coverage = min(
            comparison.output_coverage,
            comparison.reference_coverage,
        )
        if supplemented:
            valid = (
                comparison.output_coverage >= 0.33
                and comparison.reference_coverage >= 0.50
            )
        else:
            valid = coverage >= minimum_coverage
        if not valid:
            raise ValueError(
                f"{title}: comparison coverage "
                f"{comparison.output_coverage:.2%}/"
                f"{comparison.reference_coverage:.2%} below "
                f"{minimum_coverage:.0%}"
            )
        if number == 1 or number % 25 == 0 or number == 500:
            print(
                f"[Taiping {number:03d}/500] "
                f"{len(normalized_characters(body))} chars; "
                f"coverage {comparison.output_coverage:.2%}/"
                f"{comparison.reference_coverage:.2%}"
            )
        coverages.append(coverage)
        bodies.append(body)
    print(
        "Taiping coverage: "
        f"min {min(coverages):.2%}, "
        f"median {statistics.median(coverages):.2%}; "
        f"filled {filled_gaps} source gaps, marked {marked_gaps} as lacunae"
    )
    return bodies


def generate_liaozhai(
    source_text: str,
    pages: dict[str, str],
    minimum_coverage: float,
) -> list[str]:
    bodies = parse_liaozhai(source_text)
    story_counts: list[int] = []
    for number, body in enumerate(bodies, start=1):
        title = f"聊齋志異/第{number:02d}卷"
        reference = clean_wikitext(pages[title], liaozhai_template)
        comparison = compare_text(body, reference, align=True)
        coverage = min(
            comparison.output_coverage,
            comparison.reference_coverage,
        )
        if coverage < minimum_coverage:
            raise ValueError(
                f"{title}: comparison coverage "
                f"{comparison.output_coverage:.2%}/"
                f"{comparison.reference_coverage:.2%} below "
                f"{minimum_coverage:.0%}"
            )
        stories = len(re.findall(r"(?m)^## ", body))
        story_counts.append(stories)
        print(
            f"[Liaozhai {number:02d}/12] {stories} stories, "
            f"{len(normalized_characters(body))} chars; "
            f"coverage {comparison.output_coverage:.2%}/"
            f"{comparison.reference_coverage:.2%}"
        )
    if sum(story_counts) != 496:
        raise ValueError(f"expected 496 Liaozhai stories, found {sum(story_counts)}")
    return bodies


def write_collection_indexes() -> None:
    write_index(
        OUTPUT_DIR / "_index.md",
        "志怪",
        "志怪，收录神异传闻、博物杂记与文言小说典籍。",
        20,
        "志怪",
        "志怪典籍按作品分目录收录，兼收博物杂记与神异小说。",
    )
    write_index(
        OUTPUT_DIR / "you-yang-za-zu" / "_index.md",
        "酉阳杂俎",
        "酉阳杂俎，收录前集二十卷、续集十卷。",
        10,
        "酉阳杂俎",
        "《酉阳杂俎》按传世本收录前集二十卷、续集十卷正文。",
    )
    write_index(
        OUTPUT_DIR / "tai-ping-guang-ji" / "_index.md",
        "太平广记",
        "太平广记，按传世本五百卷收录。",
        20,
        "太平广记",
        "《太平广记》按传世本五百卷收录，保留各条原有出处。"
        "传世本本身有嗤鄙、无赖、轻薄等类卷篇残缺，本次不作臆补；"
        "卷二百六十五保留谈恺初印本附录的恢复文字，"
        "校本仍缺的文字统一标作〔阙〕。",
    )
    write_index(
        OUTPUT_DIR / "liao-zhai-zhi-yi" / "_index.md",
        "聊斋志异",
        "聊斋志异，按通行十二卷本收录四百九十六篇。",
        30,
        "聊斋志异",
        "《聊斋志异》按通行十二卷本收录四百九十六篇正文，"
        "不收入后出的拾遗与评注。",
    )


def write_outputs(
    youyang: list[str],
    taiping: list[str],
    liaozhai: list[str],
) -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    write_collection_indexes()

    youyang_dir = OUTPUT_DIR / "you-yang-za-zu"
    for number, body in enumerate(youyang, start=1):
        part = "前集" if number <= 20 else "续集"
        volume = number if number <= 20 else number - 20
        title = f"酉阳杂俎 {part}卷{CHINESE_NUMERALS[volume]}"
        summary = f"《酉阳杂俎》{part}卷{volume}。"
        (youyang_dir / f"you-yang-za-zu-{number:03d}.md").write_text(
            front_matter(title, summary, number, "酉阳杂俎") + body + "\n",
            encoding="utf-8",
        )

    taiping_dir = OUTPUT_DIR / "tai-ping-guang-ji"
    for start in range(1, 501, 30):
        end = min(start + 29, 500)
        range_dir = taiping_dir / f"{start:03d}-{end:03d}"
        write_index(
            range_dir / "_index.md",
            f"太平广记 {start}-{end}",
            f"太平广记卷{start}至卷{end}。",
            start,
            "太平广记",
        )
        for number in range(start, end + 1):
            body = taiping[number - 1]
            (range_dir / f"tai-ping-guang-ji-{number:03d}.md").write_text(
                front_matter(
                    f"太平广记 卷{number}",
                    f"《太平广记》卷{number}。",
                    number,
                    "太平广记",
                )
                + body
                + "\n",
                encoding="utf-8",
            )

    liaozhai_dir = OUTPUT_DIR / "liao-zhai-zhi-yi"
    for number, body in enumerate(liaozhai, start=1):
        (liaozhai_dir / f"liao-zhai-zhi-yi-{number:03d}.md").write_text(
            front_matter(
                f"聊斋志异 卷{CHINESE_NUMERALS[number]}",
                f"《聊斋志异》卷{number}。",
                number,
                "聊斋志异",
            )
            + body
            + "\n",
            encoding="utf-8",
        )
    print(f"Wrote 542 content files to {OUTPUT_DIR}")


def generate(
    *,
    dry_run: bool = False,
    youyang_minimum: float = 0.72,
    taiping_minimum: float = 0.68,
    liaozhai_minimum: float = 0.75,
) -> None:
    youyang_titles = [
        (
            f"酉陽雜俎/卷{CHINESE_NUMERALS[number]}"
            if number <= 20
            else f"酉陽雜俎/續集/卷{CHINESE_NUMERALS[number - 20]}"
        )
        for number in range(1, 31)
    ]
    taiping_titles = [f"太平廣記/卷第{number:03d}" for number in range(1, 501)]
    transclusion_titles = ["虯髯客", "周秦行記", "楊娼傳", "非煙傳"]
    liaozhai_titles = [f"聊齋志異/第{number:02d}卷" for number in range(1, 13)]
    all_pages = fetch_wikisource_pages(
        youyang_titles + taiping_titles + transclusion_titles + liaozhai_titles
    )

    sbck = fetch_zip_texts(
        KANRIPO_YOUYANG_SBCK_ZIP,
        r"/KR3l0125_(\d{3})\.txt$",
    )
    wyg = fetch_zip_texts(
        KANRIPO_YOUYANG_WYG_ZIP,
        r"/KR3l0125_(\d{3})\.txt$",
    )
    taiping_references = fetch_zip_texts(
        KANRIPO_TAIPING_ZIP,
        r"/KR3l0118_(\d{3})\.txt$",
    )
    liaozhai_source = fetch_text(GUTENBERG_LIAOZHAI)

    youyang = generate_youyang(
        all_pages,
        sbck,
        wyg,
        youyang_minimum,
    )
    taiping = generate_taiping(
        all_pages,
        {title: all_pages[title] for title in transclusion_titles},
        taiping_references,
        taiping_minimum,
    )
    liaozhai = generate_liaozhai(
        liaozhai_source,
        all_pages,
        liaozhai_minimum,
    )

    if dry_run:
        print("Validated 30 + 500 + 12 volumes; no files written.")
        return
    write_outputs(youyang, taiping, liaozhai)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and validate all sources without writing Markdown",
    )
    parser.add_argument(
        "--youyang-minimum",
        type=float,
        default=0.72,
        help="minimum Youyang comparison coverage (default: 0.72)",
    )
    parser.add_argument(
        "--taiping-minimum",
        type=float,
        default=0.68,
        help="minimum Taiping comparison coverage (default: 0.68)",
    )
    parser.add_argument(
        "--liaozhai-minimum",
        type=float,
        default=0.75,
        help="minimum Liaozhai comparison coverage (default: 0.75)",
    )
    args = parser.parse_args()
    generate(
        dry_run=args.dry_run,
        youyang_minimum=args.youyang_minimum,
        taiping_minimum=args.taiping_minimum,
        liaozhai_minimum=args.liaozhai_minimum,
    )


if __name__ == "__main__":
    main()
