#!/usr/bin/env python3
"""Generate the next recommended Daoist canon collection batch."""

from __future__ import annotations

import html.parser
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TAOISM_DIR = ROOT / "content" / "posts" / "taoism"
CLASSICS_DIR = TAOISM_DIR / "classics"
ALCHEMY_DIR = TAOISM_DIR / "alchemy"
RITUAL_DIR = TAOISM_DIR / "ritual"
SHANGQING_DIR = TAOISM_DIR / "shangqing"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"


HUASHU_VOLUMES = [
    ("01.md", "卷一 道化", "化书 卷一 道化", "道之委也，虛化神。", "化書/卷一"),
    ("02.md", "卷二 术化", "化书 卷二 术化", "任機者其發如機。", "化書/卷二"),
    ("03.md", "卷三 德化", "化书 卷三 德化", "飛走之類，皆可以人化。", "化書/卷三"),
    ("04.md", "卷四 仁化", "化书 卷四 仁化", "術以知奸，以刑止刑。", "化書/卷四"),
    ("05.md", "卷五 食化", "化书 卷五 食化", "火之炎也，木之焚也。", "化書/卷五"),
    ("06.md", "卷六 俭化", "化书 卷六 俭化", "禮者，民之所履也。", "化書/卷六"),
]

ZHENGAO_TITLES = [f"真誥/卷{i:03d}" for i in range(1, 21)]

ZHOU_MINGTONG_VOLUMES = [
    ("01.md", "卷之一", "周氏冥通记 卷之一", "玄人周子良，字元龢。", "周氏冥通記/1"),
    ("02.md", "卷之二", "周氏冥通记 卷之二", "周氏冥通記卷之二。", "周氏冥通記/2"),
    ("03.md", "卷之三", "周氏冥通记 卷之三", "周氏冥通記卷之三。", "周氏冥通記/3"),
    ("04.md", "卷之四", "周氏冥通记 卷之四", "周氏冥通記卷之四。", "周氏冥通記/4"),
]


class VisibleTextParser(html.parser.HTMLParser):
    block_tags = {"p", "div", "h1", "h2", "h3", "h4", "li", "br", "td", "tr"}

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


def request(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except Exception as error:  # pragma: no cover - network resilience
            last_error = error
            if attempt == 4:
                break
            time.sleep(2 * (attempt + 1))
    assert last_error is not None
    raise last_error


def fetch_raw(title: str) -> str:
    url = "https://zh.wikisource.org/w/index.php?title={}&action=raw".format(
        urllib.parse.quote(title)
    )
    return request(url).decode("utf-8")


def fetch_rendered_text(title: str) -> str:
    url = (
        "https://zh.wikisource.org/w/api.php?action=parse&prop=text&format=json&page="
        + urllib.parse.quote(title)
    )
    data = json.loads(request(url).decode("utf-8"))
    parser = VisibleTextParser()
    parser.feed(data["parse"]["text"]["*"])
    return parser.text()


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


def preserve_note_templates(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\{\{!\|([^|{}]+)\|[^{}]*\}\}", r"\1", text, flags=re.S)
        text = re.sub(r"\{\{YL\|([^{}]+)\}\}", r"\1", text, flags=re.S)
        text = re.sub(r"\{\{\*\|(.*?)\}\}", r"（\1）", text, flags=re.S)
    return text


def normalize_blank_lines(text: str) -> str:
    text = text.replace("\u3000", "").replace("\u200b", "")
    text = text.replace("﹐", "，").replace("﹕", "：").replace("﹖", "？")
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_wikitext(text: str, preserve_notes: bool = False) -> str:
    for name in ["Header", "header", "Novel", "TextQuality", "wikipedia", "檢索", "注本", "PD-old"]:
        text = strip_balanced_template(text, name)
    if preserve_notes:
        text = preserve_note_templates(text)
        text = re.sub(r"\{\{!\|([^|{}\n]+)\|[^）\n]*(?=）)", r"\1", text)
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"<pages\b[^>]*/>", "", text)
    text = re.sub(r"<poem>", "", text)
    text = re.sub(r"</poem>", "", text)
    text = re.sub(r"<div\b[^>]*>.*?</div>", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[File:[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\}\}(?=。|）|$)", "", text)
    text = text.replace("&nbsp;", " ")
    return normalize_blank_lines(text)


def convert_headings(text: str, base_level: int = 3) -> str:
    def repl(match: re.Match[str]) -> str:
        marks, title = match.group(1), match.group(2).strip()
        level = "#" * (base_level + len(marks) - 2)
        return f"{level} {title}"

    return re.sub(r"^(={2,4})\s*(.*?)\s*\1$", repl, text, flags=re.M)


def extract_onlyinclude(raw: str) -> str:
    match = re.search(r"<onlyinclude>(.*?)</onlyinclude>", raw, flags=re.S)
    return match.group(1) if match else raw


def front_matter(title: str, summary: str, weight: int, show_toc: bool = True) -> str:
    toc = "true" if show_toc else "false"
    return f"""---
title: "{title}"
date: 2026-05-14
weight: {weight}
tags: ["道家"]
draft: false
summary: "{summary}"
showToc: {toc}
tocOpen: false
ShowShareButtons: false
---
"""


def write_page(path: Path, title: str, summary: str, weight: int, body: str, show_toc: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(title, summary, weight, show_toc) + "\n" + body.strip() + "\n",
        encoding="utf-8",
    )


def write_index(path: Path, title: str, summary: str, weight: int, body: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    write_page(path / "_index.md", title, summary, weight, body, show_toc=False)


def huashu_body(source_title: str) -> str:
    raw = extract_onlyinclude(fetch_raw(source_title))
    return convert_headings(clean_wikitext(raw))


def zhengao_preface_body() -> str:
    raw = fetch_raw("真誥")
    raw = raw.split("{{col-begin}}", 1)[0]
    body = clean_wikitext(raw)
    body = convert_headings(body)
    body = re.sub(r"^真誥\s*$", "", body, flags=re.M)
    return normalize_blank_lines(body)


def zhengao_volume_body(source_title: str) -> str:
    rendered = fetch_rendered_text(source_title)
    lines: list[str] = []
    for raw_line in rendered.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if line in {"←", "→", "目錄", "真誥", "姊妹计划: 数据项", "姊妹计划", "数据项", "[编辑]", "编辑"}:
            continue
        if re.fullmatch(r"卷[一二三四五六七八九十百]+", line):
            continue
        if re.fullmatch(r"卷[一二三四五六七八九十百]+ [◄►].*", line):
            continue
        if re.fullmatch(r".*[◄►] 卷[一二三四五六七八九十百]+", line):
            continue
        if line.startswith("作者："):
            continue
        if re.match(r"^真誥卷[一二三四五六七八九十百]+", line):
            continue
        if line.startswith("○"):
            line = "### " + line[1:].strip()
        elif re.fullmatch(r"[\u4e00-\u9fff]{2,8}篇第[一二三四五六七八九十百]+", line):
            line = "### " + line
        lines.append(line)
    return normalize_blank_lines("\n\n".join(lines))


def dengzhen_parts() -> list[tuple[str, str, str]]:
    raw = fetch_raw("登真隱訣")
    body = clean_wikitext(raw, preserve_notes=True)
    body = convert_headings(body)
    body = re.sub(r"^登真隱訣\s*\n+華陽隱居陶弘景撰\s*", "", body)
    markers = list(re.finditer(r"^### 登真隱訣卷([上中下])$", body, flags=re.M))
    if len(markers) != 3:
        raise RuntimeError("unexpected 登真隱訣 volume markers")
    parts: list[tuple[str, str, str]] = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(body)
        text = normalize_blank_lines(body[marker.start() : end])
        label = marker.group(1)
        parts.append((label, f"登真隐诀 卷{label}", text))
    return parts


def zhoushi_body(source_title: str) -> str:
    raw = extract_onlyinclude(fetch_raw(source_title))
    body = clean_wikitext(raw)
    body = re.sub(r"^周氏冥通記卷之[一二三四]\s*", "", body)
    return normalize_blank_lines(convert_headings(body))


def longhu_body() -> str:
    body = clean_wikitext(fetch_raw("古文龍虎經註疏"))
    body = re.sub(r"^古文龍虎經註疏\s*", "", body)
    body = re.sub(r"經名：古文龍虎經註疏。.*?底本出處：《正統道藏》太玄部。\s*", "", body, flags=re.S)
    body = re.sub(r"^\s*(古文龍虎經註疏奏札|註琉序|古文龍虎經註疏卷[中下])\s*$", r"### \1", body, flags=re.M)
    body = "### 古文龙虎经注疏卷上\n\n" + body.lstrip()
    return normalize_blank_lines(body)


def sanguan_body() -> str:
    body = clean_wikitext(fetch_raw("太上三官寶經"))
    body = re.sub(r"^太上三官寶經\s*", "", body)
    heading_names = [
        "凈心神咒",
        "凈口神咒",
        "凈身神咒",
        "安土地咒",
        "凈天地神咒",
        "祝香咒",
        "金光神咒",
        "開經偈",
        "三官頌",
        "上元天官寶誥 志心皈命禮",
        "中元地官寶誥 志心皈命禮",
        "下元水官寶誥 志心皈命禮",
        "火官寶誥 志心皈命禮",
        "太上三元賜福赦罪解厄消災延生保命妙經",
        "太上元始天尊說三官寶號",
        "三官總誥 志心皈命禮",
    ]
    for name in heading_names:
        body = re.sub(rf"^{re.escape(name)}\s*$", f"### {name}", body, flags=re.M)
    return normalize_blank_lines(body)


def yushu_body() -> str:
    raw = extract_onlyinclude(fetch_raw("九天應元雷聲普化天尊玉樞寶經"))
    body = clean_wikitext(raw)
    body = re.sub(r"^九天應元雷聲普化天尊玉樞寶經\s*", "", body)
    body = re.sub(r"經名：九天應元雷聲普化天專玉樞寶經。.*?洞眞部本文類。\s*", "", body, flags=re.S)
    body = re.sub(r"^九天應元雷聲普化天尊玉樞寶經\s*", "", body)
    return normalize_blank_lines(body)


def main() -> None:
    write_index(
        SHANGQING_DIR,
        "上清",
        "上清派经典、真诰与相关传授记录。",
        25,
        "收录上清派经典、真诰、隐诀与相关传授记录。",
    )

    huashu_dir = CLASSICS_DIR / "huashu"
    write_index(huashu_dir, "化书", "五代谭峭撰，道化、术化、德化、仁化、食化、俭化六卷。", 46, "收录《化书》六卷。")
    for weight, (filename, title, full_title, summary, source_title) in enumerate(HUASHU_VOLUMES, 1):
        write_page(huashu_dir / filename, full_title, summary, weight, huashu_body(source_title))

    zhengao_dir = SHANGQING_DIR / "zhengao"
    write_index(zhengao_dir, "真诰", "陶弘景编次，上清经派重要文献，二十卷。", 10, "收录《真诰》二十卷及叙。")
    write_page(zhengao_dir / "00-preface.md", "真诰 叙", "嘉定十六年高似孙叙。", 0, zhengao_preface_body())
    for weight, source_title in enumerate(ZHENGAO_TITLES, 1):
        write_page(
            zhengao_dir / f"{weight:02d}.md",
            f"真诰 卷第{weight}",
            f"真诰卷第{weight}",
            weight,
            zhengao_volume_body(source_title),
        )

    dengzhen_dir = SHANGQING_DIR / "dengzhen-yinjue"
    write_index(dengzhen_dir, "登真隐诀", "陶弘景撰，上清修持诀法，分上、中、下三卷。", 20, "收录《登真隐诀》三卷。")
    for weight, (label, title, body) in enumerate(dengzhen_parts(), 1):
        write_page(dengzhen_dir / f"{weight:02d}.md", title, f"登真隐诀卷{label}", weight, body)

    zhoushi_dir = SHANGQING_DIR / "zhoushi-mingtongji"
    write_index(zhoushi_dir, "周氏冥通记", "陶弘景记周子良幽冥交通事，四卷。", 30, "收录《周氏冥通记》四卷。")
    for weight, (filename, title, full_title, summary, source_title) in enumerate(ZHOU_MINGTONG_VOLUMES, 1):
        write_page(zhoushi_dir / filename, full_title, summary, weight, zhoushi_body(source_title))

    write_page(
        ALCHEMY_DIR / "longhu-jing.md",
        "古文龙虎经注疏",
        "神室者，丹之枢纽，众石之父母。",
        36,
        longhu_body(),
    )
    write_page(
        RITUAL_DIR / "taishang-sanguan-baojing.md",
        "太上三官宝经",
        "太上三元赐福赦罪解厄消灾延生保命妙经。",
        45,
        sanguan_body(),
    )
    write_page(
        RITUAL_DIR / "yushu-baojing.md",
        "玉枢宝经",
        "九天应元雷声普化天尊在玉清天中。",
        46,
        yushu_body(),
    )


if __name__ == "__main__":
    main()
