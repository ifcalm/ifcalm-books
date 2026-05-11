#!/usr/bin/env python3
"""Generate selected compact Daoist classics from Wikisource."""

from __future__ import annotations

import html.parser
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "content" / "posts" / "taoism"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"


def request(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def fetch_raw(title: str) -> str:
    url = "https://zh.wikisource.org/w/index.php?title={}&action=raw".format(
        urllib.parse.quote(title)
    )
    return request(url).decode("utf-8")


class TextParser(html.parser.HTMLParser):
    block_tags = {"p", "div", "h1", "h2", "h3", "h4", "li", "br"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script"}:
            self.skip_depth += 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def fetch_rendered_text(title: str) -> str:
    url = (
        "https://zh.wikisource.org/w/api.php?action=parse&prop=text&format=json&page="
        + urllib.parse.quote(title)
    )
    data = json.loads(request(url).decode("utf-8"))
    parser = TextParser()
    parser.feed(data["parse"]["text"]["*"])
    return parser.text()


def strip_balanced_template(text: str, template_name: str | None = None) -> str:
    pattern = "{{" + (template_name if template_name else "")
    while pattern in text:
        start = text.index(pattern)
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
        text = text[:start] + text[end:]
    return text


def clean_wikitext(text: str) -> str:
    text = strip_balanced_template(text, "Header")
    text = strip_balanced_template(text, "header")
    text = strip_balanced_template(text, "Novel")
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"\{\{另\|([^|{}]+)\|[^{}]+\}\}", r"\1", text)
    text = re.sub(r"\{\{\*\|[^{}]*\}\}", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text)
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = text.replace("\u3000", "")
    text = text.replace("\u200b", "")
    text = text.replace("&nbsp;", " ")
    return normalize_blank_lines(text)


def normalize_blank_lines(text: str) -> str:
    text = text.replace("\u200b", "")
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def convert_headings(text: str, base_level: int = 3) -> str:
    def repl(match: re.Match[str]) -> str:
        marks, title = match.group(1), match.group(2).strip()
        level = "#" * (base_level + len(marks) - 2)
        return f"{level} {title}"

    return re.sub(r"^(={2,4})\s*(.*?)\s*\1$", repl, text, flags=re.M)


def front_matter(title: str, summary: str, weight: int, show_toc: bool = True) -> str:
    toc = "true" if show_toc else "false"
    return f"""---
title: "{title}"
date: 2026-05-11
weight: {weight}
tags: ["道家"]
draft: false
summary: "{summary}"
showToc: {toc}
tocOpen: false
ShowShareButtons: false
---
"""


def write_page(filename: str, title: str, summary: str, weight: int, body: str) -> None:
    path = OUT_DIR / filename
    path.write_text(front_matter(title, summary, weight) + "\n" + body.strip() + "\n", encoding="utf-8")


def extract_between(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    finish = text.index(end, begin) + len(end)
    return text[begin:finish]


def rendered_lines(title: str) -> list[str]:
    raw = fetch_rendered_text(title)
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line in {"[", "]", "编辑", "[编辑]"}:
            continue
        if (
            line.startswith(".mw-parser-output")
            or line.startswith("此作品在全世界")
            or line.startswith("Public domain")
        ):
            break
        lines.append(line)
    return lines


def yinfu_body() -> str:
    lines = rendered_lines("黃帝陰符經")
    headings = {
        "神仙抱一演道章上",
        "富國安民演法章中",
        "強兵戰勝演術章下",
    }
    out: list[str] = []
    keep = False
    for line in lines:
        if line in headings:
            keep = True
            out.extend([f"### {line}", ""])
            continue
        if not keep:
            continue
        if line in {"姊妹计划", "百科", "数据项", "参阅"}:
            continue
        out.extend([line, ""])
    return normalize_blank_lines("\n".join(out))


def xinyin_body() -> str:
    text = "\n".join(rendered_lines("高上玉皇心印經"))
    return normalize_blank_lines(extract_between(text, "上藥三品，神與氣精。", "誦之萬遍，妙理自明。"))


def qingjing_body() -> str:
    raw = fetch_raw("太上老君說常清靜經")
    raw = raw.split("==豎排版==", 1)[0]
    body = clean_wikitext(raw)
    return body


def cantongqi_body() -> str:
    parts = []
    for i in range(1, 36):
        raw = fetch_raw(f"周易參同契/{i:02d}章")
        m = re.search(r"<onlyinclude>(.*?)</onlyinclude>", raw, flags=re.S)
        body = m.group(1) if m else raw
        body = convert_headings(clean_wikitext(body))
        parts.append(body)
    return "\n\n".join(parts)


def wuzhen_body() -> str:
    raw = fetch_raw("悟真篇")
    body = clean_wikitext(raw)
    body = re.sub(r"^\s*悟真篇注\s*$", "", body, flags=re.M)
    body = re.sub(r"^\s*}\s*", "", body)
    body = convert_headings(body)
    return normalize_blank_lines(body)


def wenshi_body() -> str:
    titles = [
        "一宇",
        "二柱",
        "三極",
        "四符",
        "五鑒",
        "六匕",
        "七釜",
        "八籌",
        "九藥",
    ]
    parts = []
    for i, title in enumerate(titles, start=1):
        raw = fetch_raw(f"關尹子/{i}")
        body = clean_wikitext(raw)
        parts.append(f"### {title}\n\n{body}")
    return "\n\n".join(parts)


def zuowang_body() -> str:
    raw = fetch_raw("坐忘論")
    body = clean_wikitext(raw)
    body = convert_headings(body, base_level=2)
    return normalize_blank_lines(body)


def duren_body() -> str:
    raw = fetch_raw("靈寶無量度人上品妙經/1")
    m = re.search(r"<onlyinclude>(.*?)</onlyinclude>", raw, flags=re.S)
    body = m.group(1) if m else raw
    body = clean_wikitext(body)
    return "### 元始无量度人上品妙經（度人經本文）\n\n" + body


def main() -> None:
    write_page(
        "huangdi-yinfu-jing.md",
        "黄帝阴符经",
        "觀天之道，執天之行，盡矣。",
        31,
        yinfu_body(),
    )
    write_page(
        "qingjing-jing.md",
        "太上老君说常清静经",
        "人能常清静，天地悉皆归。",
        32,
        qingjing_body(),
    )
    write_page(
        "yuhuang-xinyin-jing.md",
        "玉皇心印经",
        "上药三品，神与气精。",
        33,
        xinyin_body(),
    )
    write_page(
        "zhouyi-cantongqi.md",
        "周易参同契",
        "乾坤者，易之门户，众卦之父母。",
        34,
        cantongqi_body(),
    )
    write_page(
        "wuzhen-pian.md",
        "悟真篇",
        "不求大道出迷途，纵负贤才岂丈夫。",
        35,
        wuzhen_body(),
    )
    write_page(
        "wen-shi-zhen-jing.md",
        "文始真经",
        "非有道不可言，不可言即道。",
        36,
        wenshi_body(),
    )
    write_page(
        "zuowang-lun.md",
        "坐忘论",
        "夫人之所贵者生也，生之所贵者道也。",
        37,
        zuowang_body(),
    )
    write_page(
        "duren-jing.md",
        "度人经",
        "道言：昔於始青天中，碧落空歌，大浮黎土。",
        38,
        duren_body(),
    )


if __name__ == "__main__":
    main()
