#!/usr/bin/env python3
"""Generate the first Benyuan collections from CBETA's stable juan endpoint."""

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
BENYUAN_ROOT = ROOT / "content/posts/buddha/jingzang/benyuan"
DATE = "2026-06-02"


COLLECTIONS = {
    "xiu-xing-ben-qi-jing": {
        "work": "T0184",
        "display_title": "修行本起经",
        "source_title": "修行本起經",
        "tag": "修行本起经",
        "slug": "xiu-xing-ben-qi-jing",
        "total_juan": 2,
        "weight": 10,
        "summary": "修行本起经二卷。",
        "removable_title_patterns": [r"^修行本起經卷[上下]$"],
        "removable_bylines": {"後漢西域三藏竺大力共康孟詳譯"},
    },
    "tai-zi-rui-ying-ben-qi-jing": {
        "work": "T0185",
        "display_title": "太子瑞应本起经",
        "source_title": "太子瑞應本起經",
        "tag": "太子瑞应本起经",
        "slug": "tai-zi-rui-ying-ben-qi-jing",
        "total_juan": 2,
        "weight": 20,
        "summary": "太子瑞应本起经二卷。",
        "removable_title_patterns": [r"^佛說太子瑞應本起經卷[上下]$"],
        "removable_bylines": {"吳月支優婆塞支謙譯"},
    },
    "pu-yao-jing": {
        "work": "T0186",
        "display_title": "普曜经",
        "source_title": "普曜經",
        "tag": "普曜经",
        "slug": "pu-yao-jing",
        "total_juan": 8,
        "weight": 30,
        "summary": "普曜经八卷。",
        "removable_title_patterns": [
            r"^佛說普曜經卷第[零一二三四五六七八九十百]+(?:一名方等本起)?$"
        ],
        "removable_bylines": {"西晉月氏三藏竺法護譯"},
    },
    "fang-guang-da-zhuang-yan-jing": {
        "work": "T0187",
        "display_title": "方广大庄严经",
        "source_title": "方廣大莊嚴經",
        "tag": "方广大庄严经",
        "slug": "fang-guang-da-zhuang-yan-jing",
        "total_juan": 12,
        "weight": 40,
        "summary": "方广大庄严经十二卷。",
        "removable_title_patterns": [
            r"^方廣大莊嚴經卷第[零一二三四五六七八九十百]+(?:一名神通遊戲)?$"
        ],
        "removable_bylines": {"大唐天竺三藏地婆訶羅奉詔譯"},
    },
    "guo-qu-xian-zai-yin-guo-jing": {
        "work": "T0189",
        "display_title": "过去现在因果经",
        "source_title": "過去現在因果經",
        "tag": "过去现在因果经",
        "slug": "guo-qu-xian-zai-yin-guo-jing",
        "total_juan": 4,
        "weight": 50,
        "summary": "过去现在因果经四卷。",
        "removable_title_patterns": [r"^過去現在因果經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"宋天竺三藏求那跋陀羅譯"},
    },
    "zhong-ben-qi-jing": {
        "work": "T0196",
        "display_title": "中本起经",
        "source_title": "中本起經",
        "tag": "中本起经",
        "slug": "zhong-ben-qi-jing",
        "total_juan": 2,
        "weight": 60,
        "summary": "中本起经二卷。",
        "removable_title_patterns": [r"^中本起經卷[上下](?:次名四部僧，出長阿含)?$"],
        "removable_bylines": {"後漢西域沙門曇果共康孟詳譯"},
    },
    "bai-yu-jing": {
        "work": "T0209",
        "display_title": "百喻经",
        "source_title": "百喻經",
        "tag": "百喻经",
        "slug": "bai-yu-jing",
        "total_juan": 4,
        "weight": 70,
        "summary": "百喻经四卷。",
        "removable_title_patterns": [r"^百喻經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"尊者僧伽斯那撰", "蕭齊天竺三藏求那毘地譯"},
        "drop_initial_catalog": True,
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def fetch_blocks(config: dict, juan: int):
    raw = fetch_text(API_URL.format(work=config["work"], juan=juan))
    data = json.loads(raw)
    work_info = data.get("work_info") or {}
    expected_juan = config["total_juan"]
    if int(work_info.get("juan") or 0) != expected_juan:
        raise RuntimeError(
            f"{config['display_title']} CBETA 卷数 "
            f"{work_info.get('juan')} != expected {expected_juan}"
        )

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
    title_patterns = [re.compile(pattern) for pattern in config["removable_title_patterns"]]
    removable_bylines = {normalize_text(item) for item in config["removable_bylines"]}
    first_head_seen = False

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and any(pattern.fullmatch(normalized) for pattern in title_patterns):
            continue
        if block_type == "byline" and normalized in removable_bylines:
            continue
        if block_type == "head":
            first_head_seen = True
        if (
            config.get("drop_initial_catalog")
            and not first_head_seen
            and block_type == "paragraph"
            and normalized.count("喻") >= 10
        ):
            continue
        cleaned.append((block_type, level, text))
    return cleaned


def write_collection_index(config: dict) -> None:
    target = BENYUAN_ROOT / config["slug"]
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
    target = BENYUAN_ROOT / config["slug"]
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
