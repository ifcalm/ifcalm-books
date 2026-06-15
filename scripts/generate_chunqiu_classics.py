#!/usr/bin/env python3
"""Collect Chun Qiu and its three traditional commentaries.

Primary sources:
    Chun Qiu / Zuo Zhuan: Kanripo KR1e0001 structured main text.
    Gongyang Zhuan: Wikisource pages split by the twelve dukes of Lu.
    Guliang Zhuan: Kanripo KR1e0008 structured main text.

Chinese Text Project is used separately as a proofreading source for year
counts and representative passages.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "posts" / "confucius"
MEDIAWIKI_API = "https://zh.wikisource.org/w/api.php"
RAW_GITHUB = "https://raw.githubusercontent.com"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CONTENT_DATE = "2026-06-15"

KANRIPO_LEFT_COMMIT = "dc3dc18e0039e05679d98bc650c2f980f8dcabac"
KANRIPO_GULIANG_COMMIT = "4d929aef98a42889151c04ab5b842afef74915a1"


@dataclass(frozen=True)
class Duke:
    traditional: str
    simplified: str
    slug: str
    annals_years: int
    zuo_years: int


DUKES = [
    Duke("隱公", "隐公", "yin-gong", 11, 11),
    Duke("桓公", "桓公", "huan-gong", 18, 18),
    Duke("莊公", "庄公", "zhuang-gong", 32, 32),
    Duke("閔公", "闵公", "min-gong", 2, 2),
    Duke("僖公", "僖公", "xi-gong", 33, 33),
    Duke("文公", "文公", "wen-gong", 18, 18),
    Duke("宣公", "宣公", "xuan-gong", 18, 18),
    Duke("成公", "成公", "cheng-gong", 18, 18),
    Duke("襄公", "襄公", "xiang-gong", 31, 31),
    Duke("昭公", "昭公", "zhao-gong", 32, 32),
    Duke("定公", "定公", "ding-gong", 15, 15),
    Duke("哀公", "哀公", "ai-gong", 14, 27),
]


@dataclass(frozen=True)
class Book:
    slug: str
    title: str
    summary: str
    weight: int
    expected_years: int


BOOKS = [
    Book(
        slug="chun-qiu",
        title="春秋",
        summary="鲁国编年史，上起隐公元年，下迄哀公十四年。",
        weight=60,
        expected_years=242,
    ),
    Book(
        slug="chun-qiu-zuo-zhuan",
        title="春秋左氏传",
        summary="《春秋》三传之一，以编年叙事见长。",
        weight=70,
        expected_years=255,
    ),
    Book(
        slug="chun-qiu-gong-yang",
        title="春秋公羊传",
        summary="《春秋》三传之一，以问答阐发经义。",
        weight=80,
        expected_years=242,
    ),
    Book(
        slug="chun-qiu-gu-liang",
        title="春秋谷梁传",
        summary="《春秋》三传之一，以义例阐释经文。",
        weight=90,
        expected_years=242,
    ),
]

LEFT_HEADING_RE = re.compile(
    r"^[AB]\d+\.\d+《([隱桓莊閔僖文宣成襄昭定哀]公.+?年)(經|傳)》$"
)
GULIANG_HEADING_RE = re.compile(
    r"^\d+\.\d+《([隱桓莊閔僖文宣成襄昭定哀]公.+?年)》$"
)
YEAR_HEADING_RE = re.compile(r"^##\s+(.+?年)\s*$", re.MULTILINE)
INNER_TEMPLATE_RE = re.compile(r"\{\{([^{}]*)\}\}")
OCR_CORRUPTION = ("秂", "萅", "亖", "矦", "亰")
OCR_REPLACEMENTS = str.maketrans(
    {"秂": "年", "萅": "春", "亖": "四", "矦": "侯", "亰": "京"}
)


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def api_fetch(titles: list[str]) -> dict[str, str]:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": "|".join(titles),
    }
    request = urllib.request.Request(
        f"{MEDIAWIKI_API}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)

    pages: dict[str, str] = {}
    for page in data.get("query", {}).get("pages", []):
        if page.get("missing"):
            raise ValueError(f"Missing Wikisource page: {page['title']}")
        revisions = page.get("revisions", [])
        if not revisions:
            raise ValueError(f"No revision content for: {page['title']}")
        pages[page["title"]] = revisions[0]["slots"]["main"]["content"]
    return pages


def fetch_kanripo_files(repo: str, commit: str) -> list[str]:
    urls = [
        f"{RAW_GITHUB}/kanripo/{repo}/{commit}/{repo}_{index:03d}.txt"
        for index in range(1, 13)
    ]
    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(fetch_url, urls))


def chinese_year(number: int) -> str:
    if number == 1:
        return "元"
    digits = "零一二三四五六七八九"
    if number < 10:
        return digits[number]
    if number == 10:
        return "十"
    if number < 20:
        return "十" + digits[number - 10]
    tens, ones = divmod(number, 10)
    result = digits[tens] + "十"
    return result + (digits[ones] if ones else "")


def expected_headings(duke: Duke, count: int) -> list[str]:
    return [f"{duke.traditional}{chinese_year(year)}年" for year in range(1, count + 1)]


def strip_kanripo_markup(line: str) -> str:
    line = re.sub(r"<pb:[^>]+>", "", line)
    line = line.replace("¶", "").strip().lstrip("〔")
    line = re.sub(
        r"^[「『]?(?:[AB]\d+(?:\.\d+){0,2}|\d+(?:\.\d+){2})",
        "",
        line,
    )
    line = line.replace("(corr.=", "").replace("j司徒", "司徒")
    line = line.replace("『『", "『")
    return line


def join_paragraphs(paragraphs: list[str]) -> str:
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def parse_kanripo_left(raw: str, duke: Duke) -> tuple[str, dict[str, dict[str, str]]]:
    preamble: list[str] = []
    years: dict[str, dict[str, list[str]]] = {}
    current_year: str | None = None
    current_kind: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        paragraph = "".join(buffer).strip()
        buffer.clear()
        if not paragraph:
            return
        if current_year is None:
            preamble.append(paragraph)
        elif current_kind is not None:
            years[current_year][current_kind].append(paragraph)

    for raw_line in raw.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            flush()
            continue

        line = (
            re.sub(r"<pb:[^>]+>", "", raw_line)
            .replace("¶", "")
            .strip()
            .lstrip("〔")
        )
        if not line:
            flush()
            continue
        if line.startswith(("#+", "** ")) or line == "B《傳》":
            flush()
            continue

        heading = LEFT_HEADING_RE.fullmatch(line)
        if heading:
            flush()
            current_year, current_kind = heading.groups()
            years.setdefault(current_year, {"經": [], "傳": []})
            continue

        line = strip_kanripo_markup(line)
        if line:
            buffer.append(line)

    flush()
    headings = list(years)
    expected = expected_headings(duke, duke.zuo_years)
    if headings != expected:
        raise ValueError(
            f"Kanripo Zuo Zhuan {duke.traditional}: "
            f"expected headings {expected}, found {headings}"
        )

    rendered: dict[str, dict[str, str]] = {}
    for index, heading in enumerate(headings, start=1):
        sections = years[heading]
        annals = join_paragraphs(sections["經"])
        transmission = join_paragraphs(sections["傳"])
        if index <= duke.annals_years and not annals:
            raise ValueError(f"Kanripo Zuo Zhuan {heading}: missing 經")
        if not transmission:
            raise ValueError(f"Kanripo Zuo Zhuan {heading}: missing 傳")
        rendered[heading] = {"經": annals, "傳": transmission}
    return join_paragraphs(preamble), rendered


def parse_kanripo_guliang(raw: str, duke: Duke) -> dict[str, str]:
    years: dict[str, list[str]] = {}
    current_year: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if not buffer or current_year is None:
            buffer.clear()
            return
        paragraph = "".join(buffer).strip()
        buffer.clear()
        if paragraph:
            years[current_year].append(paragraph)

    for raw_line in raw.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            flush()
            continue

        line = (
            re.sub(r"<pb:[^>]+>", "", raw_line)
            .replace("¶", "")
            .strip()
            .lstrip("〔")
        )
        if not line:
            flush()
            continue
        if line.startswith(("#+", "** ")):
            flush()
            continue

        heading = GULIANG_HEADING_RE.fullmatch(line)
        if heading:
            flush()
            current_year = heading.group(1)
            years[current_year] = []
            continue

        line = strip_kanripo_markup(line)
        if line:
            buffer.append(line)

    flush()
    headings = list(years)
    expected = expected_headings(duke, duke.annals_years)
    if headings != expected:
        raise ValueError(
            f"Kanripo Guliang Zhuan {duke.traditional}: "
            f"expected headings {expected}, found {headings}"
        )

    rendered = {heading: join_paragraphs(years[heading]) for heading in headings}
    empty = [heading for heading, text in rendered.items() if not text]
    if empty:
        raise ValueError(f"Kanripo Guliang Zhuan empty years: {empty}")
    return rendered


def replace_template(match: re.Match[str]) -> str:
    inner = match.group(1).strip()
    name, separator, payload = inner.partition("|")
    if not separator:
        return ""
    if name.strip() in {"*", "+"}:
        return payload
    return ""


def clean_wikisource(raw: str) -> str:
    text = re.split(r"^==\s*斠勘\s*==\s*$", raw, maxsplit=1, flags=re.MULTILINE)[0]
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)
    text = re.sub(r"^.*\[\[\.\./.*(?:上一篇|回目录).*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\[\[Category:.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)

    for _ in range(100):
        text, count = INNER_TEMPLATE_RE.subn(replace_template, text)
        if count == 0:
            break
    if "{{" in text or "}}" in text:
        raise ValueError("Residual or unbalanced Wikisource template markup")

    text = re.sub(r"</?onlyinclude\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref\b[^>]*/>", "", text)
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"^----+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^__\w+__\s*$", "", text, flags=re.MULTILINE)

    def convert_heading(match: re.Match[str]) -> str:
        return f"## {match.group(2).strip()}"

    text = re.sub(
        r"^(={2})\s*(.+?)\s*\1\s*$",
        convert_heading,
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"'''?", "", text)
    text = text.replace("　", "").replace("​", "").replace("&nbsp;", " ")
    text = text.translate(OCR_REPLACEMENTS)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_year_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    matches = list(YEAR_HEADING_RE.finditer(text))
    if not matches:
        raise ValueError("No year headings found")
    preamble = text[: matches[0].start()].strip()
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.end() : end].strip()))
    return preamble, sections


def render_left(
    preamble: str,
    years: dict[str, dict[str, str]],
) -> str:
    rendered = [preamble] if preamble else []
    for heading, sections in years.items():
        parts = [f"## {heading}"]
        if sections["經"]:
            parts.extend(["### 經", sections["經"]])
        parts.extend(["### 傳", sections["傳"]])
        rendered.append("\n\n".join(parts))
    return "\n\n".join(rendered)


def render_annals(years: dict[str, dict[str, str]], count: int) -> str:
    rendered = []
    for heading, sections in list(years.items())[:count]:
        if not sections["經"]:
            raise ValueError(f"Missing annals text for {heading}")
        rendered.append(f"## {heading}\n\n{sections['經']}")
    return "\n\n".join(rendered)


def render_combined(years: dict[str, str]) -> str:
    return "\n\n".join(f"## {heading}\n\n{text}" for heading, text in years.items())


def validate_body(book: Book, duke: Duke, body: str) -> None:
    _, sections = split_year_sections(body)
    expected = duke.zuo_years if book.slug == "chun-qiu-zuo-zhuan" else duke.annals_years
    if len(sections) != expected:
        raise ValueError(
            f"{book.title} {duke.simplified}: expected {expected} years, "
            f"found {len(sections)}"
        )

    forbidden = ("{{", "}}", "[[", "]]", "<pb:", "Category:", "# src:", "&KR")
    for token in (*forbidden, *OCR_CORRUPTION):
        if token in body:
            raise ValueError(f"{book.title} {duke.simplified}: residual {token!r}")
    if re.search(r"[A-Za-z0-9]", body):
        raise ValueError(f"{book.title} {duke.simplified}: residual ASCII metadata")


def front_matter(title: str, summary: str, weight: int, tag: str) -> str:
    return f"""---
title: "{title}"
date: {CONTENT_DATE}
weight: {weight}
tags: ["{tag}"]
draft: true
summary: "{summary}"
showToc: false
tocOpen: false
ShowShareButtons: false
---
"""


def build_outputs() -> dict[Path, str]:
    left_files = fetch_kanripo_files("KR1e0001", KANRIPO_LEFT_COMMIT)
    guliang_files = fetch_kanripo_files("KR1e0008", KANRIPO_GULIANG_COMMIT)
    gongyang_pages = api_fetch(
        [f"春秋公羊傳/{duke.traditional}" for duke in DUKES]
    )

    left: dict[str, tuple[str, dict[str, dict[str, str]]]] = {}
    guliang: dict[str, dict[str, str]] = {}
    gongyang: dict[str, str] = {}
    for index, duke in enumerate(DUKES):
        left[duke.traditional] = parse_kanripo_left(left_files[index], duke)
        guliang[duke.traditional] = parse_kanripo_guliang(guliang_files[index], duke)
        gongyang[duke.traditional] = clean_wikisource(
            gongyang_pages[f"春秋公羊傳/{duke.traditional}"]
        )

    outputs: dict[Path, str] = {}
    for book in BOOKS:
        directory = CONTENT_ROOT / book.slug
        outputs[directory / "_index.md"] = front_matter(
            book.title,
            book.summary,
            book.weight,
            book.title,
        )
        total_years = 0

        for weight, duke in enumerate(DUKES, start=1):
            preamble, left_years = left[duke.traditional]
            if book.slug == "chun-qiu":
                body = render_annals(left_years, duke.annals_years)
            elif book.slug == "chun-qiu-zuo-zhuan":
                body = render_left(preamble, left_years)
            elif book.slug == "chun-qiu-gong-yang":
                body = gongyang[duke.traditional]
            else:
                body = render_combined(guliang[duke.traditional])

            validate_body(book, duke, body)
            _, sections = split_year_sections(body)
            total_years += len(sections)

            title = f"{book.title}-{duke.simplified}"
            summary = f"{book.title}：{duke.simplified}"
            path = directory / f"{book.slug}-{duke.slug}.md"
            outputs[path] = (
                front_matter(title, summary, weight, book.title)
                + "\n"
                + body
                + "\n"
            )

        if total_years != book.expected_years:
            raise ValueError(
                f"{book.title}: expected {book.expected_years} years, "
                f"found {total_years}"
            )
    return outputs


def generated_paths() -> set[Path]:
    paths: set[Path] = set()
    for book in BOOKS:
        directory = CONTENT_ROOT / book.slug
        if directory.exists():
            paths.update(directory.glob("*.md"))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if generated files are missing or out of date",
    )
    args = parser.parse_args()

    outputs = build_outputs()
    expected_paths = set(outputs)
    if args.check:
        stale = [
            path.relative_to(ROOT)
            for path, content in outputs.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        extras = sorted(generated_paths() - expected_paths)
        if stale or extras:
            lines = [*(f"- outdated: {path}" for path in stale)]
            lines.extend(f"- unexpected: {path.relative_to(ROOT)}" for path in extras)
            raise SystemExit("Chun Qiu collections are out of date:\n" + "\n".join(lines))
        print("Chun Qiu collections are up to date: 4 books, 48 content files.")
        return

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print("Collected Chun Qiu and Three Commentaries: 4 books, 48 content files.")


if __name__ == "__main__":
    main()
