#!/usr/bin/env python3
"""Generate Lotus-related sutra collections from CBETA's stable juan endpoint.

Main source: CBETA stable juan API.
Bibliographic/proofreading references used during collection setup:
- Lotus translations: T0262 / T0263 / T0264
- Companion sutras: T0276 / T0277
"""

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
    "miao-fa-lian-hua-jing": {
        "work": "T0262",
        "source_title": "妙法蓮華經",
        "display_title": "妙法莲华经",
        "tag": "妙法莲华经",
        "slug": "miao-fa-lian-hua-jing",
        "target": ROOT / "content/posts/buddha/jingzang/fahua/miao-fa-lian-hua-jing",
        "total_juan": 7,
        "weight": 10,
        "summary": "妙法莲华经七卷。",
        "removable_bylines": {"後秦龜茲國三藏法師鳩摩羅什奉詔譯"},
    },
    "wu-liang-yi-jing": {
        "work": "T0276",
        "source_title": "無量義經",
        "display_title": "无量义经",
        "tag": "无量义经",
        "slug": "wu-liang-yi-jing",
        "target": ROOT / "content/posts/buddha/jingzang/fahua/wu-liang-yi-jing",
        "total_juan": 1,
        "weight": 20,
        "summary": "无量义经一卷。",
        "removable_bylines": {"蕭齊天竺三藏曇摩伽陀耶舍譯"},
        "removable_titles": {"無量義經"},
    },
    "guan-pu-xian-pu-sa-xing-fa-jing": {
        "work": "T0277",
        "source_title": "佛說觀普賢菩薩行法經",
        "display_title": "佛说观普贤菩萨行法经",
        "tag": "佛说观普贤菩萨行法经",
        "slug": "guan-pu-xian-pu-sa-xing-fa-jing",
        "target": ROOT / "content/posts/buddha/jingzang/fahua/guan-pu-xian-pu-sa-xing-fa-jing",
        "total_juan": 1,
        "weight": 30,
        "summary": "佛说观普贤菩萨行法经一卷。",
        "removable_bylines": {"宋元嘉年曇無蜜多於楊州譯"},
        "removable_titles": {"佛說觀普賢菩薩行法經"},
    },
    "zheng-fa-hua-jing": {
        "work": "T0263",
        "source_title": "正法華經",
        "display_title": "正法华经",
        "tag": "正法华经",
        "slug": "zheng-fa-hua-jing",
        "target": ROOT / "content/posts/buddha/jingzang/fahua/zheng-fa-hua-jing",
        "total_juan": 10,
        "weight": 40,
        "summary": "正法华经十卷。",
        "removable_bylines": {"西晉月氏國三藏竺法護譯"},
    },
    "tian-pin-miao-fa-lian-hua-jing": {
        "work": "T0264",
        "source_title": "添品妙法蓮華經",
        "display_title": "添品妙法莲华经",
        "tag": "添品妙法莲华经",
        "slug": "tian-pin-miao-fa-lian-hua-jing",
        "target": ROOT / "content/posts/buddha/jingzang/fahua/tian-pin-miao-fa-lian-hua-jing",
        "total_juan": 7,
        "weight": 50,
        "summary": "添品妙法莲华经七卷。",
        "removable_bylines": {"隋天竺三藏闍那崛多共笈多譯"},
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def title_pattern(source_title: str) -> re.Pattern[str]:
    return re.compile(rf"^(?:佛說)?{re.escape(source_title)}卷第[零一二三四五六七八九十百]+$")


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
    removable_titles = {normalize_text(item) for item in config.get("removable_titles", set())}

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and (title_re.fullmatch(normalized) or normalized in removable_titles):
            continue
        if block_type == "byline" and normalized in removable_bylines:
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
    target = config["target"]
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{config['slug']}-{juan:03d}.md"
    path.write_text(render_markdown(config, juan, blocks), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=sorted(COLLECTIONS), default="miao-fa-lian-hua-jing")
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
    juans = list(range(start, end + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(write_juan, config, juan): juan for juan in juans}
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            juan = future_map[future]
            path = future.result()
            print(f"[{completed:03d}/{len(juans):03d}] {config['display_title']} 卷{juan:03d} -> {path}")


if __name__ == "__main__":
    main()
