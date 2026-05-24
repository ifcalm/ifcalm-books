#!/usr/bin/env python3
"""Generate 二十四史 Markdown pages from the Chinese Notes corpus.

Chinese Notes provides a CC BY 4.0 corpus with per-text metadata files under
``data/corpus``.  The metadata is important because several histories split a
canonical volume into 上/下/之一 parts.  This generator groups those parts back
to the standard 二十四史 volume counts used by the site.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import generate_history_from_wikisource as wikisource
from setup_history_structure import HISTORIES


ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT / "content" / "posts" / "history"
DATE = "2026-05-24"
DEFAULT_SOURCE_DIR = Path("/tmp/ifcalm-chinesenotes")
CHINESE_NOTES_REPO = "https://github.com/alexamies/chinesenotes.com.git"
SOURCE_URL = "https://chinesenotes.com/corpus.html"
SOURCE_LICENSE = "CC BY 4.0"
WIKISOURCE_LICENSE = "CC BY-SA 4.0"
HANCHUAN_LICENSE = "Public domain source text"
KANRIPO_LICENSE = "CC BY-SA 4.0"


CN_DIRS = {
    "shi-ji": "shiji",
    "han-shu": "hanshu",
    "hou-han-shu": "houhanshu",
    "san-guo-zhi": "sanguozhi",
    "jin-shu": "jinshu",
    "song-shu": "songshu",
    "nan-qi-shu": "nanqishu",
    "liang-shu": "liangshu",
    "chen-shu": "chenshu",
    "wei-shu": "weishu",
    "bei-qi-shu": "beiqishu",
    "zhou-shu": "zhoushu",
    "sui-shu": "suishu",
    "nan-shi": "nanshi",
    "bei-shi": "beishi",
    "jiu-tang-shu": "jiutangshu",
    "xin-tang-shu": "xintangshu",
    "jiu-wu-dai-shi": "jiuwudaishi",
    "xin-wu-dai-shi": "xinwudaishi",
    "song-shi": "songshi",
    "liao-shi": "liaoshi",
    "jin-shi": "jinshi",
    "yuan-shi": "yuanshi",
    "ming-shi": "mingshi",
}

HANCHUAN_DIRS = {
    "ming-shi": "a24",
}

KANRIPO_REPOS = {
    "jin-shu": "KR2a0015",
    "song-shi": "KR2a0032",
    "jin-shi": "KR2a0035",
}

CHINESE_DIGITS = {
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


@dataclass
class Entry:
    source_file: str
    title: str
    volume: int
    part_title: str


@dataclass
class SourceInfo:
    name: str
    url: str
    license: str


def chinese_int(text: str) -> int | None:
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "十" not in text and "百" not in text and len(text) > 1:
        digits: list[str] = []
        for ch in text:
            if ch not in CHINESE_DIGITS:
                return None
            digits.append(str(CHINESE_DIGITS[ch]))
        return int("".join(digits))

    total = 0
    current = 0
    for ch in text:
        if ch == "百":
            total += (current or 1) * 100
            current = 0
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch in CHINESE_DIGITS:
            current = CHINESE_DIGITS[ch]
        else:
            return None
    return total + current


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def volume_group_dir(vol: int, total: int, chunk: int = 30) -> str:
    start = ((vol - 1) // chunk) * chunk + 1
    end = min(start + chunk - 1, total)
    return f"{start:03d}-{end:03d}"


def strip_english_tail(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\s+Volume\s+\d+[A-Za-z]?.*$", "", title).strip()
    title = re.sub(
        r"\s+(Annals|Tables|Treatises|Biographies|Genealogies|Autobiographical|House|Yearly)\b.*$",
        "",
        title,
    ).strip()
    return title


def volume_from_title(title: str, slug: str = "") -> int | None:
    m = re.search(r"卷\s*([0-9一二三四五六七八九十百零〇]+)", title)
    if m:
        return chinese_int(m.group(1))
    if slug == "hou-han-shu":
        m = re.match(r"第([一二三四五六七八九十百零〇]+)\s", title)
        if m:
            n = chinese_int(m.group(1))
            if n is not None:
                return 90 + n
    m = re.search(r"\bVolume\s+(\d+)", title)
    if m:
        return int(m.group(1))
    return None


def parse_entries(source_dir: Path, hist: dict) -> list[Entry]:
    slug = hist["slug"]
    cn_dir = CN_DIRS[slug]
    csv_path = source_dir / "data" / "corpus" / f"{cn_dir}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"missing metadata file: {csv_path}")

    entries: list[Entry] = []
    shiji_seq = 1
    for raw in csv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        source_file, _html_file, title = parts[0], parts[1], parts[2]
        if not source_file.endswith(".txt"):
            continue
        if "000" in Path(source_file).stem:
            continue

        if slug == "shi-ji":
            volume = shiji_seq
            shiji_seq += 1
        else:
            volume = volume_from_title(title, slug)
            if volume is None:
                continue

        if not 1 <= volume <= hist["volumes"]:
            continue

        part_title = strip_english_tail(title)
        entries.append(Entry(source_file=source_file, title=title, volume=volume, part_title=part_title))

    grouped = {vol for vol in range(1, hist["volumes"] + 1)}
    found = {entry.volume for entry in entries}
    missing = sorted(grouped - found)
    if missing:
        raise RuntimeError(f"{hist['title']} missing volumes in metadata: {missing[:20]}")
    return entries


def cjk_count(text: str) -> int:
    return sum(1 for ch in text if "\u3400" <= ch <= "\u9fff" or "\uf900" <= ch <= "\ufaff")


def clean_line(line: str) -> str | None:
    line = line.strip()
    if not line:
        return ""
    if "引用错误" in line or "引用錯誤" in line:
        return None
    if line == "目录":
        return None
    if re.match(r"^[一二三四五六七八九十百零〇０-９0-9]+頁", line) and "按：" in line:
        return None
    if "维基百科條目" in line or "維基百科條目" in line or "维基百科标志" in line or "維基百科標誌" in line:
        return None
    if line.startswith(("Chinese text:", "public domain worldwide", "Source:", "Retrieved from")):
        return None
    if re.match(r"^</?(p|ol|li|h\d|a)\b", line, re.I):
        return None
    if cjk_count(line) == 0 and re.search(r"[A-Za-z]{3,}", line):
        return None

    line = re.sub(r"\s+Volume\s+\d+[A-Za-z]?.*$", "", line).strip()
    line = re.sub(
        r"\s+(Annals|Tables|Treatises|Biographies|Genealogies|Autobiographical|House|Yearly)\b.*$",
        "",
        line,
    ).strip()
    line = re.sub(r"\{\{[^{}|]*\|", "", line)
    line = line.replace("{{", "").replace("}}", "")
    line = re.sub(r"<([^>\n]{1,12})>", r"〈\1〉", line)
    return line


def clean_text(raw: str) -> str:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # Drop trailing source/license notes and Chinese Notes proofreading notes.
    for idx in range(max(0, len(lines) - 30), len(lines)):
        stripped = lines[idx].strip()
        if stripped == "校" or stripped.startswith("全文以") or stripped.startswith("Chinese text:"):
            lines = lines[:idx]
            break

    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        value = clean_line(line)
        if value is None:
            continue
        if value == "":
            if not previous_blank and cleaned:
                cleaned.append("")
            previous_blank = True
            continue
        cleaned.append(value)
        previous_blank = False

    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def write_frontmatter(
    path: Path,
    title: str,
    summary: str,
    weight: int,
    tags: list[str],
    body: str = "",
) -> None:
    lines = [
        "---",
        f"title: {yaml_string(title)}",
        f"date: {DATE}",
        f"weight: {weight}",
        f"tags: {yaml_list(tags)}",
        "draft: false",
        f"summary: {yaml_string(summary)}",
        "showToc: false",
        "tocOpen: false",
        "ShowShareButtons: false",
    ]
    lines.extend(["---", "", body.rstrip()])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def ensure_indexes() -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    write_frontmatter(
        OUT_BASE / "_index.md",
        "二十四史",
        "二十四史，中国古代各朝撰写的二十四部史书的总称。",
        5,
        ["二十四史"],
    )
    for idx, hist in enumerate(HISTORIES, start=1):
        hist_dir = OUT_BASE / hist["slug"]
        write_frontmatter(
            hist_dir / "_index.md",
            hist["title"],
            hist["summary"],
            idx * 10,
            [hist["title"]],
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


def prepare_source(source_dir: Path) -> None:
    cn_paths = [f"corpus/{name}" for name in CN_DIRS.values()]
    csv_paths = [f"data/corpus/{name}.csv" for name in CN_DIRS.values()]
    paths = ["license.txt", "README.md", *cn_paths, *csv_paths]

    if not (source_dir / ".git").exists():
        if source_dir.exists():
            shutil.rmtree(source_dir)
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                CHINESE_NOTES_REPO,
                str(source_dir),
            ],
            check=True,
        )

    subprocess.run(
        [
            "git",
            "-c",
            "http.version=HTTP/1.1",
            "sparse-checkout",
            "set",
            "--skip-checks",
            *paths,
        ],
        cwd=source_dir,
        check=True,
    )


FORBIDDEN_BODY_PATTERNS = [
    (re.compile(r"Chinese text:"), "Chinese Notes license tail"),
    (re.compile(r"public domain worldwide"), "public-domain boilerplate"),
    (re.compile(r"维基百科條目|維基百科條目|维基百科标志|維基百科標誌"), "Wikipedia link boilerplate"),
    (re.compile(r"</?(p|ol|li|h\d|a)\b", re.I), "HTML tag"),
    (re.compile(r"</?[A-Za-z][^>\n]*>|</ref>|<ref\b", re.I), "HTML tag"),
    (re.compile(r"#REDIRECT", re.I), "#REDIRECT"),
    (re.compile(r"<references?\b", re.I), "<references>"),
    (re.compile(r"引用错误|引用錯誤"), "reference error"),
    (re.compile(r"\{\{|\}\}"), "raw template braces"),
    (re.compile(r"Category:"), "Category line"),
    (re.compile(r"(?m)^\s*表略\s*$|表格略|以下表格略"), "表格略"),
]

RAW_SOURCE_PATTERNS = [
    (re.compile(r"引用错误|引用錯誤"), "raw source reference error"),
]

_WIKISOURCE_PAGE_CACHE: dict[str, dict[int, list[str]]] = {}


def raw_source_issue(raw: str) -> str | None:
    for pattern, label in RAW_SOURCE_PATTERNS:
        if pattern.search(raw):
            return label
    return None


def body_issue(body: str, min_len: int = 50) -> str | None:
    if len(body.strip()) < min_len:
        return "正文过短"
    for pattern, label in FORBIDDEN_BODY_PATTERNS:
        if pattern.search(body):
            return label
    return None


def clean_wikisource_body(body: str) -> str:
    cleaned: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if "◄" in stripped or "►" in stripped:
            continue
        if "参阅维基百科" in stripped or "參閱維基百科" in stripped:
            continue
        if "公有领域" in stripped or "公有領域" in stripped:
            continue
        if stripped.startswith("Public domain"):
            continue
        if "引用错误" in stripped or "引用錯誤" in stripped:
            continue
        stripped = re.sub(r"<([^>\n]{1,12})>", r"〈\1〉", stripped)
        cleaned.append(stripped)
    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def wikisource_fallback_body(hist: dict, vol: int) -> tuple[str, SourceInfo] | None:
    wiki_title = wikisource.WIKI_TITLES[hist["slug"]]
    if wiki_title not in _WIKISOURCE_PAGE_CACHE:
        _WIKISOURCE_PAGE_CACHE[wiki_title] = wikisource.discover_volume_pages(wiki_title, hist["volumes"])

    titles = _WIKISOURCE_PAGE_CACHE[wiki_title].get(vol, [])
    if not titles:
        return None

    parts: list[str] = []
    resolved_titles: list[str] = []
    for title in titles:
        resolved, rendered_html = wikisource.fetch_rendered_page(title)
        body = clean_wikisource_body(wikisource.html_to_markdown(rendered_html))
        if body:
            parts.append(body)
            resolved_titles.append(resolved)
        time.sleep(0.05)

    body = "\n\n".join(parts).strip()
    if not body:
        return None
    source_title = resolved_titles[0] if resolved_titles else titles[0]
    source_url = "https://zh.wikisource.org/wiki/" + urllib.parse.quote(source_title.replace(" ", "_"))
    return body, SourceInfo("Wikisource rendered page", source_url, WIKISOURCE_LICENSE)


def clean_hanchuan_body(body: str) -> str:
    lines = body.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().startswith("###### "):
            lines = lines[idx + 1 :]
            break

    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if "首頁 /" in stripped or "上卷 /" in stripped or "下卷 /" in stripped:
            continue
        if "漢川草廬" in stripped or stripped.startswith("二十四史-"):
            continue
        stripped = re.sub(r"<([^>\n]{1,12})>", r"〈\1〉", stripped)
        cleaned.append(stripped)
    text = "\n".join(cleaned).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def hanchuan_fallback_body(hist: dict, vol: int) -> tuple[str, SourceInfo] | None:
    site_dir = HANCHUAN_DIRS.get(hist["slug"])
    if not site_dir:
        return None
    url = f"https://www.sidneyluo.net/a/{site_dir}/{vol:03d}.htm"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            rendered_html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    body = clean_hanchuan_body(wikisource.html_to_markdown(rendered_html))
    if not body:
        return None
    return body, SourceInfo("Hanchuan Caolu transcription", url, HANCHUAN_LICENSE)


def clean_kanripo_body(raw: str) -> str:
    text = raw.replace("¶", "\n")
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("#"):
            continue
        if re.match(r"^<pb:", stripped):
            continue
        if stripped == "欽定四庫全書":
            continue
        if "四庫全書" in stripped and len(stripped) < 16:
            continue
        stripped = re.sub(r"<([^>\n]{1,12})>", r"〈\1〉", stripped)
        lines.append(stripped)
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def kanripo_fallback_body(hist: dict, vol: int) -> tuple[str, SourceInfo] | None:
    repo = KANRIPO_REPOS.get(hist["slug"])
    if not repo:
        return None
    path = Path("/tmp/ifcalm-kanripo") / repo / f"{repo}_{vol:03d}.txt"
    if not path.exists():
        return None
    body = clean_kanripo_body(path.read_text(encoding="utf-8"))
    if not body:
        return None
    url = f"https://github.com/kanripo/{repo}"
    return body, SourceInfo("Kanseki Repository/Kanripo", url, KANRIPO_LICENSE)


def find_fallback_body(hist: dict, vol: int) -> tuple[str, SourceInfo] | None:
    for provider in (wikisource_fallback_body, hanchuan_fallback_body, kanripo_fallback_body):
        result = provider(hist, vol)
        if not result:
            continue
        body, source_info = result
        if not body_issue(body):
            return body, source_info
    return None


def generate_history(source_dir: Path, hist: dict, use_wikisource_fallback: bool = False) -> int:
    entries = parse_entries(source_dir, hist)
    by_volume: dict[int, list[Entry]] = {}
    for entry in entries:
        by_volume.setdefault(entry.volume, []).append(entry)

    total = hist["volumes"]
    written = 0
    for vol in range(1, total + 1):
        parts = by_volume[vol]
        bodies: list[str] = []
        source_issue: str | None = None
        for part in parts:
            raw_path = source_dir / "corpus" / part.source_file
            raw = raw_path.read_text(encoding="utf-8")
            source_issue = source_issue or raw_source_issue(raw)
            text = clean_text(raw)
            if not text:
                continue
            if len(parts) > 1:
                bodies.append(f"## {part.part_title}\n\n{text}")
            else:
                bodies.append(text)

        body = "\n\n".join(bodies).strip()
        if use_wikisource_fallback and (body_issue(body) or source_issue):
            fallback = find_fallback_body(hist, vol)
            if fallback:
                replacement_body, _fallback_source = fallback
                body = replacement_body
        title = f"{hist['title']} 卷{vol}"
        rel_dir = volume_group_dir(vol, total)
        out = OUT_BASE / hist["slug"] / rel_dir / f"{hist['slug']}-{vol:03d}.md"
        write_frontmatter(
            out,
            title,
            f"{hist['title']}卷{vol}。",
            vol,
            [hist["title"]],
            body=body,
        )
        written += 1

    return written


def clean_output_dir() -> None:
    if not OUT_BASE.exists():
        return
    for child in OUT_BASE.iterdir():
        if child.name == ".DS_Store":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def validate() -> int:
    expected_total = sum(hist["volumes"] for hist in HISTORIES)
    errors: list[str] = []
    files = list(OUT_BASE.glob("*/*/*.md"))
    volume_files = [p for p in files if re.search(r"-\d{3}\.md$", p.name)]
    if len(volume_files) != expected_total:
        errors.append(f"正文文件数量 {len(volume_files)} != 期望 {expected_total}")

    for hist in HISTORIES:
        slug = hist["slug"]
        found: set[int] = set()
        for path in (OUT_BASE / slug).glob("*/*.md"):
            m = re.match(rf"{re.escape(slug)}-(\d{{3}})\.md$", path.name)
            if m:
                found.add(int(m.group(1)))
        expected = set(range(1, hist["volumes"] + 1))
        missing = sorted(expected - found)
        extra = sorted(found - expected)
        if missing:
            errors.append(f"{hist['title']} 缺卷: {missing[:20]}")
        if extra:
            errors.append(f"{hist['title']} 多余卷: {extra[:20]}")

    for path in volume_files:
        text = path.read_text(encoding="utf-8")
        body = text.split("---", 2)[-1].strip()
        issue = body_issue(body)
        if issue == "正文过短":
            errors.append(f"正文过短: {path.relative_to(ROOT)}")
        elif issue:
            errors.append(f"残留 {issue}: {path.relative_to(ROOT)}")

    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        for err in errors[:200]:
            print(f"- {err}", file=sys.stderr)
        if len(errors) > 200:
            print(f"... {len(errors) - 200} more", file=sys.stderr)
        return 1

    print(f"VALIDATION OK: {expected_total} volume files")
    return 0


def source_report(source_dir: Path) -> int:
    ok = True
    for hist in HISTORIES:
        entries = parse_entries(source_dir, hist)
        volumes = {entry.volume for entry in entries}
        print(
            f"{hist['slug']:16} parts={len(entries):4} volumes={len(volumes):4} expected={hist['volumes']:4}"
        )
        if len(volumes) != hist["volumes"]:
            ok = False
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--prepare-source", action="store_true", help="clone/update Chinese Notes corpus cache")
    parser.add_argument("--all", action="store_true", help="generate all histories")
    parser.add_argument("--history", choices=[h["slug"] for h in HISTORIES], help="generate one history")
    parser.add_argument("--clean", action="store_true", help="remove existing generated history output first")
    parser.add_argument("--source-report", action="store_true", help="check source metadata counts")
    parser.add_argument("--validate", action="store_true", help="validate generated Markdown")
    parser.add_argument(
        "--wikisource-fallback",
        action="store_true",
        help="use alternate sources for empty, short, polluted, or incomplete source volumes",
    )
    args = parser.parse_args()

    if args.prepare_source:
        prepare_source(args.source_dir)

    if args.source_report:
        return source_report(args.source_dir)

    if args.clean:
        clean_output_dir()

    if args.all or args.history:
        ensure_indexes()
        targets = HISTORIES if args.all else [h for h in HISTORIES if h["slug"] == args.history]
        total = 0
        for hist in targets:
            count = generate_history(args.source_dir, hist, use_wikisource_fallback=args.wikisource_fallback)
            total += count
            print(f"{hist['title']}: wrote {count} volumes", flush=True)
        print(f"DONE: wrote {total} volume files", flush=True)

    if args.validate:
        return validate()

    if not (args.all or args.history or args.validate or args.source_report):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
