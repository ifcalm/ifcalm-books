#!/usr/bin/env python3
"""Generate the second wave of Yogacara Lun-zang texts from CBETA."""

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
YUJIA_ROOT = ROOT / "content/posts/buddha/lunzang/yujia"
DATE = "2026-06-05"


COLLECTIONS = {
    "wei-shi-er-shi-lun": {
        "work": "T1590",
        "display_title": "唯识二十论",
        "tag": "唯识二十论",
        "slug": "wei-shi-er-shi-lun",
        "target": "wei-shi-er-shi-lun",
        "total_juan": 1,
        "weight": 15,
        "summary": "唯识二十论一卷。",
        "expected_category": "瑜伽部類",
        "removable_title_patterns": [r"^唯識二十論一卷$"],
        "removable_bylines": {"世親菩薩造", "大唐三藏法師玄奘奉詔譯"},
    },
    "cheng-wei-shi-lun": {
        "work": "T1585",
        "display_title": "成唯识论",
        "tag": "成唯识论",
        "slug": "cheng-wei-shi-lun",
        "target": "cheng-wei-shi-lun",
        "total_juan": 10,
        "weight": 30,
        "summary": "成唯识论十卷。",
        "expected_category": "瑜伽部類",
        "removable_title_patterns": [r"^成唯識論卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"護法等菩薩造", "三藏法師玄奘奉詔譯"},
    },
    "she-da-cheng-lun-ben": {
        "work": "T1594",
        "display_title": "摄大乘论本",
        "tag": "摄大乘论本",
        "slug": "she-da-cheng-lun-ben",
        "target": "she-da-cheng-lun-ben",
        "total_juan": 3,
        "weight": 40,
        "summary": "摄大乘论本三卷。",
        "expected_category": "瑜伽部類",
        "removable_title_patterns": [r"^攝大乘論本卷[上中下]$"],
        "removable_bylines": {"無著菩薩造", "三藏法師玄奘奉詔譯"},
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def target_path(config: dict) -> Path:
    return YUJIA_ROOT / config["target"]


def drop_repeated_title_and_byline(config: dict, blocks):
    cleaned = []
    title_patterns = [re.compile(pattern) for pattern in config["removable_title_patterns"]]
    removable_bylines = {normalize_text(item) for item in config["removable_bylines"]}

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and any(pattern.fullmatch(normalized) for pattern in title_patterns):
            continue
        if block_type == "byline" and normalized in removable_bylines:
            continue
        cleaned.append((block_type, level, text))
    return cleaned


def fetch_blocks(config: dict, juan: int):
    raw = fetch_text(API_URL.format(work=config["work"], juan=juan))
    data = json.loads(raw)
    work_info = data.get("work_info") or {}
    if int(work_info.get("juan") or 0) != config["total_juan"]:
        raise RuntimeError(
            f"{config['display_title']} CBETA 卷数 "
            f"{work_info.get('juan')} != expected {config['total_juan']}"
        )
    if work_info.get("category") != config["expected_category"]:
        raise RuntimeError(
            f"{config['display_title']} CBETA 部类 "
            f"{work_info.get('category')} != expected {config['expected_category']}"
        )

    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"{config['display_title']} 卷{juan} API 返回为空")

    parser = CbetaJuanParser()
    parser.feed(html.unescape(results[0]))
    if not parser.blocks:
        raise RuntimeError(f"{config['display_title']} 卷{juan} 未解析到正文段落")
    return drop_repeated_title_and_byline(config, parser.blocks)


def write_collection_index(config: dict) -> None:
    target = target_path(config)
    target.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "---",
            f'title: "{config["display_title"]}"',
            f"date: {DATE}",
            f'tags: ["{config["tag"]}"]',
            "draft: true",
            f'summary: "{config["summary"]}"',
            "showToc: false",
            "tocOpen: false",
            "ShowShareButtons: false",
            f'weight: {config["weight"]}',
            "---",
            "",
            f'收录《{config["display_title"]}》{chinese_number(config["total_juan"])}卷。',
            "",
        ]
    )
    (target / "_index.md").write_text(content, encoding="utf-8")


def front_matter(config: dict, juan: int) -> list[str]:
    cn = chinese_number(juan)
    return [
        "---",
        f'title: "{config["display_title"]} 卷第{cn}"',
        f"date: {DATE}",
        f'tags: ["{config["tag"]}"]',
        "draft: true",
        f'summary: "{config["display_title"]}卷第{cn}"',
        "showToc: false",
        "tocOpen: false",
        "ShowShareButtons: false",
        f"weight: {juan}",
        "---",
        "",
    ]


def render_markdown(config: dict, juan: int, blocks) -> str:
    lines = front_matter(config, juan)
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


def write_juan(config: dict, juan: int) -> Path:
    blocks = fetch_blocks(config, juan)
    target = target_path(config)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{config['slug']}-{juan:03d}.md"
    path.write_text(render_markdown(config, juan, blocks), encoding="utf-8")
    return path


def generate_collection(config: dict, start: int, end: int, workers: int) -> None:
    write_collection_index(config)
    juans = list(range(start, end + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(write_juan, config, juan): juan for juan in juans}
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            juan = future_map[future]
            path = future.result()
            print(f"[{completed:02d}/{len(juans):02d}] {config['display_title']} 卷{juan:03d} -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=sorted(COLLECTIONS), help="Only generate one collection.")
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    selected = (
        {args.collection: COLLECTIONS[args.collection]}
        if args.collection
        else COLLECTIONS
    )
    for config in selected.values():
        start = args.start or 1
        end = args.end or config["total_juan"]
        if start < 1 or end > config["total_juan"] or start > end:
            raise SystemExit(f"{config['display_title']} 卷号范围必须在 1..{config['total_juan']} 内")
        generate_collection(config, start, end, args.workers)


if __name__ == "__main__":
    main()
