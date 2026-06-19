#!/usr/bin/env python3
"""Generate the first-priority Jingbu additions from CText pages.

The generated set is:

- 《孝经》, one page with 18 chapter headings
- 《尔雅》, one page with 19 chapter headings
- 《周礼》, six files
- 《仪礼》, seventeen files
- 《礼记》, forty-nine files

CText HTML pages provide the primary text. Wikisource is used as a secondary
catalog witness for page existence and chapter counts.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext


ROOT = Path(__file__).resolve().parents[1]
CONFUCIUS_DIR = ROOT / "content" / "posts" / "confucius"
CONTENT_DATE = "2026-06-19"
CONTENT_DRAFT = "true"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CTEXT_BASE = "https://ctext.org"
WIKISOURCE_API = "https://zh.wikisource.org/w/api.php"
FETCH_DELAY = 0.05


@dataclass(frozen=True)
class TextSpec:
    id: str
    slug: str
    title: str
    traditional_title: str
    ctext_root: str
    summary: str
    index_body: str
    weight: int
    mode: str
    expected_chapters: int
    expected_files: int
    expected_headings: int
    wikisource_page: str | None = None
    wikisource_prefix: str | None = None
    wikisource_expected_pages: int | None = None
    body_source: str = "ctext"


@dataclass(frozen=True)
class Chapter:
    index: int
    path: str
    title: str
    paragraphs: tuple[str, ...]

    @property
    def path_slug(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def body(self) -> str:
        return "\n\n".join(self.paragraphs)


SPECS: dict[str, TextSpec] = {
    "xiao-jing": TextSpec(
        id="xiao-jing",
        slug="xiao-jing",
        title="孝经",
        traditional_title="孝經",
        ctext_root="xiao-jing",
        summary="孝经，儒家十三经之一，以孝道为核心。",
        index_body="《孝经》按传世十八章收录正文。",
        weight=45,
        mode="single",
        expected_chapters=18,
        expected_files=1,
        expected_headings=18,
        wikisource_page="今文孝經",
    ),
    "er-ya": TextSpec(
        id="er-ya",
        slug="er-ya",
        title="尔雅",
        traditional_title="爾雅",
        ctext_root="er-ya",
        summary="尔雅，中国早期训诂辞书，儒家十三经之一。",
        index_body="《尔雅》按十九篇收录正文。",
        weight=55,
        mode="single",
        expected_chapters=19,
        expected_files=1,
        expected_headings=19,
        wikisource_page="爾雅",
    ),
    "zhou-li": TextSpec(
        id="zhou-li",
        slug="zhou-li",
        title="周礼",
        traditional_title="周禮",
        ctext_root="rites-of-zhou",
        summary="周礼，记载古代官制与政教制度的礼学典籍。",
        index_body="《周礼》按六官篇目收录正文。",
        weight=12,
        mode="files",
        expected_chapters=6,
        expected_files=6,
        expected_headings=0,
        wikisource_prefix="周禮/",
        wikisource_expected_pages=6,
    ),
    "yi-li": TextSpec(
        id="yi-li",
        slug="yi-li",
        title="仪礼",
        traditional_title="儀禮",
        ctext_root="yili",
        summary="仪礼，记载冠、婚、丧、祭、朝聘等礼仪制度。",
        index_body="《仪礼》按传世十七篇收录正文。",
        weight=13,
        mode="files",
        expected_chapters=17,
        expected_files=17,
        expected_headings=0,
        wikisource_prefix="儀禮/",
        wikisource_expected_pages=17,
    ),
    "li-ji": TextSpec(
        id="li-ji",
        slug="li-ji",
        title="礼记",
        traditional_title="禮記",
        ctext_root="liji",
        summary="礼记，儒家礼学文献汇编，传世四十九篇。",
        index_body="《礼记》按传世四十九篇收录正文。",
        weight=14,
        mode="files",
        expected_chapters=49,
        expected_files=49,
        expected_headings=0,
        wikisource_prefix="禮記/",
        wikisource_expected_pages=53,
        body_source="wikisource",
    ),
}

WIKISOURCE_TITLE_ALIASES = {
    ("yi-li", "有司徹"): "有司",
}

WIKISOURCE_TEXT_REPLACEMENTS = {
    "\ue4aa": "噍",
}

CATALOG_OVERRIDES = {
    "li-ji": [
        ("liji/qu-li-i", "曲禮上"),
        ("liji/qu-li-ii", "曲禮下"),
        ("liji/tan-gong-i", "檀弓上"),
        ("liji/tan-gong-ii", "檀弓下"),
        ("liji/wang-zhi", "王制"),
        ("liji/yue-ling", "月令"),
        ("liji/zengzi-wen", "曾子問"),
        ("liji/wen-wang-shi-zi", "文王世子"),
        ("liji/li-yun", "禮運"),
        ("liji/li-qi", "禮器"),
        ("liji/jiao-te-sheng", "郊特牲"),
        ("liji/nei-ze", "內則"),
        ("liji/yu-zao", "玉藻"),
        ("liji/ming-tang-wei", "明堂位"),
        ("liji/sang-fu-xiao-ji", "喪服小記"),
        ("liji/da-zhuan", "大傳"),
        ("liji/shao-yi", "少儀"),
        ("liji/xue-ji", "學記"),
        ("liji/yue-ji", "樂記"),
        ("liji/za-ji-i", "雜記上"),
        ("liji/za-ji-ii", "雜記下"),
        ("liji/sang-da-ji", "喪大記"),
        ("liji/ji-fa", "祭法"),
        ("liji/ji-yi", "祭義"),
        ("liji/ji-tong", "祭統"),
        ("liji/jing-jie", "經解"),
        ("liji/ai-gong-wen", "哀公問"),
        ("liji/zhongni-yan-ju", "仲尼燕居"),
        ("liji/kongzi-xian-ju", "孔子閒居"),
        ("liji/fang-ji", "坊記"),
        ("liji/zhong-yong", "中庸"),
        ("liji/biao-ji", "表記"),
        ("liji/zi-yi", "緇衣"),
        ("liji/ben-sang", "奔喪"),
        ("liji/wen-sang", "問喪"),
        ("liji/fu-wen", "服問"),
        ("liji/jian-zhuan", "間傳"),
        ("liji/san-nian-wen", "三年問"),
        ("liji/shen-yi", "深衣"),
        ("liji/tou-hu", "投壺"),
        ("liji/ru-xing", "儒行"),
        ("liji/da-xue", "大學"),
        ("liji/guan-yi", "冠義"),
        ("liji/hun-yi", "昏義"),
        ("liji/xiang-yin-jiu-yi", "鄉飲酒義"),
        ("liji/she-yi", "射義"),
        ("liji/yan-yi", "燕義"),
        ("liji/pin-yi", "聘義"),
        ("liji/sang-fu-si-zhi", "喪服四制"),
    ],
}


class CTextProtectedError(RuntimeError):
    pass


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> dict:
    return json.loads(fetch_text(url))


def ctext_url(path: str) -> str:
    return f"{CTEXT_BASE}/{path}/zh"


def dump_yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(title: str, summary: str, weight: int, tag: str) -> str:
    return f"""---
title: {dump_yaml_string(title)}
date: {CONTENT_DATE}
weight: {weight}
tags: {json.dumps([tag], ensure_ascii=False)}
draft: {CONTENT_DRAFT}
summary: {dump_yaml_string(summary)}
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def write_index(spec: TextSpec) -> None:
    out_dir = CONFUCIUS_DIR / spec.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_index.md").write_text(
        front_matter(spec.title, spec.summary, spec.weight, spec.title)
        + spec.index_body
        + "\n",
        encoding="utf-8",
    )


def write_page(
    out_file: Path,
    title: str,
    summary: str,
    weight: int,
    tag: str,
    body: str,
) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        front_matter(title, summary, weight, tag) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def parse_ctext_catalog(spec: TextSpec) -> list[tuple[str, str]]:
    if spec.id in CATALOG_OVERRIDES:
        entries = CATALOG_OVERRIDES[spec.id]
        if len(entries) != spec.expected_chapters:
            raise ValueError(
                f"{spec.title}: expected {spec.expected_chapters} override chapters, "
                f"found {len(entries)}"
            )
        return entries

    page_html = fetch_text(ctext_url(spec.ctext_root))
    prefix = f"{spec.ctext_root}/"
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'<a class="menuitem" id="m\d+" href="([^"]+)/zh" >([^<]+)</a>'
    )

    for path, raw_title in pattern.findall(page_html):
        if not path.startswith(prefix) or path in seen:
            continue
        title = html.unescape(raw_title).strip()
        seen.add(path)
        entries.append((path, title))

    if len(entries) != spec.expected_chapters:
        raise ValueError(
            f"{spec.title}: expected {spec.expected_chapters} CText chapters, "
            f"found {len(entries)}"
        )
    return entries


def parse_ctext_chapter(path: str) -> tuple[str, ...]:
    page_html = fetch_text(ctext_url(path))
    if "Please confirm that you are human" in page_html or "敬請輸入認證圖案" in page_html:
        raise CTextProtectedError(f"CText human verification required for {path}")

    cells = re.findall(r'<td class="ctext">\s*(.*?)</td>', page_html, flags=re.S)
    paragraphs: list[str] = []

    for cell in cells:
        text = re.sub(r"<br\s*/?>", "\n", cell)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text).replace("\u3000", "").strip()
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        if text:
            paragraphs.append(text)

    if not paragraphs:
        raise ValueError(f"Could not parse CText body for {path}")
    return tuple(paragraphs)


def fetch_wikisource_raw(title: str) -> str:
    query = urllib.parse.urlencode({"title": title, "action": "raw"})
    return fetch_text(f"https://zh.wikisource.org/w/index.php?{query}")


def clean_wikisource_body(raw: str) -> tuple[str, ...]:
    text = clean_wikitext(raw)
    for old, new in WIKISOURCE_TEXT_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = text.replace("數噍 毋", "數噍毋")
    text = re.sub(r"</?onlyinclude\b[^>]*>", "", text)
    text = re.sub(r"</?poem\b[^>]*>", "", text)
    text = re.sub(r"</?[a-zA-Z][^>\n]*>", "", text)
    text = re.sub(r"^Category:.*$", "", text, flags=re.M)
    text = re.sub(r"^\|[A-Za-z_-]+=[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"\{\{[^}]+\}\}", "", text)
    text = text.replace("{{", "").replace("}}", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    paragraphs = tuple(
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    )
    if not paragraphs:
        raise ValueError("Empty Wikisource body")
    return paragraphs


def wikisource_title_for_chapter(spec: TextSpec, chapter_title: str) -> str:
    if not spec.wikisource_prefix:
        raise ValueError(f"{spec.title}: no Wikisource prefix configured")
    title = WIKISOURCE_TITLE_ALIASES.get((spec.id, chapter_title), chapter_title)
    return f"{spec.wikisource_prefix}{title}"


def parse_wikisource_chapter(spec: TextSpec, chapter_title: str) -> tuple[str, ...]:
    return clean_wikisource_body(fetch_wikisource_raw(wikisource_title_for_chapter(spec, chapter_title)))


def fetch_collection(spec: TextSpec) -> list[Chapter]:
    chapters: list[Chapter] = []
    for index, (path, title) in enumerate(parse_ctext_catalog(spec), start=1):
        if spec.body_source == "wikisource":
            paragraphs = parse_wikisource_chapter(spec, title)
        else:
            try:
                paragraphs = parse_ctext_chapter(path)
            except CTextProtectedError:
                if not spec.wikisource_prefix:
                    raise
                paragraphs = parse_wikisource_chapter(spec, title)

        chapters.append(
            Chapter(
                index=index,
                path=path,
                title=title,
                paragraphs=paragraphs,
            )
        )
        time.sleep(FETCH_DELAY)
    return chapters


def render_single_body(chapters: list[Chapter]) -> str:
    blocks = []
    for chapter in chapters:
        blocks.append(f"### {chapter.title}\n\n{chapter.body}")
    return "\n\n".join(blocks)


def clean_output_dir(spec: TextSpec, clean: bool) -> None:
    out_dir = CONFUCIUS_DIR / spec.slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)


def generate_spec(spec: TextSpec, clean: bool = False) -> int:
    clean_output_dir(spec, clean)
    chapters = fetch_collection(spec)
    write_index(spec)
    out_dir = CONFUCIUS_DIR / spec.slug

    if spec.mode == "single":
        out_file = out_dir / f"{spec.slug}.md"
        write_page(
            out_file,
            spec.title,
            spec.summary,
            1,
            spec.title,
            render_single_body(chapters),
        )
        return 1

    for chapter in chapters:
        out_file = out_dir / f"{spec.slug}-{chapter.path_slug}.md"
        write_page(
            out_file,
            f"{spec.title}-{chapter.title}",
            f"{spec.title}：{chapter.title}",
            chapter.index,
            spec.title,
            chapter.body,
        )
    return len(chapters)


def read_body(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Missing front matter: {path}")
    return parts[2].strip()


def front_matter_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.S)
    if not match:
        raise ValueError(f"Missing front matter: {path}")
    return match.group(1)


def validate_front_matter(path: Path, spec: TextSpec) -> None:
    front = front_matter_text(path)
    forbidden = ("source:", "source_url:", "source_license:", "categories:")
    for key in forbidden:
        if re.search(rf"^{re.escape(key)}", front, flags=re.M):
            raise ValueError(f"{path}: forbidden front matter key {key}")
    if f'tags: ["{spec.title}"]' not in front:
        raise ValueError(f"{path}: expected one tag {spec.title}")
    if "draft: true" not in front:
        raise ValueError(f"{path}: expected draft: true")
    if "showToc: false" not in front:
        raise ValueError(f"{path}: expected showToc: false")


def validate_text_body(path: Path) -> None:
    body = read_body(path)
    if not body:
        raise ValueError(f"{path}: empty body")
    forbidden_patterns = [
        r"\{\{",
        r"\}\}",
        r"\[\[",
        r"\]\]",
        r"<[^>]+>",
        r"Category:",
        r"顯示相似段落",
        r"打開字典",
        r"dictionary\.pl",
        r"text\.pl",
        r"href=",
        r"ERR_",
        "\ufffd",
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, body):
            raise ValueError(f"{path}: residual source artifact {pattern!r}")
    if re.search(r"[\ue000-\uf8ff]", body):
        raise ValueError(f"{path}: private-use character found")


def local_markdown_files(spec: TextSpec) -> list[Path]:
    out_dir = CONFUCIUS_DIR / spec.slug
    return sorted(path for path in out_dir.glob("*.md") if path.name != "_index.md")


def check_local_spec(spec: TextSpec) -> None:
    out_dir = CONFUCIUS_DIR / spec.slug
    index_file = out_dir / "_index.md"
    if not index_file.exists():
        raise ValueError(f"{spec.title}: missing _index.md")
    validate_front_matter(index_file, spec)
    validate_text_body(index_file)

    files = local_markdown_files(spec)
    if len(files) != spec.expected_files:
        raise ValueError(
            f"{spec.title}: expected {spec.expected_files} files, found {len(files)}"
        )

    weights: list[int] = []
    for path in files:
        validate_front_matter(path, spec)
        validate_text_body(path)
        front = front_matter_text(path)
        match = re.search(r"^weight:\s*(\d+)\s*$", front, flags=re.M)
        if not match:
            raise ValueError(f"{path}: missing numeric weight")
        weights.append(int(match.group(1)))

    expected_weights = list(range(1, spec.expected_files + 1))
    if sorted(weights) != expected_weights:
        raise ValueError(f"{spec.title}: expected weights {expected_weights}, got {weights}")

    if spec.expected_headings:
        body = read_body(files[0])
        headings = re.findall(r"^###\s+", body, flags=re.M)
        if len(headings) != spec.expected_headings:
            raise ValueError(
                f"{spec.title}: expected {spec.expected_headings} headings, "
                f"found {len(headings)}"
            )


def wikisource_query(params: dict[str, str | int]) -> dict:
    query = urllib.parse.urlencode(params)
    return fetch_json(f"{WIKISOURCE_API}?{query}")


def wikisource_allpages(prefix: str) -> list[str]:
    params: dict[str, str | int] = {
        "action": "query",
        "format": "json",
        "list": "allpages",
        "apprefix": prefix,
        "aplimit": 500,
    }
    pages: list[str] = []
    while True:
        data = wikisource_query(params)
        pages.extend(
            page["title"] for page in data.get("query", {}).get("allpages", [])
        )
        if "continue" not in data:
            break
        params.update(data["continue"])
    return sorted(pages)


def check_wikisource_witness(spec: TextSpec, ctext_titles: list[str]) -> None:
    if spec.wikisource_page:
        data = wikisource_query(
            {
                "action": "query",
                "format": "json",
                "titles": spec.wikisource_page,
            }
        )
        page = next(iter(data.get("query", {}).get("pages", {}).values()))
        if page.get("missing") is not None:
            raise ValueError(f"{spec.title}: missing Wikisource page")
        return

    if not spec.wikisource_prefix:
        return

    pages = wikisource_allpages(spec.wikisource_prefix)
    if spec.wikisource_expected_pages and len(pages) != spec.wikisource_expected_pages:
        raise ValueError(
            f"{spec.title}: expected {spec.wikisource_expected_pages} Wikisource "
            f"pages, found {len(pages)}"
        )

    page_titles = [page.split("/", 1)[1] for page in pages]
    expected_titles = [
        WIKISOURCE_TITLE_ALIASES.get((spec.id, title), title)
        for title in ctext_titles
    ]
    missing = [title for title in expected_titles if title not in page_titles]
    if missing:
        raise ValueError(f"{spec.title}: titles missing in Wikisource: {missing}")


def check_source_spec(spec: TextSpec) -> None:
    chapters = fetch_collection(spec)
    ctext_titles = [chapter.title for chapter in chapters]
    check_wikisource_witness(spec, ctext_titles)

    if spec.mode == "single":
        out_file = CONFUCIUS_DIR / spec.slug / f"{spec.slug}.md"
        if read_body(out_file) != render_single_body(chapters):
            raise ValueError(f"{spec.title}: local body differs from CText parse")
        return

    for chapter in chapters:
        out_file = CONFUCIUS_DIR / spec.slug / f"{spec.slug}-{chapter.path_slug}.md"
        if read_body(out_file) != chapter.body:
            raise ValueError(f"{spec.title}: local body differs for {chapter.title}")


def selected_specs(text_id: str | None, all_texts: bool) -> list[TextSpec]:
    if all_texts:
        return list(SPECS.values())
    if text_id:
        return [SPECS[text_id]]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", choices=sorted(SPECS), help="Generate or check one text")
    parser.add_argument("--all", action="store_true", help="Generate or check all five texts")
    parser.add_argument("--clean", action="store_true", help="Remove generated target directories first")
    parser.add_argument("--check", action="store_true", help="Check local generated Markdown")
    parser.add_argument(
        "--source-check",
        action="store_true",
        help="Compare generated Markdown with CText and Wikisource witnesses",
    )
    args = parser.parse_args()

    specs = selected_specs(args.text, args.all)
    if not specs:
        parser.print_help()
        return 0

    if args.check:
        for spec in specs:
            check_local_spec(spec)
            print(f"Checked local {spec.title}")
        return 0

    if args.source_check:
        for spec in specs:
            check_local_spec(spec)
            check_source_spec(spec)
            print(f"Checked source witnesses for {spec.title}")
        return 0

    for spec in specs:
        count = generate_spec(spec, clean=args.clean)
        print(f"Generated {spec.title}: {count} content file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
