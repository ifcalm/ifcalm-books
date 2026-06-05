#!/usr/bin/env python3
"""Generate high-frequency Chinese Buddhist reading texts from CBETA."""

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
BUDDHA_ROOT = ROOT / "content/posts/buddha"
DATE = "2026-06-05"


GROUPS = {
    "zongpai": {
        "title": "宗派典籍",
        "summary": "中国佛教宗派与祖师著述。",
        "intro": "收录中国佛教宗派与祖师著述。",
        "tag": "佛学",
        "weight": 40,
    },
    "zongpai/chan": {
        "title": "禅宗部",
        "summary": "禅宗典籍与修心法要。",
        "intro": "收录禅宗典籍与修心法要。",
        "tag": "佛学",
        "weight": 10,
    },
    "zongpai/chan/yongming": {
        "title": "永明延寿系",
        "summary": "永明延寿禅师相关著述。",
        "intro": "收录永明延寿禅师相关著述。",
        "tag": "佛学",
        "weight": 20,
    },
}


COLLECTIONS = {
    "liu-zu-da-shi-fa-bao-tan-jing": {
        "work": "T2008",
        "display_title": "六祖坛经",
        "tag": "六祖坛经",
        "slug": "liu-zu-da-shi-fa-bao-tan-jing",
        "target": "zongpai/chan/liu-zu-da-shi-fa-bao-tan-jing",
        "total_juan": 1,
        "weight": 10,
        "summary": "六祖大师法宝坛经一卷。",
        "expected_category": "禪宗部類",
        "removable_title_patterns": [
            r"^六祖大師法寶壇經$",
            r"^六祖大師法寶壇經終$",
            r"^附錄終$",
        ],
        "removable_bylines": {"風旛報恩光孝禪寺住持嗣祖比丘宗寶編"},
        "drop_initial_until": "目錄終",
    },
    "wan-shan-tong-gui-ji": {
        "work": "T2017",
        "display_title": "万善同归集",
        "tag": "万善同归集",
        "slug": "wan-shan-tong-gui-ji",
        "target": "zongpai/chan/yongming/wan-shan-tong-gui-ji",
        "total_juan": 3,
        "weight": 10,
        "summary": "万善同归集三卷。",
        "expected_category": "禪宗部類",
        "removable_title_patterns": [r"^萬善同歸集卷[上中下]$"],
        "removable_bylines": {"杭州慧日永明寺智覺禪師延壽述"},
    },
    "yong-ming-zhi-jue-chan-shi-wei-xin-jue": {
        "work": "T2018",
        "display_title": "永明智觉禅师唯心诀",
        "tag": "唯心诀",
        "slug": "yong-ming-zhi-jue-chan-shi-wei-xin-jue",
        "target": "zongpai/chan/yongming/yong-ming-zhi-jue-chan-shi-wei-xin-jue",
        "total_juan": 1,
        "weight": 20,
        "summary": "永明智觉禅师唯心诀一卷。",
        "expected_category": "禪宗部類",
        "removable_title_patterns": [
            r"^永明智覺禪師唯心訣$",
            r"^永明智覺禪師唯心訣終$",
        ],
        "removable_bylines": set(),
    },
    "gao-li-guo-pu-zhao-chan-shi-xiu-xin-jue": {
        "work": "T2020",
        "display_title": "高丽国普照禅师修心诀",
        "tag": "修心诀",
        "slug": "gao-li-guo-pu-zhao-chan-shi-xiu-xin-jue",
        "target": "zongpai/chan/gao-li-guo-pu-zhao-chan-shi-xiu-xin-jue",
        "total_juan": 1,
        "weight": 30,
        "summary": "高丽国普照禅师修心诀一卷。",
        "expected_category": "禪宗部類",
        "removable_title_patterns": [r"^高麗國普照禪師修心訣$"],
        "removable_bylines": set(),
    },
    "zhao-lun": {
        "work": "T1858",
        "display_title": "肇论",
        "tag": "肇论",
        "slug": "zhao-lun",
        "target": "lunzang/zhongguan/zhao-lun",
        "total_juan": 1,
        "weight": 40,
        "summary": "肇论一卷。",
        "expected_category": "中觀部類",
        "removable_title_patterns": [
            r"^肇論$",
            r"^肇論終$",
            r"^物不遷論終$",
            r"^不真空論終$",
            r"^般若無知論終$",
            r"^涅槃無名論終$",
        ],
        "removable_bylines": {"後秦長安釋僧肇作"},
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def target_path(config: dict) -> Path:
    return BUDDHA_ROOT / config["target"]


def drop_initial_catalog(config: dict, blocks):
    marker = config.get("drop_initial_until")
    if not marker or not blocks:
        return blocks
    marker_normalized = normalize_text(marker)
    if marker_normalized not in {normalize_text(block[2]) for block in blocks[:8]}:
        return blocks
    for index, block in enumerate(blocks):
        if normalize_text(block[2]) == marker_normalized:
            return blocks[index + 1 :]
    return blocks


def drop_repeated_title_and_byline(config: dict, blocks):
    cleaned = []
    title_patterns = [re.compile(pattern) for pattern in config["removable_title_patterns"]]
    removable_bylines = {normalize_text(item) for item in config["removable_bylines"]}

    for block_type, level, text in drop_initial_catalog(config, blocks):
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


def write_group_indexes() -> None:
    for rel_target, config in GROUPS.items():
        target = BUDDHA_ROOT / rel_target
        target.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            [
                "---",
                f'title: "{config["title"]}"',
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
                config["intro"],
                "",
            ]
        )
        (target / "_index.md").write_text(content, encoding="utf-8")


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

    write_group_indexes()
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
