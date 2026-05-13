#!/usr/bin/env python3
"""Generate Daoist alchemy texts from stable Wikisource raw pages."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALCHEMY_DIR = ROOT / "content" / "posts" / "taoism" / "alchemy"
BAOPUZI_DIR = ALCHEMY_DIR / "baopuzi-neipian"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
ASSET_BASE_URL = "https://static.ifcalm.org/books"

BAOPUZI_INNER = [
    ("01", "卷一 畅玄", "暢玄", "抱朴子/卷01"),
    ("02", "卷二 论仙", "論仙", "抱朴子/卷02"),
    ("03", "卷三 对俗", "對俗", "抱朴子/卷03"),
    ("04", "卷四 金丹", "金丹", "抱朴子/卷04"),
    ("05", "卷五 至理", "至理", "抱朴子/卷05"),
    ("06", "卷六 微旨", "微旨", "抱朴子/卷06"),
    ("07", "卷七 塞难", "塞難", "抱朴子/卷07"),
    ("08", "卷八 释滞", "釋滯", "抱朴子/卷08"),
    ("09", "卷九 道意", "道意", "抱朴子/卷09"),
    ("10", "卷十 明本", "明本", "抱朴子/卷10"),
    ("11", "卷十一 仙药", "仙藥", "抱朴子/卷11"),
    ("12", "卷十二 辨问", "辨問", "抱朴子/卷12"),
    ("13", "卷十三 极言", "極言", "抱朴子/卷13"),
    ("14", "卷十四 勤求", "勤求", "抱朴子/卷14"),
    ("15", "卷十五 杂应", "雜應", "抱朴子/卷15"),
    ("16", "卷十六 黄白", "黃白", "抱朴子/卷16"),
    ("17", "卷十七 登涉", "登涉", "抱朴子/卷17"),
    ("18", "卷十八 地真", "地真", "抱朴子/卷18"),
    ("19", "卷十九 遐览", "遐覽", "抱朴子/卷19"),
    ("20", "卷二十 袪惑", "袪惑", "抱朴子/卷20"),
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


def onlyinclude_or_all(raw: str) -> str:
    match = re.search(r"<onlyinclude>(.*?)</onlyinclude>", raw, flags=re.S)
    return match.group(1) if match else raw


def clean_wikitext(text: str) -> str:
    text = re.sub(r"\{\{PUA\|([^{}]*)\}\}", r"\1", text)
    text = text.replace("<口父>", "㕮")
    text = text.replace("{藟系}", "虆")
    for template in [
        "Header",
        "header",
        "注本",
        "金丹四百字注",
        "北宋作品",
        "PD-old",
        "東晉作品",
    ]:
        text = strip_balanced_template(text, template)
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"</?poem>", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    return normalize_blank_lines(text)


def convert_headings(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        marks, title = match.group(1), match.group(2).strip()
        level = "#" * (len(marks) + 1)
        return f"{level} {title}"

    return re.sub(r"^(={2,4})\s*(.*?)\s*\1$", repl, text, flags=re.M)


def baopuzi_17_symbols() -> dict[str, str]:
    base = f"{ASSET_BASE_URL}/taoism/baopuzi-neipian/dengshe"

    def image_block(label: str, pages: list[int]) -> str:
        return "\n\n".join(
            f"![{label}（涵芬楼版第 {page} 页）]({base}/0870-{page}.png)"
            for page in pages
        )

    return {
        "（圖片，五張符文）": image_block("入山符", [112, 113, 114]),
        "（圖片，兩張符文）": image_block("入山符", [116, 117]),
        "（圖片，一張符文）": image_block("老君神印符", [119]),
        "（圖片，三張符文）": image_block("入山佩带符", [119, 120]),
    }


def add_baopuzi_17_images(body: str) -> str:
    replacements = baopuzi_17_symbols()
    body = body.replace("（圖片，五張符文）", replacements["（圖片，五張符文）"], 1)
    body = body.replace("（圖片，兩張符文）", replacements["（圖片，兩張符文）"], 1)
    body = body.replace("（圖片，兩張符文）", image_block_last_two(), 1)
    body = body.replace("（圖片，一張符文）", replacements["（圖片，一張符文）"], 1)
    body = body.replace("（圖片，三張符文）", replacements["（圖片，三張符文）"], 1)
    body = body.replace(
        "（圖片，五張符文）",
        "\n\n".join(
            f"![禁山符（涵芬楼版第 {page} 页）]({ASSET_BASE_URL}/taoism/baopuzi-neipian/dengshe/0870-{page}.png)"
            for page in [126, 127, 128]
        ),
        1,
    )
    return body


def image_block_last_two() -> str:
    base = f"{ASSET_BASE_URL}/taoism/baopuzi-neipian/dengshe"
    return "\n\n".join(
        f"![陈安世入山辟虎狼符（涵芬楼版第 {page} 页）]({base}/0870-{page}.png)"
        for page in [118, 119]
    )


def front_matter(
    title: str,
    summary: str,
    weight: int,
    tags: list[str] | None = None,
    show_toc: bool = True,
) -> str:
    tag_values = tags or ["道家", "丹道"]
    tag_text = ", ".join(f'"{tag}"' for tag in tag_values)
    toc = "true" if show_toc else "false"
    return f"""---
title: "{title}"
date: 2026-05-13
weight: {weight}
tags: [{tag_text}]
draft: false
summary: "{summary}"
showToc: {toc}
tocOpen: false
ShowShareButtons: false
---
"""


def write_page(
    path: Path,
    title: str,
    summary: str,
    weight: int,
    body: str,
    tags: list[str] | None = None,
    show_toc: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(title, summary, weight, tags, show_toc) + "\n" + body.strip() + "\n",
        encoding="utf-8",
    )


def source_body(title: str) -> str:
    return convert_headings(clean_wikitext(onlyinclude_or_all(fetch_raw(title))))


def write_short_alchemy_texts() -> None:
    write_page(
        ALCHEMY_DIR / "ruyao-jing.md",
        "入药镜",
        "先天炁，后天气，得之者，常似醉。",
        40,
        source_body("入藥鏡"),
    )
    write_page(
        ALCHEMY_DIR / "jindan-sibaizi.md",
        "金丹四百字",
        "七返九还金液大丹者，七乃火数，九乃金数。",
        41,
        source_body("金丹四百字"),
    )
    write_page(
        ALCHEMY_DIR / "cuixu-pian.md",
        "翠虚篇",
        "真息子王思诚谨焚香稽首再拜序。",
        42,
        source_body("翠虛篇"),
    )


def write_baopuzi_inner() -> None:
    index_body = "《抱朴子内篇》二十卷，按卷分篇收录。"
    write_page(
        BAOPUZI_DIR / "_index.md",
        "抱朴子内篇",
        "葛洪撰，道教神仙、金丹、方术与修道理论要籍。",
        43,
        index_body,
        tags=["道家", "丹道", "抱朴子"],
        show_toc=False,
    )
    for weight, (number, title, source_title, raw_title) in enumerate(BAOPUZI_INNER, 1):
        body = clean_wikitext(fetch_raw(raw_title))
        if raw_title == "抱朴子/卷17":
            body = add_baopuzi_17_images(body)
        write_page(
            BAOPUZI_DIR / f"{number}.md",
            f"抱朴子内篇 {title}",
            f"抱朴子内篇{source_title}。",
            weight,
            body,
            tags=["道家", "丹道", "抱朴子"],
        )


def main() -> None:
    write_short_alchemy_texts()
    write_baopuzi_inner()


if __name__ == "__main__":
    main()
