#!/usr/bin/env python3
"""Generate the core Baoji pure-land group from CBETA's stable juan endpoint."""

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
    "slug": "jingtu",
    "title": "净土经组",
    "summary": "宝积部中无量寿、阿弥陀及观经相关经典。",
    "intro": "收录宝积部中无量寿、阿弥陀及观经相关经典。",
    "weight": 30,
}

COLLECTIONS = {
    "fo-shuo-wu-liang-shou-jing": {
        "work": "T0360",
        "display_title": "佛说无量寿经",
        "tag": "佛说无量寿经",
        "slug": "fo-shuo-wu-liang-shou-jing",
        "total_juan": 2,
        "weight": 10,
        "summary": "佛说无量寿经二卷。",
        "removable_title_patterns": [r"^佛說無量壽經卷(?:上|下)$"],
        "removable_bylines": {"曹魏天竺三藏康僧鎧譯"},
    },
    "fo-shuo-wu-liang-qing-jing-ping-deng-jue-jing": {
        "work": "T0361",
        "display_title": "佛说无量清净平等觉经",
        "tag": "佛说无量清净平等觉经",
        "slug": "fo-shuo-wu-liang-qing-jing-ping-deng-jue-jing",
        "total_juan": 4,
        "weight": 20,
        "summary": "佛说无量清净平等觉经四卷。",
        "removable_title_patterns": [
            r"^佛說無量清淨平等覺經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {
            "後漢月支國三藏支婁迦讖譯",
            "後漢月氏國三藏支婁迦讖譯",
        },
    },
    "fo-shuo-a-mi-tuo-san-ye-san-fo-sa-lou-fo-tan-guo-du-ren-dao-jing": {
        "work": "T0362",
        "display_title": "佛说阿弥陀三耶三佛萨楼佛檀过度人道经",
        "tag": "佛说阿弥陀三耶三佛萨楼佛檀过度人道经",
        "slug": "fo-shuo-a-mi-tuo-san-ye-san-fo-sa-lou-fo-tan-guo-du-ren-dao-jing",
        "total_juan": 2,
        "weight": 30,
        "summary": "佛说阿弥陀三耶三佛萨楼佛檀过度人道经二卷。",
        "removable_title_patterns": [
            r"^佛說阿彌陀三耶三佛薩樓佛檀過度人道經卷上$",
            r"^佛說阿彌陀經卷下$",
        ],
        "removable_bylines": {"吳月支國居士支謙譯"},
    },
    "fo-shuo-da-cheng-wu-liang-shou-zhuang-yan-jing": {
        "work": "T0363",
        "display_title": "佛说大乘无量寿庄严经",
        "tag": "佛说大乘无量寿庄严经",
        "slug": "fo-shuo-da-cheng-wu-liang-shou-zhuang-yan-jing",
        "total_juan": 3,
        "weight": 40,
        "summary": "佛说大乘无量寿庄严经三卷。",
        "removable_title_patterns": [
            r"^佛說大乘無量壽莊嚴經卷(?:上|中|下)$"
        ],
        "removable_bylines": {
            "西天譯經三藏朝散大夫試光祿卿明教大師臣法賢奉詔譯"
        },
    },
    "fo-shuo-da-a-mi-tuo-jing": {
        "work": "T0364",
        "display_title": "佛说大阿弥陀经",
        "tag": "佛说大阿弥陀经",
        "slug": "fo-shuo-da-a-mi-tuo-jing",
        "total_juan": 2,
        "weight": 50,
        "summary": "佛说大阿弥陀经二卷。",
        "removable_title_patterns": [r"^佛說大阿彌陀經卷(?:上|下)$"],
        "removable_bylines": {"國學進士龍舒王日休校輯"},
    },
    "fo-shuo-guan-wu-liang-shou-fo-jing": {
        "work": "T0365",
        "display_title": "佛说观无量寿佛经",
        "tag": "佛说观无量寿佛经",
        "slug": "fo-shuo-guan-wu-liang-shou-fo-jing",
        "total_juan": 1,
        "weight": 60,
        "summary": "佛说观无量寿佛经一卷。",
        "removable_titles": {"佛說觀無量壽佛經"},
        "removable_bylines": {"宋西域三藏畺良耶舍譯"},
    },
    "fo-shuo-a-mi-tuo-jing": {
        "work": "T0366",
        "display_title": "佛说阿弥陀经",
        "tag": "佛说阿弥陀经",
        "slug": "fo-shuo-a-mi-tuo-jing",
        "total_juan": 1,
        "weight": 70,
        "summary": "佛说阿弥陀经一卷。",
        "removable_titles": {"佛說阿彌陀經"},
        "removable_bylines": {"姚秦龜茲三藏鳩摩羅什譯"},
    },
    "cheng-zan-jing-tu-fo-she-shou-jing": {
        "work": "T0367",
        "display_title": "称赞净土佛摄受经",
        "tag": "称赞净土佛摄受经",
        "slug": "cheng-zan-jing-tu-fo-she-shou-jing",
        "total_juan": 1,
        "weight": 80,
        "summary": "称赞净土佛摄受经一卷。",
        "removable_titles": {"稱讚淨土佛攝受經"},
        "removable_bylines": {"大唐三藏法師玄奘奉詔譯"},
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
