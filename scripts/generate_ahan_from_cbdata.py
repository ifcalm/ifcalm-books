#!/usr/bin/env python3
"""Generate Āgama collections from CBETA's stable juan endpoint."""

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

COLLECTIONS = {
    "chang-ahan": {
        "work": "T0001",
        "source_title": "長阿含經",
        "display_title": "长阿含经",
        "tag": "长阿含经",
        "slug": "chang-ahan",
        "target": ROOT / "content/posts/buddha/ahan/chang-ahan",
        "total_juan": 22,
        "weight": 10,
        "summary": "长阿含经二十二卷。",
        "removable_bylines": {"後秦弘始年佛陀耶舍共竺佛念譯"},
    },
    "zhong-ahan": {
        "work": "T0026",
        "source_title": "中阿含經",
        "display_title": "中阿含经",
        "tag": "中阿含经",
        "slug": "zhong-ahan",
        "target": ROOT / "content/posts/buddha/ahan/zhong-ahan",
        "total_juan": 60,
        "weight": 20,
        "summary": "中阿含经六十卷。",
        "removable_bylines": {"東晉罽賓三藏瞿曇僧伽提婆譯"},
        "drop_sutra_colophons": True,
    },
    "za-ahan": {
        "work": "T0099",
        "source_title": "雜阿含經",
        "display_title": "杂阿含经",
        "tag": "杂阿含经",
        "slug": "za-ahan",
        "target": ROOT / "content/posts/buddha/ahan/za-ahan",
        "total_juan": 50,
        "weight": 30,
        "summary": "杂阿含经五十卷。",
        "removable_bylines": {"宋天竺三藏求那跋陀羅譯"},
    },
    "zeng-yi-ahan": {
        "work": "T0125",
        "source_title": "增壹阿含經",
        "display_title": "增壹阿含经",
        "tag": "增壹阿含经",
        "slug": "zeng-yi-ahan",
        "target": ROOT / "content/posts/buddha/ahan/zeng-yi-ahan",
        "total_juan": 51,
        "weight": 40,
        "summary": "增壹阿含经五十一卷。",
        "removable_bylines": {
            "東晉賓三藏瞿曇僧伽提婆譯",
            "東晉罽賓三藏瞿曇僧伽提婆譯",
        },
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def title_pattern(source_title: str) -> re.Pattern[str]:
    return re.compile(
        rf"^(?:佛說)?{re.escape(source_title)}卷第[零一二三四五六七八九十百]+"
    )


def collection_path(config: dict, juan: int) -> Path:
    if config["total_juan"] <= 30:
        return config["target"]
    start = ((juan - 1) // 30) * 30 + 1
    end = min(start + 29, config["total_juan"])
    return config["target"] / f"{start:03d}-{end:03d}"


def fetch_blocks(config: dict, juan: int):
    raw = fetch_text(API_URL.format(work=config["work"], juan=juan))
    data = json.loads(raw)
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"{config['display_title']} 卷{juan} API 返回为空")

    parser = CbetaJuanParser()
    parser.feed(html.unescape(results[0]))
    if not parser.blocks:
        raise RuntimeError(f"{config['display_title']} 卷{juan} 未解析到正文段落")
    return drop_repeated_title_and_byline(config, parser.blocks)


def drop_repeated_title_and_byline(config: dict, blocks):
    cleaned = []
    title_re = title_pattern(config["source_title"])
    removable_bylines = {normalize_text(item) for item in config["removable_bylines"]}
    sutra_colophon_re = re.compile(
        r"^.+經第[零一二三四五六七八九十百]+竟"
        r"[零一二三四五六七八九十百千萬]+字$"
    )

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and title_re.match(normalized):
            continue
        if block_type == "byline" and normalized in removable_bylines:
            continue
        if (
            config.get("drop_sutra_colophons")
            and block_type == "paragraph"
            and sutra_colophon_re.fullmatch(normalized)
        ):
            continue
        cleaned.append((block_type, level, text))
    return cleaned


def write_collection_index(config: dict) -> None:
    target = config["target"]
    target.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "---",
            f'title: "{config["display_title"]}"',
            "date: 2026-05-15",
            f'tags: ["{config["tag"]}"]',
            'categories: ["佛学"]',
            "draft: false",
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


def write_range_indexes(config: dict) -> None:
    if config["total_juan"] <= 30:
        return

    for start in range(1, config["total_juan"] + 1, 30):
        end = min(start + 29, config["total_juan"])
        target = config["target"] / f"{start:03d}-{end:03d}"
        target.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            [
                "---",
                f'title: "{config["display_title"]} 卷第{chinese_number(start)}至卷第{chinese_number(end)}"',
                "date: 2026-05-15",
                f'tags: ["{config["tag"]}"]',
                'categories: ["佛学"]',
                "draft: false",
                f'summary: "{config["display_title"]}卷第{chinese_number(start)}至卷第{chinese_number(end)}"',
                "showToc: false",
                "tocOpen: false",
                "ShowShareButtons: false",
                f"weight: {start}",
                "---",
                "",
            ]
        )
        (target / "_index.md").write_text(content, encoding="utf-8")


def front_matter(config: dict, juan: int) -> list[str]:
    cn = chinese_number(juan)
    return [
        "---",
        f'title: "{config["display_title"]} 卷第{cn}"',
        "date: 2026-05-15",
        f'tags: ["{config["tag"]}"]',
        'categories: ["佛学"]',
        "draft: false",
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
    target = collection_path(config, juan)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{config['slug']}-{juan:03d}.md"
    path.write_text(render_markdown(config, juan, blocks), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=sorted(COLLECTIONS), default="chang-ahan")
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    config = COLLECTIONS[args.collection]
    start = args.start or 1
    end = args.end or config["total_juan"]
    if start < 1 or end > config["total_juan"] or start > end:
        raise SystemExit(f"卷号范围必须在 1..{config['total_juan']} 内")

    write_collection_index(config)
    write_range_indexes(config)

    juans = list(range(start, end + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(write_juan, config, juan): juan for juan in juans}
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            juan = future_map[future]
            path = future.result()
            print(f"[{completed:03d}/{len(juans):03d}] {config['display_title']} 卷{juan:03d} -> {path}")


if __name__ == "__main__":
    main()
