#!/usr/bin/env python3
"""Generate 二十四史 from rendered Wikisource pages.

The old raw-wikitext path was brittle for redirects, split pages, and tables.
This generator asks MediaWiki to render pages first, then converts the visible
article body to Markdown so templates and tables are not silently discarded.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from setup_history_structure import HISTORIES


ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "content" / "posts" / "history"
API = "https://zh.wikisource.org/w/api.php"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
DATE = "2026-05-24"

WIKI_TITLES = {
    "shi-ji": "史記",
    "han-shu": "漢書",
    "hou-han-shu": "後漢書",
    "san-guo-zhi": "三國志",
    "jin-shu": "晉書",
    "song-shu": "宋書",
    "nan-qi-shu": "南齊書",
    "liang-shu": "梁書",
    "chen-shu": "陳書",
    "wei-shu": "魏書",
    "bei-qi-shu": "北齊書",
    "zhou-shu": "周書",
    "sui-shu": "隋書",
    "nan-shi": "南史",
    "bei-shi": "北史",
    "jiu-tang-shu": "舊唐書",
    "xin-tang-shu": "新唐書",
    "jiu-wu-dai-shi": "舊五代史",
    "xin-wu-dai-shi": "新五代史",
    "song-shi": "宋史",
    "liao-shi": "遼史",
    "jin-shi": "金史",
    "yuan-shi": "元史",
    "ming-shi": "明史",
}

CHINESE_NUM = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

PART_ORDER = {
    "": 0,
    "上": 10,
    "中": 20,
    "下": 30,
    "甲": 40,
    "乙": 50,
    "丙": 60,
    "丁": 70,
    "b": 80,
}


def api_query(params: dict[str, object], retries: int = 4) -> dict:
    query = urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(2 + attempt * 3)
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries:
                time.sleep(2 + attempt * 3)
                continue
            raise
    raise RuntimeError("unreachable")


def chinese_int(text: str) -> int | None:
    if not text:
        return None
    if text == "十":
        return 10
    total = 0
    current = 0
    for ch in text:
        if ch == "百":
            total += (current or 1) * 100
            current = 0
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch in CHINESE_NUM:
            current = CHINESE_NUM[ch]
        else:
            return None
    return total + current


def volume_from_title(title: str) -> int | None:
    marker = "/卷"
    if marker not in title:
        return None
    rest = title.split(marker, 1)[1]
    m = re.match(r"0*(\d+)", rest)
    if m:
        return int(m.group(1))

    m = re.match(r"([零〇一二三四五六七八九十百]+)", rest)
    if m:
        return chinese_int(m.group(1))

    return None


def part_sort_key(title: str) -> tuple[int, str]:
    rest = title.split("/卷", 1)[1] if "/卷" in title else title
    rest = re.sub(r"^0*\d+", "", rest)
    rest = re.sub(r"^[零〇一二三四五六七八九十百]+", "", rest)

    if rest.startswith("/第"):
        m = re.match(r"/第([零〇一二三四五六七八九十百]+)部分", rest)
        n = chinese_int(m.group(1)) if m else 99
        return (100 + (n or 99), title)

    if rest.startswith("之"):
        n = chinese_int(rest[1:])
        return (n or 90, title)

    if rest in PART_ORDER:
        return (PART_ORDER[rest], title)

    m = re.match(r"([上中下甲乙丙丁])之([上下])", rest)
    if m:
        return (PART_ORDER[m.group(1)] + (1 if m.group(2) == "上" else 2), title)

    return (90, title)


def volume_group_dir(vol: int, total: int, chunk: int = 30) -> str:
    start = ((vol - 1) // chunk) * chunk + 1
    end = min(start + chunk - 1, total)
    return f"{start:03d}-{end:03d}"


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def write_frontmatter(
    path: Path,
    title: str,
    summary: str,
    weight: int,
    tags: list[str],
    categories: list[str] | None = None,
    body: str = "",
) -> None:
    categories = categories or ["史部"]
    content = "\n".join(
        [
            "---",
            f"title: {yaml_string(title)}",
            f"date: {DATE}",
            f"weight: {weight}",
            f"tags: {yaml_list(tags)}",
            f"categories: {yaml_list(categories)}",
            "draft: false",
            f"summary: {yaml_string(summary)}",
            "showToc: false",
            "tocOpen: false",
            "ShowShareButtons: false",
            "---",
            "",
            body.rstrip(),
        ]
    ).rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_indexes() -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    write_frontmatter(
        OUT_BASE / "_index.md",
        "二十四史",
        "二十四史，中国古代各朝撰写的二十四部史书的总称。",
        5,
        ["二十四史", "史部"],
    )

    for idx, hist in enumerate(HISTORIES, start=1):
        hist_dir = OUT_BASE / hist["slug"]
        tags = [hist["title"], hist["dynasty"]]
        write_frontmatter(
            hist_dir / "_index.md",
            hist["title"],
            hist["summary"],
            idx * 10,
            tags,
        )

        for group_idx, start in enumerate(range(1, hist["volumes"] + 1, 30), start=1):
            end = min(start + 29, hist["volumes"])
            group_name = f"{start:03d}-{end:03d}"
            write_frontmatter(
                hist_dir / group_name / "_index.md",
                f"{hist['title']} 卷{start}-{end}",
                f"{hist['title']}卷{start}至卷{end}。",
                group_idx,
                [hist["title"]],
            )


class WikisourceHtmlExtractor(HTMLParser):
    """Small HTML-to-Markdown extractor for MediaWiki parser output."""

    SKIP_TAGS = {"style", "script", "noscript"}
    SKIP_IDS = {
        "headerContainer",
        "catlinks",
        "mw-navigation",
        "footer",
        "licenseContainer",
    }
    SKIP_CLASS_TOKENS = {
        "mw-editsection",
        "noprint",
        "metadata",
        "plainlinks",
        "sisterproject",
        "ws-noexport",
        "reference",
        "references",
        "mw-references-wrap",
        "printfooter",
        "ambox",
        "header",
        "headertemplate",
        "licenseContainer",
    }
    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "center",
        "dd",
        "details",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "hr",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.buf: list[str] = []
        self.skip_stack: list[str] = []
        self.table_stack: list[dict] = []

    def attrs_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {k: v or "" for k, v in attrs}

    def should_skip(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        if tag in self.SKIP_TAGS:
            return True
        values = self.attrs_dict(attrs)
        if values.get("id") in self.SKIP_IDS:
            return True
        classes = set(values.get("class", "").split())
        return bool(classes & self.SKIP_CLASS_TOKENS)

    def append_text(self, text: str) -> None:
        if not text or self.skip_stack:
            return
        text = text.replace("\xa0", " ").replace("\u200b", "")
        if self.table_stack and self.table_stack[-1].get("cell") is not None:
            self.table_stack[-1]["cell"].append(text)
        else:
            self.buf.append(text)

    def flush_line(self) -> None:
        if self.skip_stack or self.table_stack:
            return
        line = clean_inline("".join(self.buf))
        self.buf = []
        if line:
            self.lines.append(line)

    def blank_line(self) -> None:
        self.flush_line()
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip_stack:
            if self.should_skip(tag, attrs):
                self.skip_stack.append(tag)
            return
        if self.should_skip(tag, attrs):
            self.flush_line()
            self.skip_stack.append(tag)
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.blank_line()
            level = min(int(tag[1]) + 1, 6)
            self.buf.append("#" * level + " ")
        elif tag == "br":
            if self.table_stack and self.table_stack[-1].get("cell") is not None:
                self.table_stack[-1]["cell"].append(" ")
            else:
                self.flush_line()
        elif tag == "li":
            self.flush_line()
            self.buf.append("- ")
        elif tag == "table":
            self.flush_line()
            self.table_stack.append({"rows": [], "row": None, "cell": None})
        elif tag == "tr" and self.table_stack:
            self.table_stack[-1]["row"] = []
        elif tag in {"td", "th"} and self.table_stack:
            self.table_stack[-1]["cell"] = []
        elif tag in self.BLOCK_TAGS:
            self.flush_line()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_stack:
            if tag == self.skip_stack[-1]:
                self.skip_stack.pop()
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "li"}:
            self.flush_line()
        elif tag in self.BLOCK_TAGS:
            self.blank_line()
        elif tag in {"td", "th"} and self.table_stack:
            table = self.table_stack[-1]
            cell = clean_inline("".join(table.get("cell") or []))
            row = table.get("row")
            if row is not None:
                row.append(cell)
            table["cell"] = None
        elif tag == "tr" and self.table_stack:
            table = self.table_stack[-1]
            row = table.get("row")
            if row is not None and any(cell for cell in row):
                table["rows"].append(row)
            table["row"] = None
        elif tag == "table" and self.table_stack:
            table = self.table_stack.pop()
            if not self.table_stack:
                self.render_table(table["rows"])
            else:
                rendered = table_rows_to_text(table["rows"])
                self.table_stack[-1].setdefault("cell", []).append(rendered)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "br":
            self.handle_starttag(tag, attrs)
        elif tag == "ref":
            return

    def handle_data(self, data: str) -> None:
        self.append_text(data)

    def render_table(self, rows: list[list[str]]) -> None:
        text = table_rows_to_text(rows)
        if text:
            self.blank_line()
            self.lines.extend(text.splitlines())
            self.lines.append("")

    def markdown(self) -> str:
        self.flush_line()
        return normalize_markdown("\n".join(self.lines))


def clean_inline(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = text.replace(" ,", ",").replace(" .", ".")
    return text.strip()


def table_rows_to_text(rows: list[list[str]]) -> str:
    out: list[str] = []
    for row in rows:
        cells = [clean_inline(cell).replace("|", "｜") for cell in row]
        if not any(cells):
            continue
        if len(cells) == 1:
            out.append(cells[0])
        else:
            out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.rstrip() for line in text.splitlines()]

    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if re.match(r"^(Category|分类|分類):", stripped, flags=re.I):
            continue
        if stripped in {"目錄", "目录", "返回", "上一卷", "下一卷"}:
            continue
        cleaned.append(stripped)

    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def remove_collation_section(markdown: str) -> str:
    lines = markdown.splitlines()
    kept: list[str] = []
    for line in lines:
        if re.match(r"^#{1,6}\s*校勘[記记]\s*$", line.strip()):
            break
        kept.append(line)
    return normalize_markdown("\n".join(kept))


def html_to_markdown(rendered_html: str) -> str:
    parser = WikisourceHtmlExtractor()
    parser.feed(rendered_html)
    parser.close()
    return remove_collation_section(parser.markdown())


def fetch_rendered_page(title: str) -> tuple[str, str]:
    data = api_query(
        {
            "action": "parse",
            "format": "json",
            "formatversion": 2,
            "page": title,
            "prop": "text",
            "redirects": 1,
            "disablelimitreport": 1,
            "disableeditsection": 1,
        }
    )
    if "error" in data:
        raise RuntimeError(f"{title}: {data['error'].get('info', data['error'])}")
    parsed = data.get("parse") or {}
    return parsed.get("title", title), parsed.get("text", "")


def discover_volume_pages(wiki_title: str, total: int) -> dict[int, list[str]]:
    params: dict[str, object] = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "list": "allpages",
        "apprefix": f"{wiki_title}/卷",
        "aplimit": "max",
    }
    pages: dict[int, list[str]] = {vol: [] for vol in range(1, total + 1)}

    while True:
        data = api_query(params)
        for page in data.get("query", {}).get("allpages", []):
            title = page["title"]
            vol = volume_from_title(title)
            if vol is not None and 1 <= vol <= total:
                pages[vol].append(title)
        if "continue" not in data:
            break
        params.update(data["continue"])

    return {vol: sorted(titles, key=part_sort_key) for vol, titles in pages.items()}


def generate_volume(hist: dict, vol: int, titles: list[str], force: bool, delay: float) -> tuple[bool, str]:
    slug = hist["slug"]
    total = hist["volumes"]
    out_file = OUT_BASE / slug / volume_group_dir(vol, total) / f"{slug}-{vol:03d}.md"
    if out_file.exists() and not force:
        return True, "exists"
    if not titles:
        return False, "missing source page"

    parts: list[str] = []
    seen_titles: set[str] = set()
    seen_hashes: set[str] = set()

    for title in titles:
        resolved, rendered_html = fetch_rendered_page(title)
        if resolved in seen_titles:
            continue
        body = html_to_markdown(rendered_html)
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if body and body_hash not in seen_hashes:
            parts.append(body)
            seen_hashes.add(body_hash)
        seen_titles.add(resolved)
        if delay:
            time.sleep(delay)

    body = "\n\n".join(part for part in parts if part).strip()
    if not body:
        return False, "empty body after cleaning"

    title = f"{hist['title']} 卷{vol}"
    summary = f"{hist['title']}卷{vol}。{hist['summary']}"
    tags = [hist["title"], hist["dynasty"], hist["author"]]
    write_frontmatter(out_file, title, summary, vol, tags, body=body)
    return True, f"{len(body)} chars from {len(parts)} page(s)"


def generate_history(slug: str, force: bool, delay: float) -> tuple[int, int]:
    hist = next((item for item in HISTORIES if item["slug"] == slug), None)
    if hist is None:
        raise SystemExit(f"Unknown history slug: {slug}")

    wiki_title = WIKI_TITLES[slug]
    pages = discover_volume_pages(wiki_title, hist["volumes"])
    ok = 0
    failed = 0
    print(f"\n== {hist['title']} / {wiki_title} ({hist['volumes']}卷) ==")

    for vol in range(1, hist["volumes"] + 1):
        titles = pages.get(vol, [])
        try:
            success, message = generate_volume(hist, vol, titles, force=force, delay=delay)
        except Exception as exc:
            success, message = False, str(exc)
        if success:
            ok += 1
            print(f"  [{vol:03d}] OK {message}")
        else:
            failed += 1
            print(f"  [{vol:03d}] FAIL {message}")

    return ok, failed


def validate() -> int:
    problems: list[str] = []
    expected_total = sum(hist["volumes"] for hist in HISTORIES)
    actual_files = [p for p in OUT_BASE.glob("*/*/*.md") if p.name != "_index.md"]
    if len(actual_files) != expected_total:
        problems.append(f"正文文件数量 {len(actual_files)} != 期望 {expected_total}")

    forbidden = [
        (re.compile(r"#REDIRECT", re.I), "#REDIRECT"),
        (re.compile(r"<references?\b", re.I), "<references>"),
        (re.compile(r"\{\{|\}\}"), "raw template braces"),
        (re.compile(r"mw-parser-output|headerContainer"), "parser/header HTML"),
        (re.compile(r"表格略"), "表格略"),
        (re.compile(r"^#{1,6}\s*校勘[記记]\s*$", re.M), "校勘記 heading"),
        (re.compile(r"^(Category|分类|分類):", re.I | re.M), "Category line"),
    ]

    for hist in HISTORIES:
        slug = hist["slug"]
        files = sorted((OUT_BASE / slug).glob("*/*.md"))
        nums: list[int] = []
        for path in files:
            if path.name == "_index.md":
                continue
            m = re.match(rf"{re.escape(slug)}-(\d{{3}})\.md$", path.name)
            if not m:
                problems.append(f"文件名异常: {path.relative_to(ROOT)}")
                continue
            vol = int(m.group(1))
            nums.append(vol)
            text = path.read_text(encoding="utf-8")
            body = re.sub(r"(?s)^---\n.*?\n---\n?", "", text).strip()
            if len(body) < 200:
                problems.append(f"正文过短: {path.relative_to(ROOT)} ({len(body)} chars)")
            for pattern, label in forbidden:
                if pattern.search(body):
                    problems.append(f"残留 {label}: {path.relative_to(ROOT)}")
                    break
        missing = [n for n in range(1, hist["volumes"] + 1) if n not in set(nums)]
        if missing:
            problems.append(f"{hist['title']} 缺卷: {missing}")
        if len(nums) != len(set(nums)):
            problems.append(f"{hist['title']} 卷号重复")

    if problems:
        print("\nVALIDATION FAILED")
        for item in problems[:200]:
            print(f"  - {item}")
        if len(problems) > 200:
            print(f"  ... and {len(problems) - 200} more")
        return 1

    print(f"\nVALIDATION OK: {expected_total} volume files")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", choices=[item["slug"] for item in HISTORIES])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite existing volume files.")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between parse API requests.")
    args = parser.parse_args()

    if args.list:
        for item in HISTORIES:
            print(f"{item['slug']:20s} {item['title']} {item['volumes']}卷")
        return

    if args.validate:
        raise SystemExit(validate())

    ensure_indexes()
    if args.history:
        ok, failed = generate_history(args.history, force=args.force, delay=args.delay)
        print(f"\nDONE: {ok} OK, {failed} failed")
        raise SystemExit(0 if failed == 0 else 1)
    if args.all:
        total_ok = 0
        total_failed = 0
        for item in HISTORIES:
            ok, failed = generate_history(item["slug"], force=args.force, delay=args.delay)
            total_ok += ok
            total_failed += failed
        print(f"\nALL DONE: {total_ok} OK, {total_failed} failed")
        raise SystemExit(0 if total_failed == 0 else 1)

    parser.print_help()


if __name__ == "__main__":
    main()
