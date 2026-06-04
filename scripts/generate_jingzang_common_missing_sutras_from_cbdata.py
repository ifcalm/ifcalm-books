#!/usr/bin/env python3
"""Generate common missing sutras from CBETA's stable juan endpoint."""

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
JINGZANG_ROOT = ROOT / "content/posts/buddha/jingzang"
DATE = "2026-06-04"


GROUPS = {
    "jingji/changsong": {
        "title": "常诵经",
        "summary": "经集部中长期流通、常被诵习的短篇经典。",
        "intro": "收录经集部中长期流通、常被诵习的短篇经典。",
        "tag": "佛学",
        "weight": 60,
    },
    "jingji/lengjia": {
        "title": "楞伽系",
        "summary": "经集部中楞伽经典的三种重要汉译。",
        "intro": "收录经集部中楞伽经典的三种重要汉译。",
        "tag": "佛学",
        "weight": 70,
    },
    "jingji/yujia": {
        "title": "瑜伽深密系",
        "summary": "经集部中瑜伽行派与深密教义相关经典。",
        "intro": "收录经集部中瑜伽行派与深密教义相关经典。",
        "tag": "佛学",
        "weight": 80,
    },
    "jingji/yuanjue": {
        "title": "圆觉系",
        "summary": "经集部中圆觉法门相关经典。",
        "intro": "收录经集部中圆觉法门相关经典。",
        "tag": "佛学",
        "weight": 90,
    },
}


COLLECTIONS = {
    "fo-yi-jiao-jing": {
        "work": "T0389",
        "display_title": "佛遗教经",
        "tag": "佛遗教经",
        "slug": "fo-yi-jiao-jing",
        "target": "niepan/fo-yi-jiao-jing",
        "total_juan": 1,
        "weight": 80,
        "summary": "佛垂般涅槃略说教诫经，又名佛遗教经，一卷。",
        "removable_title_patterns": [r"^佛垂般涅槃略說教誡經(?:亦名遺教經)?$"],
        "removable_bylines": {"後秦龜茲國三藏鳩摩羅什奉詔譯"},
    },
    "fo-shuo-ba-da-ren-jue-jing": {
        "work": "T0779",
        "display_title": "佛说八大人觉经",
        "tag": "佛说八大人觉经",
        "slug": "fo-shuo-ba-da-ren-jue-jing",
        "target": "jingji/changsong/fo-shuo-ba-da-ren-jue-jing",
        "total_juan": 1,
        "weight": 10,
        "summary": "佛说八大人觉经一卷。",
        "removable_title_patterns": [r"^佛說八大人覺經$"],
        "removable_bylines": {"後漢安息國三藏安世高譯"},
    },
    "da-fang-guang-yuan-jue-xiu-duo-luo-liao-yi-jing": {
        "work": "T0842",
        "display_title": "圆觉经",
        "tag": "圆觉经",
        "slug": "da-fang-guang-yuan-jue-xiu-duo-luo-liao-yi-jing",
        "target": "jingji/yuanjue/da-fang-guang-yuan-jue-xiu-duo-luo-liao-yi-jing",
        "total_juan": 1,
        "weight": 10,
        "summary": "大方广圆觉修多罗了义经一卷。",
        "removable_title_patterns": [r"^大方廣圓覺修多羅了義經$"],
        "removable_bylines": {"大唐、罽賓三藏佛陀多羅譯"},
    },
    "jie-shen-mi-jing": {
        "work": "T0676",
        "display_title": "解深密经",
        "tag": "解深密经",
        "slug": "jie-shen-mi-jing",
        "target": "jingji/yujia/jie-shen-mi-jing",
        "total_juan": 5,
        "weight": 10,
        "summary": "解深密经五卷。",
        "removable_title_patterns": [r"^解深密經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"大唐三藏法師玄奘奉詔譯"},
    },
    "leng-jia-a-ba-duo-luo-bao-jing": {
        "work": "T0670",
        "display_title": "楞伽阿跋多罗宝经",
        "tag": "楞伽阿跋多罗宝经",
        "slug": "leng-jia-a-ba-duo-luo-bao-jing",
        "target": "jingji/lengjia/leng-jia-a-ba-duo-luo-bao-jing",
        "total_juan": 4,
        "weight": 10,
        "summary": "楞伽阿跋多罗宝经四卷。",
        "removable_title_patterns": [r"^楞伽阿跋多羅寶經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"宋天竺三藏求那跋陀羅譯"},
    },
    "ru-leng-jia-jing": {
        "work": "T0671",
        "display_title": "入楞伽经",
        "tag": "入楞伽经",
        "slug": "ru-leng-jia-jing",
        "target": "jingji/lengjia/ru-leng-jia-jing",
        "total_juan": 10,
        "weight": 20,
        "summary": "入楞伽经十卷。",
        "removable_title_patterns": [r"^入楞伽經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"元魏天竺三藏菩提留支譯"},
    },
    "da-cheng-ru-leng-jia-jing": {
        "work": "T0672",
        "display_title": "大乘入楞伽经",
        "tag": "大乘入楞伽经",
        "slug": "da-cheng-ru-leng-jia-jing",
        "target": "jingji/lengjia/da-cheng-ru-leng-jia-jing",
        "total_juan": 7,
        "weight": 30,
        "summary": "大乘入楞伽经七卷。",
        "removable_title_patterns": [r"^大乘入楞伽經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"大周于闐國三藏法師實叉難陀奉勅譯"},
    },
    "fa-ju-jing": {
        "work": "T0210",
        "display_title": "法句经",
        "tag": "法句经",
        "slug": "fa-ju-jing",
        "target": "benyuan/fa-ju-jing",
        "total_juan": 2,
        "weight": 80,
        "summary": "法句经二卷。",
        "removable_title_patterns": [r"^法句經卷[上下]$"],
        "removable_bylines": {"尊者法救撰", "吳天竺沙門維祇難等譯"},
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def target_path(config: dict) -> Path:
    return JINGZANG_ROOT / config["target"]


def fetch_blocks(config: dict, juan: int):
    raw = fetch_text(API_URL.format(work=config["work"], juan=juan))
    data = json.loads(raw)
    work_info = data.get("work_info") or {}
    if int(work_info.get("juan") or 0) != config["total_juan"]:
        raise RuntimeError(
            f"{config['display_title']} CBETA 卷数 "
            f"{work_info.get('juan')} != expected {config['total_juan']}"
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

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and any(pattern.fullmatch(normalized) for pattern in title_patterns):
            continue
        if block_type == "byline" and normalized in removable_bylines:
            continue
        cleaned.append((block_type, level, text))
    return cleaned


def write_group_indexes() -> None:
    for rel_target, config in GROUPS.items():
        target = JINGZANG_ROOT / rel_target
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
