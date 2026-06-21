#!/usr/bin/env python3
"""Generate the next History-section priority texts.

This batch collects compact, high-value historical classics after 二十四史 and
资治通鉴:

* 竹书纪年: received modern text and Wang Guowei's old-text reconstruction.
* 逸周书: 10 juan.
* 吴越春秋: 10 biographies/outer biographies.
* 越绝书: 15 juan.
* 贞观政要: 10 juan.

Wikisource is used as the repeatable primary source because its MediaWiki API is
stable for bulk retrieval. CText pages were checked as catalog/provenance
witnesses where accessible through search metadata, but CText blocks automated
bulk access from this environment and is therefore not used as the downloader.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext, remove_balanced


ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = ROOT / "content" / "posts" / "history"
WIKISOURCE_API = "https://zh.wikisource.org/w/api.php"
WIKISOURCE_RAW = "https://zh.wikisource.org/w/index.php"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CONTENT_DATE = "2026-06-21"
CONTENT_DRAFT = True
FETCH_DELAY = 0.05


@dataclass(frozen=True)
class SourcePart:
    title: str
    wiki_title: str


@dataclass(frozen=True)
class Unit:
    title: str
    slug: str
    source_parts: tuple[SourcePart, ...]
    expected_markers: tuple[str, ...] = ()
    remove_first_line_patterns: tuple[str, ...] = ()
    trim_before: str | None = None
    trim_after: str | None = None


@dataclass(frozen=True)
class Work:
    key: str
    title: str
    slug: str
    summary: str
    primary_url: str
    proofreading_url: str
    weight: int
    units: tuple[Unit, ...]


ZHU_SHU_PARTS = (
    SourcePart("五帝纪", "今本竹書紀年/五帝紀"),
    SourcePart("夏纪", "今本竹書紀年/夏紀"),
    SourcePart("殷纪", "今本竹書紀年/殷紀"),
    SourcePart("周纪", "今本竹書紀年/周紀"),
    SourcePart("晋纪", "今本竹書紀年/晉紀"),
    SourcePart("魏纪", "今本竹書紀年/魏紀"),
)

YIZHOUSHU_UNITS = tuple(
    Unit(
        f"卷{idx}",
        f"{idx:03d}",
        (SourcePart(f"卷{idx}", f"逸周書/卷{cn}"),),
    )
    for idx, cn in enumerate("一二三四五六七八九十", start=1)
)

WUYUE_UNITS = (
    Unit("吴太伯传", "wu-taibo-zhuan", (SourcePart("吴太伯传", "吳越春秋/吳太伯傳"),)),
    Unit("吴王寿梦传", "wu-wang-shou-meng-zhuan", (SourcePart("吴王寿梦传", "吳越春秋/吳王壽夢傳"),)),
    Unit("王僚使公子光传", "wang-liao-shi-gongzi-guang-zhuan", (SourcePart("王僚使公子光传", "吳越春秋/王僚使公子光傳"),)),
    Unit("阖闾内传", "helu-nei-zhuan", (SourcePart("阖闾内传", "吳越春秋/闔閭內傳"),)),
    Unit("夫差内传", "fuchai-nei-zhuan", (SourcePart("夫差内传", "吳越春秋/夫差內傳"),)),
    Unit("越王无余外传", "yue-wang-wu-yu-wai-zhuan", (SourcePart("越王无余外传", "吳越春秋/越王無余外傳"),)),
    Unit("勾践入臣外传", "goujian-ru-chen-wai-zhuan", (SourcePart("勾践入臣外传", "吳越春秋/勾踐入臣外傳"),)),
    Unit("勾践归国外传", "goujian-gui-guo-wai-zhuan", (SourcePart("勾践归国外传", "吳越春秋/勾踐歸國外傳"),)),
    Unit("勾践阴谋外传", "goujian-yin-mou-wai-zhuan", (SourcePart("勾践阴谋外传", "吳越春秋/勾踐陰謀外傳"),)),
    Unit(
        "勾践伐吴外传",
        "goujian-fa-wu-wai-zhuan",
        (SourcePart("勾践伐吴外传", "吳越春秋/勾踐伐吳外傳"),),
        remove_first_line_patterns=(r"^吳越春秋勾踐伐吳外傳第十$",),
    ),
)

YUEJUE_UNITS = tuple(
    Unit(
        f"卷{idx}",
        f"{idx:03d}",
        (SourcePart(f"卷{idx}", f"越絕書/卷{cn}"),),
    )
    for idx, cn in enumerate(
        ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五"),
        start=1,
    )
)

ZHENGUAN_UNITS = tuple(
    Unit(
        f"卷{idx}",
        f"{idx:03d}",
        (SourcePart(f"卷{idx}", f"貞觀政要/卷{idx:02d}"),),
    )
    for idx in range(1, 11)
)


WORKS = {
    "zhu-shu-ji-nian": Work(
        "zhu-shu-ji-nian",
        "竹书纪年",
        "zhu-shu-ji-nian",
        "竹书纪年，汲冢出土古史之编年书，今本与古本辑校并收。",
        "https://zh.wikisource.org/wiki/竹書紀年",
        "https://ctext.org/wiki.pl?if=en&res=872517",
        260,
        (
            Unit(
                "今本",
                "jin-ben",
                ZHU_SHU_PARTS,
                expected_markers=("黃帝軒轅氏", "帝禹夏", "武王", "顯王"),
            ),
            Unit(
                "古本辑校",
                "gu-ben-ji-jiao",
                (SourcePart("古本辑校", "古本竹書紀年輯校"),),
                expected_markers=("自序", "黃帝", "隱王"),
                trim_before="=自序=",
                trim_after="=外部鏈接=",
            ),
        ),
    ),
    "yi-zhou-shu": Work(
        "yi-zhou-shu",
        "逸周书",
        "yi-zhou-shu",
        "逸周书十卷，保存周代史事、训诰与制度传说等材料。",
        "https://zh.wikisource.org/wiki/逸周書",
        "https://ctext.org/lost-book-of-zhou/zh",
        270,
        YIZHOUSHU_UNITS,
    ),
    "wu-yue-chun-qiu": Work(
        "wu-yue-chun-qiu",
        "吴越春秋",
        "wu-yue-chun-qiu",
        "吴越春秋十卷，东汉赵晔撰，记吴越兴亡史事。",
        "https://zh.wikisource.org/wiki/吳越春秋",
        "https://ctext.org/datawiki.pl?if=en&res=862567",
        280,
        WUYUE_UNITS,
    ),
    "yue-jue-shu": Work(
        "yue-jue-shu",
        "越绝书",
        "yue-jue-shu",
        "越绝书十五卷，记吴越地理、人物、政事与传说。",
        "https://zh.wikisource.org/wiki/越絕書",
        "https://ctext.org/yue-jue-shu/zh",
        290,
        YUEJUE_UNITS,
    ),
    "zhen-guan-zheng-yao": Work(
        "zhen-guan-zheng-yao",
        "贞观政要",
        "zhen-guan-zheng-yao",
        "贞观政要十卷，唐吴兢撰，辑唐太宗君臣问答与政论。",
        "https://zh.wikisource.org/wiki/貞觀政要",
        "https://ctext.org/wiki.pl?if=en&res=891288",
        300,
        ZHENGUAN_UNITS,
    ),
}

FORBIDDEN_FRONT_KEYS = {"categories", "source", "source_url", "source_license"}
FORBIDDEN_BODY_PATTERNS = [
    (re.compile(r"#REDIRECT|#重定向", re.I), "redirect"),
    (re.compile(r"\{\{|\}\}"), "raw template braces"),
    (re.compile(r"[{}]"), "raw brace"),
    (re.compile(r"\[\[|\]\]"), "raw wiki link"),
    (re.compile(r"<[^>]+>"), "raw HTML tag"),
    (re.compile(r"^#{4,6}\s", re.M), "low-level source heading"),
    (re.compile(r"Category:|分類:|分类:", re.I), "category line"),
    (re.compile(r"PD-old|Wikisource|維基文庫|维基文库"), "source boilerplate"),
    (re.compile(r"File:|thumb|px\|"), "image artifact"),
    (re.compile(r"href=|dictionary\.pl|text\.pl"), "HTML link artifact"),
    (re.compile(r"__NOEDITSECTION__|__TOC__"), "MediaWiki marker"),
    (re.compile(r"�"), "replacement character"),
    (re.compile(r"[\ue000-\uf8ff]"), "private-use character"),
]


def dump_yaml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(title: str, summary: str, weight: int, tag: str) -> str:
    return f"""---
title: {dump_yaml(title)}
date: {CONTENT_DATE}
weight: {weight}
tags: {json.dumps([tag], ensure_ascii=False)}
draft: {"true" if CONTENT_DRAFT else "false"}
summary: {dump_yaml(summary)}
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> dict:
    return json.loads(fetch_text(url))


def fetch_wikisource_raw(title: str) -> str:
    query = urllib.parse.urlencode({"title": title, "action": "raw"})
    try:
        return fetch_text(f"{WIKISOURCE_RAW}?{query}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Could not fetch Wikisource page: {title}") from exc


def wikisource_query(params: dict[str, str | int]) -> dict:
    query = urllib.parse.urlencode(params)
    return fetch_json(f"{WIKISOURCE_API}?{query}")


def apply_source_trims(raw: str, unit: Unit) -> str:
    text = raw
    if unit.trim_before and unit.trim_before in text:
        text = text[text.index(unit.trim_before) :]
    if unit.trim_after and unit.trim_after in text:
        text = text[: text.index(unit.trim_after)]
    return text


def strip_template(raw: str, name: str) -> str:
    while "{{" + name in raw:
        raw = remove_balanced(raw, "{{" + name, "}}")
    return raw


def preclean_wikitext(raw: str) -> str:
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    raw = re.sub(r"\[\[(?:File|文件|Image|圖像|图像):[^\]]+\]\]", "", raw, flags=re.I)
    raw = re.sub(r"\{\{另\|([^|}]+)\|[^}]+\}\}", r"\1", raw)
    raw = re.sub(r"\{\{(?:blue|resize)\|([^{}|]+)\}\}", r"\1", raw)
    raw = re.sub(r"\{\{color\|[^{}|]+\|([^{}]+)\}\}", r"\1", raw)
    for name in ("footer", "PD-old", "Wikipedia", "seealso", "align", "檢索"):
        raw = strip_template(raw, name)
    return raw


def normalize_heading_line(line: str) -> str:
    match = re.fullmatch(r"={1,6}\s*(.+?)\s*={1,6}", line)
    if match:
        title = match.group(1).strip()
        return f"### {title}"
    return line


def normalize_blocks(text: str) -> str:
    output: list[str] = []
    paragraph: list[str] = []
    pending_label: str | None = None

    def is_year_label(value: str) -> bool:
        return bool(re.fullmatch(r"(?:元|[一二三四五六七八九十百廿卅〇零]+)年(?:[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]+)?", value))

    def merge_label(label: str, value: str) -> str:
        if value.startswith(label) or value.startswith(("后" + label, "帝" + label, "王" + label)):
            return value
        if is_year_label(label):
            return label + value
        return f"{label}：{value}"

    def split_long_paragraph(value: str, target: int = 900) -> list[str]:
        if len(value) <= target:
            return [value]
        pieces = re.split(r"([。！？；])", value)
        chunks: list[str] = []
        current = ""
        for idx in range(0, len(pieces), 2):
            sentence = pieces[idx]
            if idx + 1 < len(pieces):
                sentence += pieces[idx + 1]
            if current and len(current) + len(sentence) > target:
                chunks.append(current)
                current = sentence
            else:
                current += sentence
        if current:
            chunks.append(current)
        return chunks or [value]

    def flush_paragraph() -> None:
        if not paragraph:
            return
        joined = "".join(paragraph)
        joined = re.sub(r"\s+", " ", joined).strip()
        if joined:
            output.extend(split_long_paragraph(joined))
        paragraph.clear()

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = html_unescape(raw_line)
        line = line.strip().strip("\ufeff")
        line = normalize_heading_line(line)
        line = re.sub(r"^:+", "", line).strip()
        line = line.replace("\u3000", "")
        line = re.sub(r"[ \t]+", " ", line).strip()

        if not line:
            if pending_label:
                output.append(pending_label)
                pending_label = None
            flush_paragraph()
            continue
        heading = re.match(r"^(#{2,6})\s+(.+)$", line)
        if heading:
            marks, title = heading.group(1), heading.group(2).strip()
            if len(marks) <= 3:
                if pending_label:
                    output.append(pending_label)
                    pending_label = None
                flush_paragraph()
                output.append(f"{marks} {title}")
            else:
                if pending_label:
                    output.append(pending_label)
                flush_paragraph()
                pending_label = title
            continue
        duplicated_heading = re.match(
            r"^(#{2,6}\s+)([\u3400-\u9fff]{1,12})(\2[，、。；：].*)$",
            line,
        )
        if duplicated_heading:
            flush_paragraph()
            output.append(f"{duplicated_heading.group(1)}{duplicated_heading.group(2)}")
            paragraph.append(duplicated_heading.group(3))
            continue
        if line.startswith("### "):
            flush_paragraph()
            output.append(line)
            continue
        if re.fullmatch(r"\*+", line):
            flush_paragraph()
            continue
        if pending_label:
            line = merge_label(pending_label, line)
            pending_label = None
        paragraph.append(line)

    if pending_label:
        output.append(pending_label)
    flush_paragraph()
    return "\n\n".join(output).strip()


def html_unescape(text: str) -> str:
    # Avoid importing html under a name that can be confused with local page HTML.
    import html as html_module

    return html_module.unescape(text)


def clean_body(raw: str, unit: Unit) -> str:
    raw = preclean_wikitext(apply_source_trims(raw, unit))
    text = clean_wikitext(raw)
    text = re.sub(r"</?onlyinclude\b[^>]*>", "", text)
    text = re.sub(r"</?poem\b[^>]*>", "", text)
    text = re.sub(r"<templatestyles\b[^>]*>", "", text)
    text = re.sub(r"<references\s*/?>", "", text)
    text = re.sub(r"</?(?:small|u|span|center|big)\b[^>]*>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^Category:.*$", "", text, flags=re.M | re.I)
    text = re.sub(r"^\[\[Category:[^\]]+\]\]$", "", text, flags=re.M | re.I)
    text = re.sub(r"^\s*\|[A-Za-z_-]+\s*=.*$", "", text, flags=re.M)
    text = re.sub(r"^{{[^{}]+}}$", "", text, flags=re.M)
    text = text.replace("{{", "").replace("}}", "")
    text = text.replace("{", "").replace("}", "")
    text = text.replace("\ue05c", "醟")
    text = normalize_blocks(text)
    text = re.split(r"\n###\s*校[勘刊校]?[記记]\b", text, maxsplit=1)[0].strip()

    lines = []
    first_patterns = [re.compile(pattern) for pattern in unit.remove_first_line_patterns]
    for line in text.splitlines():
        if not lines and any(pattern.search(line.strip()) for pattern in first_patterns):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def body_for_unit(unit: Unit) -> str:
    rendered_parts: list[str] = []
    for part in unit.source_parts:
        raw = fetch_wikisource_raw(part.wiki_title)
        body = clean_body(raw, unit)
        if not body:
            raise ValueError(f"{part.wiki_title}: empty body after cleaning")
        if len(unit.source_parts) > 1:
            body = f"### {part.title}\n\n{body}"
        rendered_parts.append(body)
        time.sleep(FETCH_DELAY)
    return "\n\n".join(rendered_parts).strip()


def write_page(path: Path, title: str, summary: str, weight: int, tag: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(title, summary, weight, tag) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def write_work_index(work: Work) -> None:
    write_page(
        HISTORY_DIR / work.slug / "_index.md",
        work.title,
        work.summary,
        work.weight,
        work.title,
    )


def generate_work(work: Work, clean: bool) -> int:
    out_dir = HISTORY_DIR / work.slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    write_work_index(work)

    for index, unit in enumerate(work.units, start=1):
        body = body_for_unit(unit)
        if len(body) < 100:
            raise ValueError(f"{work.title}-{unit.title}: body too short")
        for marker in unit.expected_markers:
            if marker not in body:
                raise ValueError(f"{work.title}-{unit.title}: missing marker {marker}")
        write_page(
            out_dir / f"{work.slug}-{unit.slug}.md",
            f"{work.title}-{unit.title}",
            f"{work.title}：{unit.title}",
            index,
            work.title,
            body,
        )
        print(f"Generated {work.title}-{unit.title} ({len(body)} chars)")

    return len(work.units)


def parse_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip().splitlines()
    body = text[end + 5 :]
    fm: dict[str, str] = {}
    for line in raw:
        if ":" in line:
            key, value = line.split(":", 1)
            fm[key.strip()] = value.strip()
    return fm, body


def validate_page(path: Path, expected_tag: str, check_body: bool = True) -> list[str]:
    problems: list[str] = []
    rel = path.relative_to(ROOT)
    fm, body = parse_front_matter(path)
    if not fm:
        return [f"{rel}: missing front matter"]

    forbidden = FORBIDDEN_FRONT_KEYS.intersection(fm)
    if forbidden:
        problems.append(f"{rel}: forbidden front matter {sorted(forbidden)}")
    if fm.get("tags") != json.dumps([expected_tag], ensure_ascii=False):
        problems.append(f"{rel}: expected tags {[expected_tag]}, got {fm.get('tags')}")
    if fm.get("draft") != "true":
        problems.append(f"{rel}: expected draft true, got {fm.get('draft')}")
    if fm.get("showToc") != "false":
        problems.append(f"{rel}: expected showToc false")

    if not check_body:
        return problems

    body = body.strip()
    if len(body) < 100:
        problems.append(f"{rel}: body too short")
    for pattern, label in FORBIDDEN_BODY_PATTERNS:
        if pattern.search(body):
            problems.append(f"{rel}: residual {label}")
            break
    for line_no, line in enumerate(body.splitlines(), start=1):
        if len(line) > 3000:
            problems.append(f"{rel}: line {line_no} too long ({len(line)} chars)")
            break
    return problems


def check_work(work: Work, source_check: bool) -> int:
    problems: list[str] = []
    out_dir = HISTORY_DIR / work.slug
    index_file = out_dir / "_index.md"
    if not index_file.exists():
        problems.append(f"{work.title}: missing _index.md")
    else:
        problems.extend(validate_page(index_file, work.title, check_body=False))

    expected_files = [out_dir / f"{work.slug}-{unit.slug}.md" for unit in work.units]
    actual_files = sorted(path for path in out_dir.glob("*.md") if path.name != "_index.md")
    if set(actual_files) != set(expected_files):
        problems.append(
            f"{work.title}: file list mismatch, expected {[p.name for p in expected_files]}, "
            f"got {[p.name for p in actual_files]}"
        )

    for index, (unit, path) in enumerate(zip(work.units, expected_files, strict=True), start=1):
        if not path.exists():
            problems.append(f"{path.relative_to(ROOT)}: missing")
            continue
        problems.extend(validate_page(path, work.title))
        fm, body = parse_front_matter(path)
        if fm.get("weight") != str(index):
            problems.append(f"{path.relative_to(ROOT)}: expected weight {index}")
        for marker in unit.expected_markers:
            if marker not in body:
                problems.append(f"{path.relative_to(ROOT)}: missing marker {marker}")
        if source_check:
            fresh_body = body_for_unit(unit)
            if body.strip() != fresh_body.strip():
                problems.append(f"{path.relative_to(ROOT)}: differs from cleaned source")

    if problems:
        print(f"CHECK FAILED: {work.title}")
        for problem in problems[:100]:
            print(f"  - {problem}")
        if len(problems) > 100:
            print(f"  ... and {len(problems) - 100} more")
        return 1
    print(f"CHECK OK: {work.title} {len(work.units)} content files")
    return 0


def selected_works(text: str | None, all_texts: bool) -> list[Work]:
    if all_texts:
        return list(WORKS.values())
    if text:
        return [WORKS[text]]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", choices=sorted(WORKS), help="Generate or check one work")
    parser.add_argument("--all", action="store_true", help="Generate or check all works")
    parser.add_argument("--clean", action="store_true", help="Remove target directories first")
    parser.add_argument("--check", action="store_true", help="Validate local generated Markdown")
    parser.add_argument(
        "--source-check",
        action="store_true",
        help="Regenerate cleaned source in memory and compare with local Markdown",
    )
    args = parser.parse_args()

    works = selected_works(args.text, args.all)
    if not works:
        parser.print_help()
        return 0

    if args.check or args.source_check:
        status = 0
        for work in works:
            status |= check_work(work, source_check=args.source_check)
        return status

    total = 0
    for work in works:
        total += generate_work(work, clean=args.clean)
    print(f"DONE: generated {total} content files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
