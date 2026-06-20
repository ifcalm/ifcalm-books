#!/usr/bin/env python3
"""Generate first-priority History-section texts.

This script intentionally extends the existing history area beyond 二十四史
without moving the already-published directory layout. The generated files keep
the repository's current Hugo front matter conventions and remain draft pages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_history_from_wikisource import (  # noqa: E402
    OUT_BASE,
    ROOT,
    discover_volume_pages,
    fetch_rendered_page,
    html_to_markdown,
    normalize_markdown,
    volume_group_dir,
)


DATE = "2026-06-20"

WORKS = {
    "zi-zhi-tong-jian": {
        "title": "资治通鉴",
        "wiki_title": "資治通鑑",
        "total": 294,
        "weight": 250,
        "summary": (
            "资治通鉴二百九十四卷，北宋司马光主编，"
            "上起周威烈王二十三年，下迄后周世宗显德六年。"
        ),
    },
}

FORBIDDEN_FRONT_KEYS = {"categories", "source", "source_url", "source_license"}
FORBIDDEN_BODY_PATTERNS = [
    (re.compile(r"#REDIRECT", re.I), "#REDIRECT"),
    (re.compile(r"<references?\b", re.I), "<references>"),
    (re.compile(r"\{\{|\}\}"), "raw template braces"),
    (re.compile(r"mw-parser-output|headerContainer"), "parser/header HTML"),
    (re.compile(r"^\| .*資治通鑑.*[◄►].*\|$", re.M), "source navigation row"),
    (re.compile(r"^(Category|分类|分類):", re.I | re.M), "Category line"),
    (re.compile(r"Textquality|__TOC__|北宋作品"), "source maintenance marker"),
    (re.compile(r"footer|href=", re.I), "HTML/footer artifact"),
    (re.compile(r"<[^>]+>"), "raw HTML tag"),
    (re.compile(r"\[\[|\]\]"), "raw wiki link"),
    (re.compile(r"^資治通鑑\s+(?:第[0-9零〇一二三四五六七八九十百千]+[卷巻]|[卷巻]第[0-9零〇一二三四五六七八九十百千]+)$", re.M), "repeated source title"),
    (re.compile(r"^卷第[0-9零〇一二三四五六七八九十百千]+$", re.M), "repeated source volume title"),
    (re.compile(r"^【】", re.M), "empty source title bracket"),
    (re.compile(r"^#{1,6}\s*校(?:[勘刊改])?[記记]\s*$", re.M), "collation heading"),
    (re.compile(r"此北宋作品在全世界都属于公有领域|Public domainPublic domain"), "source license footer"),
    (re.compile(r"^[，。！？；：、]", re.M), "broken punctuation-start line"),
    (re.compile(r"。[ \t]*[1-9]\d*　"), "fused numbered entries"),
    (re.compile(r"涒\s*□灘"), "known corrupted sexagenary year name"),
    (re.compile(r"[\ue000-\uf8ff]"), "private-use character"),
    (re.compile(r"�"), "replacement character"),
]


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def front_matter(
    title: str,
    summary: str,
    weight: int,
    tags: list[str],
    body: str = "",
) -> str:
    return (
        "\n".join(
            [
                "---",
                f"title: {yaml_string(title)}",
                f"date: {DATE}",
                f"weight: {weight}",
                f"tags: {yaml_list(tags)}",
                "draft: true",
                f"summary: {yaml_string(summary)}",
                "showToc: false",
                "tocOpen: false",
                "ShowShareButtons: false",
                "---",
                "",
                body.rstrip(),
            ]
        ).rstrip()
        + "\n"
    )


def write_markdown(
    path: Path,
    title: str,
    summary: str,
    weight: int,
    tags: list[str],
    body: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(title, summary, weight, tags, body),
        encoding="utf-8",
    )


def write_history_index() -> None:
    write_markdown(
        OUT_BASE / "_index.md",
        "史部",
        "史部，收录正史、编年、纪事本末、杂史等历史典籍。",
        5,
        ["史部"],
    )


def write_work_indexes(slug: str, work: dict[str, object]) -> None:
    title = str(work["title"])
    total = int(work["total"])
    out_dir = OUT_BASE / slug
    write_markdown(
        out_dir / "_index.md",
        title,
        str(work["summary"]),
        int(work["weight"]),
        [title],
    )

    for group_idx, start in enumerate(range(1, total + 1, 30), start=1):
        end = min(start + 29, total)
        write_markdown(
            out_dir / f"{start:03d}-{end:03d}" / "_index.md",
            f"{title} 卷{start}-{end}",
            f"{title}卷{start}至卷{end}。",
            group_idx,
            [title],
        )


def expected_paths(slug: str, work: dict[str, object]) -> list[Path]:
    total = int(work["total"])
    paths = [OUT_BASE / "_index.md", OUT_BASE / slug / "_index.md"]
    for start in range(1, total + 1, 30):
        end = min(start + 29, total)
        paths.append(OUT_BASE / slug / f"{start:03d}-{end:03d}" / "_index.md")
    for vol in range(1, total + 1):
        paths.append(
            OUT_BASE
            / slug
            / volume_group_dir(vol, total)
            / f"{slug}-{vol:03d}.md"
        )
    return paths


def fetch_volume_body(titles: list[str], delay: float) -> str:
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

    return normalize_markdown("\n\n".join(parts))


def clean_work_body(body: str) -> str:
    repeated_title = re.compile(
        r"^資治通鑑\s+(?:第[0-9零〇一二三四五六七八九十百千]+[卷巻]|[卷巻]第[0-9零〇一二三四五六七八九十百千]+)$"
    )
    repeated_volume = re.compile(r"^卷第[0-9零〇一二三四五六七八九十百千]+$")
    body = re.sub(r"涒\s*□灘", "涒灘", body)
    cleaned: list[str] = []

    for line in body.splitlines():
        stripped = line.strip()
        if repeated_title.match(stripped) or repeated_volume.match(stripped):
            continue
        if stripped.startswith("【】"):
            continue
        cleaned.append(stripped if stripped else "")

    separated: list[str] = []
    previous_nonblank = False
    for line in cleaned:
        if not line:
            if separated and separated[-1] != "":
                separated.append("")
            previous_nonblank = False
            continue
        if previous_nonblank:
            separated.append("")
        separated.append(line)
        previous_nonblank = True

    return normalize_markdown("\n".join(separated))


def generate_work(slug: str, clean: bool, delay: float) -> int:
    work = WORKS[slug]
    title = str(work["title"])
    total = int(work["total"])
    out_dir = OUT_BASE / slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)

    write_history_index()
    write_work_indexes(slug, work)

    pages = discover_volume_pages(str(work["wiki_title"]), total)
    missing = [vol for vol in range(1, total + 1) if not pages.get(vol)]
    if missing:
        raise RuntimeError(f"{title} missing Wikisource volume pages: {missing}")

    print(f"== {title} / {work['wiki_title']} ({total}卷) ==")
    print(
        f"Discovered {sum(len(items) for items in pages.values())} source page(s) "
        f"for {total} volume(s)."
    )

    for vol in range(1, total + 1):
        body = clean_work_body(fetch_volume_body(pages[vol], delay))
        if len(body) < 200:
            raise RuntimeError(f"{title} 卷{vol} body too short after cleaning.")

        write_markdown(
            out_dir / volume_group_dir(vol, total) / f"{slug}-{vol:03d}.md",
            f"{title} 卷{vol}",
            f"{title}卷{vol}。",
            vol,
            [title],
            body,
        )
        if vol == 1 or vol % 10 == 0 or vol == total:
            print(f"  [{vol:03d}/{total:03d}] OK ({len(body)} chars)", flush=True)

    return total


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
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


def validate_markdown_file(path: Path, expected_tag: str, check_body: bool) -> list[str]:
    problems: list[str] = []
    rel = path.relative_to(ROOT)
    text = path.read_text(encoding="utf-8")
    fm, body = parse_front_matter(text)
    if not fm:
        return [f"{rel}: missing front matter"]

    forbidden_front = FORBIDDEN_FRONT_KEYS.intersection(fm)
    if forbidden_front:
        problems.append(f"{rel}: forbidden front matter {sorted(forbidden_front)}")

    if fm.get("draft") != "true":
        problems.append(f"{rel}: draft is {fm.get('draft', '<missing>')}, expected true")
    if fm.get("showToc") != "false":
        problems.append(f"{rel}: showToc is {fm.get('showToc', '<missing>')}, expected false")

    if fm.get("tags") != yaml_list([expected_tag]):
        problems.append(f"{rel}: tags are {fm.get('tags', '<missing>')}, expected {[expected_tag]}")

    if not check_body:
        return problems

    body = body.strip()
    if len(body) < 200:
        problems.append(f"{rel}: body too short ({len(body)} chars)")
    for pattern, label in FORBIDDEN_BODY_PATTERNS:
        if pattern.search(body):
            problems.append(f"{rel}: residual {label}")
            break
    for line_no, line in enumerate(body.splitlines(), start=1):
        if len(line) > 8000:
            problems.append(f"{rel}: line {line_no} is unusually long ({len(line)} chars)")
            break
    previous_nonblank: tuple[int, str] | None = None
    for line_no, line in enumerate(body.splitlines(), start=1):
        if not line.strip():
            previous_nonblank = None
            continue
        if previous_nonblank is not None:
            prev_no, _prev_line = previous_nonblank
            problems.append(f"{rel}: body lines {prev_no} and {line_no} are not separated by a blank line")
            break
        previous_nonblank = (line_no, line)
    return problems


def validate_work(slug: str) -> int:
    work = WORKS[slug]
    title = str(work["title"])
    total = int(work["total"])
    out_dir = OUT_BASE / slug
    problems: list[str] = []

    for path in expected_paths(slug, work):
        if not path.exists():
            problems.append(f"missing expected path: {path.relative_to(ROOT)}")

    actual_groups = sorted(child.name for child in out_dir.iterdir() if child.is_dir()) if out_dir.exists() else []
    expected_groups = [
        f"{start:03d}-{min(start + 29, total):03d}"
        for start in range(1, total + 1, 30)
    ]
    if actual_groups != expected_groups:
        problems.append(f"{title}: range folders {actual_groups} != {expected_groups}")

    content_files = sorted(path for path in out_dir.glob("*/*.md") if path.name != "_index.md")
    if len(content_files) != total:
        problems.append(f"{title}: content file count {len(content_files)} != {total}")

    nums: list[int] = []
    for path in content_files:
        match = re.fullmatch(rf"{re.escape(slug)}-(\d{{3}})\.md", path.name)
        if not match:
            problems.append(f"{path.relative_to(ROOT)}: unexpected filename")
            continue
        vol = int(match.group(1))
        nums.append(vol)
        expected_group = volume_group_dir(vol, total)
        if path.parent.name != expected_group:
            problems.append(f"{path.relative_to(ROOT)}: expected group folder {expected_group}")
        problems.extend(validate_markdown_file(path, title, check_body=True))

    expected_nums = list(range(1, total + 1))
    if sorted(nums) != expected_nums:
        missing = sorted(set(expected_nums) - set(nums))
        extra = sorted(set(nums) - set(expected_nums))
        problems.append(f"{title}: volume sequence mismatch, missing={missing}, extra={extra}")
    if len(nums) != len(set(nums)):
        problems.append(f"{title}: duplicated volume number")

    for path in [OUT_BASE / slug / "_index.md", *sorted(out_dir.glob("*/_index.md"))]:
        if path.exists():
            problems.extend(validate_markdown_file(path, title, check_body=False))

    history_fm, _ = parse_front_matter((OUT_BASE / "_index.md").read_text(encoding="utf-8"))
    if history_fm.get("title") != yaml_string("史部"):
        problems.append("content/posts/history/_index.md: title is not 史部")
    if history_fm.get("tags") != yaml_list(["史部"]):
        problems.append("content/posts/history/_index.md: tags are not [史部]")

    first_file = out_dir / "001-030" / f"{slug}-001.md"
    last_file = out_dir / "271-294" / f"{slug}-294.md"
    if first_file.exists() and "威烈王" not in first_file.read_text(encoding="utf-8"):
        problems.append(f"{first_file.relative_to(ROOT)}: missing expected first-volume boundary text")
    if last_file.exists() and "跋" not in last_file.read_text(encoding="utf-8"):
        problems.append(f"{last_file.relative_to(ROOT)}: missing expected final-volume postface heading")

    if problems:
        print("VALIDATION FAILED")
        for problem in problems[:200]:
            print(f"  - {problem}")
        if len(problems) > 200:
            print(f"  ... and {len(problems) - 200} more")
        return 1

    print(f"VALIDATION OK: {title} {total} volume files")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", choices=sorted(WORKS), default="zi-zhi-tong-jian")
    parser.add_argument("--all", action="store_true", help="generate the selected text")
    parser.add_argument("--clean", action="store_true", help="remove generated work before writing")
    parser.add_argument("--check", action="store_true", help="validate generated files")
    parser.add_argument("--delay", type=float, default=0.05, help="delay between source requests")
    args = parser.parse_args()

    if args.all:
        generated = generate_work(args.text, clean=args.clean, delay=args.delay)
        print(f"DONE: generated {generated} files")
    if args.check:
        raise SystemExit(validate_work(args.text))
    if not args.all and not args.check:
        parser.print_help()


if __name__ == "__main__":
    main()
