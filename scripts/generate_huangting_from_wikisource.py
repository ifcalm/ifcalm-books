#!/usr/bin/env python3
"""Generate Huangting Jing Markdown pages from Wikisource raw wikitext."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "content" / "posts" / "taoism" / "huangting-jing"
RAW_URL = "https://zh.wikisource.org/w/index.php?title={title}&action=raw"

INNER_FULL = "太上黃庭內景玉經/全覽"
OUTER = "黃庭外景經"


def fetch_raw(title: str) -> str:
    url = RAW_URL.format(title=urllib.parse.quote(title))
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ifcalm-books text collector; contact: https://books.ifcalm.org/"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def strip_ref(text: str) -> str:
    return re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.S)


def strip_templates(text: str) -> str:
    """Keep the base text from {{參|base|apparatus}} and drop other templates."""
    text = strip_ref(text)
    while "{{參|" in text:
        start = text.index("{{參|")
        depth = 0
        end = None
        for i in range(start, len(text) - 1):
            pair = text[i : i + 2]
            if pair == "{{":
                depth += 1
            elif pair == "}}":
                depth -= 1
                if depth == 0:
                    end = i + 2
                    break
        if end is None:
            break
        body = text[start + 4 : end - 2]
        base = body.split("|", 1)[0]
        text = text[:start] + base + text[end:]
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    return text


def clean_line(text: str) -> str:
    text = strip_templates(text)
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = text.replace("&nbsp;", " ")
    return text.strip()


def parse_inner() -> str:
    overview = fetch_raw(INNER_FULL)
    chapters: list[tuple[str, str]] = []
    for title in re.findall(r"\{\{:太上黃庭內景玉經/([^}]+)\}\}", overview):
        raw = fetch_raw(f"太上黃庭內景玉經/{title}")
        body = clean_line(raw)
        if title.strip() == "黃庭章第四":
            body = re.sub(r"^雷鸣电激神泯泯，", "", body)
        chapters.append((title.strip(), body))

    parts = []
    for title, body in chapters:
        parts.append(f"### {title}\n\n{body}")
    return "\n\n".join(parts)


def parse_outer() -> str:
    raw = fetch_raw(OUTER)
    lines: list[str] = []
    in_header = False
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if line.startswith("{{header"):
            in_header = True
            continue
        if in_header:
            if line.endswith("}}"):
                in_header = False
            continue
        if not line or line.startswith("{{PD-old") or line.startswith("[[Category:"):
            continue
        if line == "== 說明 ==" or line == "{{reflist}}":
            break

        m2 = re.match(r"^==\s*(.*?)\s*==$", line)
        m3 = re.match(r"^===\s*(.*?)\s*===$", line)
        if m3:
            lines.append(f"### {clean_line(m3.group(1))}")
            lines.append("")
        elif m2:
            lines.append(f"## {clean_line(m2.group(1))}")
            lines.append("")
        else:
            cleaned = clean_line(line)
            if cleaned:
                lines.append(cleaned)
                lines.append("")
    return "\n".join(lines).strip()


def front_matter(title: str, summary: str, weight: int, show_toc: bool) -> str:
    toc = "true" if show_toc else "false"
    return f"""---
title: "{title}"
date: 2026-05-11
weight: {weight}
tags: ["道家", "黄庭经"]
draft: false
summary: "{summary}"
showToc: {toc}
tocOpen: false
ShowShareButtons: false
---
"""


def write_page(filename: str, title: str, summary: str, weight: int, body: str) -> None:
    path = OUT_DIR / filename
    path.write_text(front_matter(title, summary, weight, True) + "\n" + body.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = front_matter(
        "黄庭内外景经",
        "道教上清派重要经典，收《黄庭内景经》《黄庭外景经》。",
        30,
        False,
    )
    index_body = """收录《黄庭内景经》《黄庭外景经》二种。

文本以维基文库所录《正统道藏》本为主，参照中国哲学书电子化计划、Kanripo 汉籍リポジトリ等来源校正完整性，正文保留原文用字，清除了网页校勘模板、脚注与分类标记。
"""
    (OUT_DIR / "_index.md").write_text(index + "\n" + index_body, encoding="utf-8")
    write_page(
        "nei-jing.md",
        "黄庭内景经",
        "上清紫霞虚皇前，太上大道玉晨君。",
        1,
        parse_inner(),
    )
    write_page(
        "wai-jing.md",
        "黄庭外景经",
        "上有黄庭下关元，后有幽阙前命门。",
        2,
        parse_outer(),
    )


if __name__ == "__main__":
    main()
