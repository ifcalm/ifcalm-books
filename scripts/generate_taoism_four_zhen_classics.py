#!/usr/bin/env python3
"""Generate selected 四子真经 texts for the Taoism classics section."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "content" / "posts" / "taoism" / "classics"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"

WENZI_PAGES = [
    ("卷一 道原", "文子/卷一"),
    ("卷二 精誠", "文子/卷二"),
    ("卷三 九守", "文子/卷三"),
    ("卷四 符言", "文子/卷四"),
    ("卷五 道德", "文子/卷五"),
    ("卷六 上德", "文子/卷六"),
    ("卷七 微明", "文子/卷七"),
    ("卷八 自然", "文子/卷八"),
    ("卷九 下德", "文子/卷九"),
    ("卷十 上仁", "文子/卷十"),
    ("卷十一 上義", "文子/卷十一"),
    ("卷十二 上禮", "文子/卷十二"),
]

KANGCANGZI_PAGES = [
    ("全道第一", "亢倉子/全道第一"),
    ("用道第二", "亢倉子/用道第二"),
    ("政道篇第三", "亢倉子/政道篇第三"),
    ("君道第四", "亢倉子/君道第四"),
    ("臣道第五", "亢倉子/臣道第五"),
    ("賢道第六", "亢倉子/賢道第六"),
    ("順訓道第七", "亢倉子/順訓道第七"),
    ("農道第八", "亢倉子/農道第八"),
    ("兵道第九", "亢倉子/兵道第九"),
]


def request(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def fetch_raw(title: str) -> str:
    url = "https://zh.wikisource.org/w/index.php?title={}&action=raw".format(
        urllib.parse.quote(title)
    )
    return request(url).decode("utf-8")


def strip_balanced_template(text: str, template_name: str | None = None) -> str:
    pattern = "{{" + (template_name or "")
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


def normalize_blank_lines(text: str) -> str:
    text = text.replace("\u3000", "").replace("\u200b", "")
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def onlyinclude(raw: str) -> str:
    match = re.search(r"<onlyinclude>(.*?)</onlyinclude>", raw, flags=re.S)
    if not match:
        raise ValueError("source page does not contain onlyinclude block")
    return match.group(1)


def clean_wikitext(text: str) -> str:
    text = strip_balanced_template(text, "Novel")
    text = strip_balanced_template(text, "footer")
    text = strip_balanced_template(text, "header")
    text = strip_balanced_template(text, "align")
    text = strip_balanced_template(text, "see also")
    text = strip_balanced_template(text, "*")
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return normalize_blank_lines(text)


def front_matter(title: str, summary: str, weight: int) -> str:
    return f"""---
title: "{title}"
date: 2026-05-12
weight: {weight}
tags: ["道家"]
draft: false
summary: "{summary}"
showToc: true
tocOpen: false
ShowShareButtons: false
---
"""


def write_page(filename: str, title: str, summary: str, weight: int, body: str) -> None:
    path = OUT_DIR / filename
    path.write_text(
        front_matter(title, summary, weight) + "\n" + body.strip() + "\n",
        encoding="utf-8",
    )


def build_chaptered_body(pages: list[tuple[str, str]]) -> str:
    sections: list[str] = []
    for heading, title in pages:
        body = clean_wikitext(onlyinclude(fetch_raw(title)))
        sections.append(f"### {heading}\n\n{body}")
    return "\n\n".join(sections)


def kangcangzi_preface() -> str:
    raw = fetch_raw("亢倉子")
    match = re.search(r"==序==\s*(.*?)\s*==目錄==", raw, flags=re.S)
    if not match:
        raise ValueError("unable to extract 亢倉子序")
    return "### 序\n\n" + clean_wikitext(match.group(1))


def main() -> None:
    write_page(
        "tongxuan-zhenjing.md",
        "通玄真经",
        "有物混成，先天地生。",
        45,
        build_chaptered_body(WENZI_PAGES),
    )
    write_page(
        "dongling-zhenjing.md",
        "洞灵真经",
        "亢仓子居羽山之颜三年。",
        46,
        kangcangzi_preface() + "\n\n" + build_chaptered_body(KANGCANGZI_PAGES),
    )


if __name__ == "__main__":
    main()
