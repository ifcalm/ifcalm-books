#!/usr/bin/env python3
"""Generate curated Daji supplementary groups from CBETA's stable juan endpoint."""

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
DAJI_ROOT = ROOT / "content/posts/buddha/jingzang/daji"

GROUPS = {
    "dizang": {
        "title": "地藏系",
        "summary": "大集部中地藏相关经典。",
        "intro": "收录大集部中地藏相关经典。",
        "weight": 20,
    },
    "nianfo": {
        "title": "念佛般舟系",
        "summary": "大集部中念佛三昧、般舟三昧相关经典。",
        "intro": "收录大集部中念佛三昧、般舟三昧相关经典。",
        "weight": 30,
    },
}

COLLECTIONS = {
    "da-fang-guang-shi-lun-jing": {
        "work": "T0410",
        "display_title": "大方广十轮经",
        "tag": "大方广十轮经",
        "slug": "da-fang-guang-shi-lun-jing",
        "group": "dizang",
        "total_juan": 8,
        "weight": 10,
        "summary": "大方广十轮经八卷。",
        "removable_title_patterns": [
            r"^大方廣十輪經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {"失譯人名今附北涼錄"},
    },
    "da-cheng-da-ji-di-zang-shi-lun-jing": {
        "work": "T0411",
        "display_title": "大乘大集地藏十轮经",
        "tag": "大乘大集地藏十轮经",
        "slug": "da-cheng-da-ji-di-zang-shi-lun-jing",
        "group": "dizang",
        "total_juan": 10,
        "weight": 20,
        "summary": "大乘大集地藏十轮经十卷。",
        "removable_title_patterns": [
            r"^大乘大集地藏十輪經卷第[零一二三四五六七八九十百]+$"
        ],
        "paragraph_to_head": {"大乘大集地藏十輪經序品第一": "序品第一"},
        "removable_bylines": {"三藏法師玄奘奉詔譯"},
    },
    "di-zang-pu-sa-ben-yuan-jing": {
        "work": "T0412",
        "display_title": "地藏菩萨本愿经",
        "tag": "地藏菩萨本愿经",
        "slug": "di-zang-pu-sa-ben-yuan-jing",
        "group": "dizang",
        "total_juan": 2,
        "weight": 30,
        "summary": "地藏菩萨本愿经二卷。",
        "removable_title_patterns": [r"^地藏菩薩本願經卷(?:上|下)$"],
        "removable_bylines": {"唐于闐國三藏沙門實叉難陀譯"},
    },
    "bai-qian-song-da-ji-jing-di-zang-pu-sa-qing-wen-fa-shen-zan": {
        "work": "T0413",
        "display_title": "百千颂大集经地藏菩萨请问法身赞",
        "tag": "百千颂大集经地藏菩萨请问法身赞",
        "slug": "bai-qian-song-da-ji-jing-di-zang-pu-sa-qing-wen-fa-shen-zan",
        "group": "dizang",
        "total_juan": 1,
        "weight": 40,
        "summary": "百千颂大集经地藏菩萨请问法身赞一卷。",
        "removable_titles": {
            "百千頌大集經地藏菩薩請問法身讚",
            "百千誦大集經地藏菩薩請問法身讚",
        },
        "removable_bylines": {
            "開府儀同三司特進試鴻臚卿肅國公食邑三千戶賜紫贈司空謚大鑒正號大廣智大興善寺三藏沙門不空奉詔譯"
        },
    },
    "pu-sa-nian-fo-san-mei-jing": {
        "work": "T0414",
        "display_title": "菩萨念佛三昧经",
        "tag": "菩萨念佛三昧经",
        "slug": "pu-sa-nian-fo-san-mei-jing",
        "group": "nianfo",
        "total_juan": 5,
        "weight": 10,
        "summary": "菩萨念佛三昧经五卷。",
        "removable_title_patterns": [
            r"^菩薩念佛三昧經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {"宋天竺三藏功德直譯"},
    },
    "da-fang-deng-da-ji-jing-pu-sa-nian-fo-san-mei-fen": {
        "work": "T0415",
        "display_title": "大方等大集经菩萨念佛三昧分",
        "tag": "大方等大集经菩萨念佛三昧分",
        "slug": "da-fang-deng-da-ji-jing-pu-sa-nian-fo-san-mei-fen",
        "group": "nianfo",
        "total_juan": 10,
        "weight": 20,
        "summary": "大方等大集经菩萨念佛三昧分十卷。",
        "removable_title_patterns": [
            r"^大方等大集經菩薩念佛三昧分卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {"隋天竺三藏達磨笈多譯"},
    },
    "da-fang-deng-da-ji-jing-xian-hu-fen": {
        "work": "T0416",
        "display_title": "大方等大集经贤护分",
        "tag": "大方等大集经贤护分",
        "slug": "da-fang-deng-da-ji-jing-xian-hu-fen",
        "group": "nianfo",
        "total_juan": 5,
        "weight": 30,
        "summary": "大方等大集经贤护分五卷。",
        "removable_title_patterns": [
            r"^(?:大方等大集經|大乘大集經)賢護分卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {"隋天竺三藏闍那崛多譯"},
    },
    "fo-shuo-ban-zhou-san-mei-jing": {
        "work": "T0417",
        "display_title": "佛说般舟三昧经",
        "tag": "佛说般舟三昧经",
        "slug": "fo-shuo-ban-zhou-san-mei-jing",
        "group": "nianfo",
        "total_juan": 1,
        "weight": 40,
        "summary": "佛说般舟三昧经一卷。",
        "removable_titles": {"佛說般舟三昧經"},
        "removable_bylines": {"後漢月支三藏支婁迦讖譯"},
    },
    "ban-zhou-san-mei-jing": {
        "work": "T0418",
        "display_title": "般舟三昧经",
        "tag": "般舟三昧经",
        "slug": "ban-zhou-san-mei-jing",
        "group": "nianfo",
        "total_juan": 3,
        "weight": 50,
        "summary": "般舟三昧经三卷。",
        "removable_title_patterns": [
            r"^般舟三昧經卷(?:上|中|下)(?:一名十方現在佛悉在前立定經)?$"
        ],
        "removable_bylines": {"後漢月氏三藏支婁迦讖譯"},
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def collection_target(config: dict) -> Path:
    return DAJI_ROOT / config["group"] / config["slug"]


def drop_repeated_title_and_byline(config: dict, blocks):
    cleaned = []
    removable_titles = {normalize_text(item) for item in config.get("removable_titles", set())}
    removable_title_res = [re.compile(pattern) for pattern in config.get("removable_title_patterns", [])]
    removable_bylines = {normalize_text(item) for item in config["removable_bylines"]}
    paragraph_to_head = {
        normalize_text(src): dst for src, dst in config.get("paragraph_to_head", {}).items()
    }

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and normalized in paragraph_to_head:
            cleaned.append(("head", "1", paragraph_to_head[normalized]))
            continue
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


def write_group_index(group_key: str) -> None:
    config = GROUPS[group_key]
    target = DAJI_ROOT / group_key
    target.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "---",
            f'title: "{config["title"]}"',
            "date: 2026-05-18",
            'tags: ["佛学"]',
            "draft: false",
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
    target = collection_target(config)
    target.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "---",
            f'title: "{config["display_title"]}"',
            "date: 2026-05-18",
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
        "date: 2026-05-18",
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

    configs = COLLECTIONS.values() if args.all else [COLLECTIONS[args.collection]]
    for config in configs:
        write_group_index(config["group"])
        write_collection_index(config)

        start = args.start or 1
        end = args.end or config["total_juan"]
        if start < 1 or end > config["total_juan"] or start > end:
            raise SystemExit(f"{config['display_title']} 卷号范围必须在 1..{config['total_juan']} 内")

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
