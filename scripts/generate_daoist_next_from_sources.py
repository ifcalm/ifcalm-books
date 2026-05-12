#!/usr/bin/env python3
"""Generate the next batch of compact Daoist canon texts."""

from __future__ import annotations

import html.parser
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


class VisibleTextParser(html.parser.HTMLParser):
    block_tags = {"p", "div", "h1", "h2", "h3", "h4", "li", "br"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "script", "noscript"}:
            self.skip_depth += 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


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


def clean_wikitext(text: str) -> str:
    text = strip_balanced_template(text, "Header")
    text = strip_balanced_template(text, "header")
    text = strip_balanced_template(text, "注本")
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"<poem>", "", text)
    text = re.sub(r"</poem>", "", text)
    text = re.sub(r"<div\b[^>]*>.*?</div>", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[File:[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    return normalize_blank_lines(text)


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
date: 2026-05-12
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


def onlyinclude_or_all(raw: str) -> str:
    match = re.search(r"<onlyinclude>(.*?)</onlyinclude>", raw, flags=re.S)
    return match.group(1) if match else raw


def xisheng_body() -> str:
    raw = fetch_raw("西昇經")
    body = convert_headings(clean_wikitext(raw))
    return body


def neiguan_body() -> str:
    raw = fetch_raw("太上老君內觀經")
    return clean_wikitext(raw)


def neiriyong_body() -> str:
    raw = fetch_raw("太上老君內日用妙經")
    return clean_wikitext(onlyinclude_or_all(raw))


def wairiyong_body() -> str:
    raw = fetch_raw("太上老君外日用妙經")
    return clean_wikitext(raw)


def beidou_body() -> str:
    raw = fetch_raw("太上玄靈北斗本命延生真經")
    body = clean_wikitext(raw)
    body = re.sub(r"^太上玄靈北斗本命延生真經\s*\n+", "", body)
    return body


def xiaozai_body() -> str:
    html = request("https://www.donglishuzhai.net/chapter/7142.html").decode("utf-8", "ignore")
    parser = VisibleTextParser()
    parser.feed(html)
    lines = [line.strip() for line in parser.text().splitlines() if line.strip()]
    start = lines.index("爾時，元始天尊在七寶林中，五明宮內，與無極聖眾俱。放無極光明，照無極世界，觀無極眾生，受無極苦惱；宛轉世間，輪迴生死，漂浪愛河，流吹欲海，沉滯聲色，迷惑有無；無空有空，無色有色，無無有無，有有無有，終始暗昧，不能自明，畢竟迷惑。")
    end = lines.index("太上昇玄消灾護命妙經竟")
    body_lines = lines[start : end + 1]
    return normalize_blank_lines("\n\n".join(body_lines))


def main() -> None:
    write_page(
        "xi-sheng-jing.md",
        "西升经",
        "老君西升，开道竺乾。",
        39,
        xisheng_body(),
    )
    write_page(
        "neiguan-jing.md",
        "太上老君内观经",
        "天地媾精，阴阳布化，万物以生。",
        40,
        neiguan_body(),
    )
    write_page(
        "nei-riyong-jing.md",
        "太上老君内日用妙经",
        "夫日用者，饮食则定，禁口独坐。",
        41,
        neiriyong_body(),
    )
    write_page(
        "wai-riyong-jing.md",
        "太上老君外日用妙经",
        "敬天地，重日月。",
        42,
        wairiyong_body(),
    )
    write_page(
        "xiaozai-huming-jing.md",
        "太上升玄消灾护命妙经",
        "元始天尊在七宝林中，五明宫内。",
        43,
        xiaozai_body(),
    )
    write_page(
        "beidou-jing.md",
        "太上玄灵北斗本命延生真经",
        "人身难得，中土难生。",
        44,
        beidou_body(),
    )


if __name__ == "__main__":
    main()
