#!/usr/bin/env python3
"""Generate the core Baoji collection from CBETA's stable juan endpoint."""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
from pathlib import Path

from generate_bore_from_cbdata import CbetaJuanParser, chinese_number, fetch_text


ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://cbdata.dila.edu.tw/stable/juans?work={work}&juan={juan}&work_info=1&toc=1"

CONFIG = {
    "work": "T0310",
    "display_title": "大宝积经",
    "tag": "大宝积经",
    "slug": "da-bao-ji-jing",
    "target": ROOT / "content/posts/buddha/jingzang/baoji/da-bao-ji-jing",
    "total_juan": 120,
    "weight": 10,
    "summary": "《大宝积经》四十九会，共一百二十卷。",
    "index_intro": "收录《大宝积经》四十九会，共一百二十卷。",
}

TITLE_PATTERN = re.compile(r"^大寶積經卷第[零一二三四五六七八九十百]+$")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def collection_path(juan: int) -> Path:
    start = ((juan - 1) // 30) * 30 + 1
    end = min(start + 29, CONFIG["total_juan"])
    return CONFIG["target"] / f"{start:03d}-{end:03d}"


def work_payload(juan: int) -> dict:
    raw = fetch_text(API_URL.format(work=CONFIG["work"], juan=juan))
    return json.loads(raw)


def assembly_start_juans() -> set[int]:
    payload = work_payload(1)
    toc = payload.get("toc") or {}
    return {
        int(item["juan"])
        for item in toc.get("mulu", [])
        if item.get("type") == "會" and item.get("juan")
    }


def drop_repeated_title_and_nonassembly_bylines(
    blocks, juan: int, assembly_starts: set[int]
):
    cleaned = []
    preserve_bylines = juan in assembly_starts
    pending_byline = None
    removed_title_before = False

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and (
            normalized == "大寶積經" or TITLE_PATTERN.fullmatch(normalized)
        ):
            removed_title_before = True
            continue
        if preserve_bylines and block_type == "byline" and removed_title_before:
            pending_byline = (block_type, level, text)
            removed_title_before = False
            continue
        if pending_byline is not None and block_type == "head":
            cleaned.append((block_type, level, text))
            cleaned.append(pending_byline)
            pending_byline = None
            removed_title_before = False
            continue
        if block_type == "byline" and not preserve_bylines:
            continue
        cleaned.append((block_type, level, text))
        removed_title_before = False

    if pending_byline is not None:
        cleaned.append(pending_byline)
    return cleaned


def fetch_blocks(juan: int, assembly_starts: set[int]):
    data = work_payload(juan)
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"{CONFIG['display_title']} 卷{juan} API 返回为空")

    parser = CbetaJuanParser()
    parser.feed(html.unescape(results[0]))
    if not parser.blocks:
        raise RuntimeError(f"{CONFIG['display_title']} 卷{juan} 未解析到正文段落")
    return drop_repeated_title_and_nonassembly_bylines(parser.blocks, juan, assembly_starts)


def write_collection_index() -> None:
    target = CONFIG["target"]
    target.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "---",
            f'title: "{CONFIG["display_title"]}"',
            "date: 2026-05-17",
            f'tags: ["{CONFIG["tag"]}"]',
            'categories: ["佛学"]',
            "draft: false",
            f'summary: "{CONFIG["summary"]}"',
            "showToc: false",
            "tocOpen: false",
            "ShowShareButtons: false",
            f'weight: {CONFIG["weight"]}',
            "---",
            "",
            CONFIG["index_intro"],
            "",
        ]
    )
    (target / "_index.md").write_text(content, encoding="utf-8")


def write_range_indexes() -> None:
    for start in range(1, CONFIG["total_juan"] + 1, 30):
        end = min(start + 29, CONFIG["total_juan"])
        target = CONFIG["target"] / f"{start:03d}-{end:03d}"
        target.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            [
                "---",
                f'title: "{CONFIG["display_title"]} 卷第{chinese_number(start)}至卷第{chinese_number(end)}"',
                "date: 2026-05-17",
                f'tags: ["{CONFIG["tag"]}"]',
                'categories: ["佛学"]',
                "draft: false",
                f'summary: "{CONFIG["display_title"]}卷第{chinese_number(start)}至卷第{chinese_number(end)}"',
                "showToc: false",
                "tocOpen: false",
                "ShowShareButtons: false",
                f"weight: {start}",
                "---",
                "",
            ]
        )
        (target / "_index.md").write_text(content, encoding="utf-8")


def front_matter(juan: int) -> list[str]:
    cn = chinese_number(juan)
    return [
        "---",
        f'title: "{CONFIG["display_title"]} 卷第{cn}"',
        "date: 2026-05-17",
        f'tags: ["{CONFIG["tag"]}"]',
        'categories: ["佛学"]',
        "draft: false",
        f'summary: "{CONFIG["display_title"]}卷第{cn}"',
        "showToc: false",
        "tocOpen: false",
        "ShowShareButtons: false",
        f"weight: {juan}",
        "---",
        "",
    ]


def render_markdown(juan: int, blocks) -> str:
    lines = front_matter(juan)
    for block_type, level, text in blocks:
        if block_type == "head":
            try:
                heading_level = max(2, min(6, int(level or 2)))
            except ValueError:
                heading_level = 2
            lines.append("#" * heading_level + " " + text)
        elif block_type == "verse":
            lines.append("  \n".join(text.splitlines()))
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_juan(juan: int, assembly_starts: set[int]) -> Path:
    blocks = fetch_blocks(juan, assembly_starts)
    target = collection_path(juan)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{CONFIG['slug']}-{juan:03d}.md"
    path.write_text(render_markdown(juan, blocks), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    start = args.start or 1
    end = args.end or CONFIG["total_juan"]
    if start < 1 or end > CONFIG["total_juan"] or start > end:
        raise SystemExit(f"卷号范围必须在 1..{CONFIG['total_juan']} 内")

    assembly_starts = assembly_start_juans()
    write_collection_index()
    write_range_indexes()

    juans = list(range(start, end + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(write_juan, juan, assembly_starts): juan for juan in juans
        }
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            juan = future_map[future]
            path = future.result()
            print(f"[{completed:03d}/{len(juans):03d}] {CONFIG['display_title']} 卷{juan:03d} -> {path}")


if __name__ == "__main__":
    main()
