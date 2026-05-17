#!/usr/bin/env python3
"""Generate curated Baoji alternate translations / independent recensions from CBETA."""

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
BAOJI_ROOT = ROOT / "content/posts/buddha/jingzang/baoji"

GROUP = {
    "slug": "yiyi",
    "title": "异译别行",
    "summary": "与《大宝积经》诸会互参的异译、别行经典。",
    "intro": "收录与《大宝积经》诸会互参的异译、别行经典。",
    "weight": 20,
}

COLLECTIONS = {
    "da-fang-guang-san-jie-jing": {
        "work": "T0311",
        "display_title": "大方广三戒经",
        "tag": "大方广三戒经",
        "slug": "da-fang-guang-san-jie-jing",
        "total_juan": 3,
        "weight": 10,
        "summary": "大方广三戒经三卷。",
        "removable_title_patterns": [r"^大方廣三戒經卷(?:上|中|下)$"],
        "removable_bylines": {"北涼天竺三藏曇無讖譯"},
    },
    "a-chu-fo-guo-jing": {
        "work": "T0313",
        "display_title": "阿閦佛国经",
        "tag": "阿閦佛国经",
        "slug": "a-chu-fo-guo-jing",
        "total_juan": 2,
        "weight": 20,
        "summary": "阿閦佛国经二卷。",
        "removable_title_patterns": [r"^阿閦佛國經卷(?:上|下)$"],
        "removable_bylines": {"後漢月支國三藏支婁迦讖譯"},
    },
    "wen-shu-shi-li-fo-tu-yan-jing-jing": {
        "work": "T0318",
        "display_title": "文殊师利佛土严净经",
        "tag": "文殊师利佛土严净经",
        "slug": "wen-shu-shi-li-fo-tu-yan-jing-jing",
        "total_juan": 2,
        "weight": 30,
        "summary": "文殊师利佛土严净经二卷。",
        "removable_title_patterns": [r"^文殊師利佛土嚴淨經卷(?:上|下)$"],
        "removable_bylines": {"西晉月氏國三藏竺法護譯"},
    },
    "sheng-shan-zhu-yi-tian-zi-suo-wen-jing": {
        "work": "T0341",
        "display_title": "圣善住意天子所问经",
        "tag": "圣善住意天子所问经",
        "slug": "sheng-shan-zhu-yi-tian-zi-suo-wen-jing",
        "total_juan": 3,
        "weight": 40,
        "summary": "圣善住意天子所问经三卷。",
        "removable_title_patterns": [r"^聖善住意天子所問經卷(?:上|中|下)$"],
        "removable_bylines": {"元魏三藏毘目智仙共般若流支譯"},
    },
    "fo-shuo-ru-huan-san-mei-jing": {
        "work": "T0342",
        "display_title": "佛说如幻三昧经",
        "tag": "佛说如幻三昧经",
        "slug": "fo-shuo-ru-huan-san-mei-jing",
        "total_juan": 2,
        "weight": 50,
        "summary": "佛说如幻三昧经二卷。",
        "removable_title_patterns": [r"^佛說如幻三昧經卷(?:上|下)$"],
        "removable_bylines": {"西晉月氏國三藏竺法護譯"},
    },
    "hui-shang-pu-sa-wen-da-shan-quan-jing": {
        "work": "T0345",
        "display_title": "慧上菩萨问大善权经",
        "tag": "慧上菩萨问大善权经",
        "slug": "hui-shang-pu-sa-wen-da-shan-quan-jing",
        "total_juan": 2,
        "weight": 60,
        "summary": "慧上菩萨问大善权经二卷。",
        "removable_title_patterns": [r"^慧上菩薩問大善權經卷(?:上|下)$"],
        "removable_bylines": {"西晉月氏國三藏竺法護譯"},
    },
    "fo-shuo-da-fang-guang-shan-qiao-fang-bian-jing": {
        "work": "T0346",
        "display_title": "佛说大方广善巧方便经",
        "tag": "佛说大方广善巧方便经",
        "slug": "fo-shuo-da-fang-guang-shan-qiao-fang-bian-jing",
        "total_juan": 4,
        "weight": 70,
        "summary": "佛说大方广善巧方便经四卷。",
        "removable_title_patterns": [
            r"^佛說大方廣善巧方便經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {
            "西天譯經三藏朝奉大夫試光祿卿傳法大師賜紫臣施護奉詔譯"
        },
    },
    "fo-shuo-da-jia-ye-wen-da-bao-ji-zheng-fa-jing": {
        "work": "T0352",
        "display_title": "佛说大迦叶问大宝积正法经",
        "tag": "佛说大迦叶问大宝积正法经",
        "slug": "fo-shuo-da-jia-ye-wen-da-bao-ji-zheng-fa-jing",
        "total_juan": 5,
        "weight": 80,
        "summary": "佛说大迦叶问大宝积正法经五卷。",
        "removable_title_patterns": [
            r"^佛說大迦葉問大寶積正法經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {
            "西天譯經三藏朝散大夫試鴻臚少卿傳法大師臣施護奉詔譯"
        },
    },
    "sheng-man-shi-zi-hou-yi-cheng-da-fang-bian-fang-guang-jing": {
        "work": "T0353",
        "display_title": "胜鬘师子吼一乘大方便方广经",
        "tag": "胜鬘师子吼一乘大方便方广经",
        "slug": "sheng-man-shi-zi-hou-yi-cheng-da-fang-bian-fang-guang-jing",
        "total_juan": 1,
        "weight": 90,
        "summary": "胜鬘师子吼一乘大方便方广经一卷。",
        "removable_titles": {"勝鬘師子吼一乘大方便方廣經"},
        "removable_bylines": {"宋中印度三藏求那跋陀羅譯"},
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def collection_target(config: dict) -> Path:
    return BAOJI_ROOT / GROUP["slug"] / config["slug"]


def drop_repeated_title_and_byline(config: dict, blocks):
    cleaned = []
    removable_titles = {normalize_text(item) for item in config.get("removable_titles", set())}
    removable_title_res = [re.compile(pattern) for pattern in config.get("removable_title_patterns", [])]
    removable_bylines = {normalize_text(item) for item in config["removable_bylines"]}

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and (
            normalized in removable_titles
            or any(regex.fullmatch(normalized) for regex in removable_title_res)
        ):
            continue
        if block_type == "byline" and normalized in removable_bylines:
            continue
        cleaned.append((block_type, level, text))
    return cleaned


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


def write_group_index() -> None:
    target = BAOJI_ROOT / GROUP["slug"]
    target.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "---",
            f'title: "{GROUP["title"]}"',
            "date: 2026-05-17",
            'tags: ["佛学"]',
            "draft: false",
            f'summary: "{GROUP["summary"]}"',
            "showToc: false",
            "tocOpen: false",
            "ShowShareButtons: false",
            f'weight: {GROUP["weight"]}',
            "---",
            "",
            GROUP["intro"],
            "",
        ]
    )
    (target / "_index.md").write_text(content, encoding="utf-8")


def write_collection_index(config: dict) -> None:
    target = collection_target(config)
    target.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "---",
            f'title: "{config["display_title"]}"',
            "date: 2026-05-17",
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
        "date: 2026-05-17",
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
    target = collection_target(config)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{config['slug']}-{juan:03d}.md"
    path.write_text(render_markdown(config, juan, blocks), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=sorted(COLLECTIONS))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    if not args.collection and not args.all:
        raise SystemExit("请指定 --collection 或 --all")
    if args.collection and args.all:
        raise SystemExit("--collection 与 --all 不能同时使用")

    write_group_index()
    configs = COLLECTIONS.values() if args.all else [COLLECTIONS[args.collection]]

    for config in configs:
        start = args.start or 1
        end = args.end or config["total_juan"]
        if start < 1 or end > config["total_juan"] or start > end:
            raise SystemExit(f"{config['display_title']} 卷号范围必须在 1..{config['total_juan']} 内")

        write_collection_index(config)
        juans = list(range(start, end + 1))
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_map = {executor.submit(write_juan, config, juan): juan for juan in juans}
            for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
                juan = future_map[future]
                path = future.result()
                print(
                    f"[{completed:03d}/{len(juans):03d}] "
                    f"{config['display_title']} 卷{juan:03d} -> {path}"
                )


if __name__ == "__main__":
    main()
