#!/usr/bin/env python3
"""Generate core Huayan supplementary texts from CBETA's stable juan endpoint."""

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
HUAYAN_ROOT = ROOT / "content/posts/buddha/jingzang/huayan"

GROUPS = {
    "jingxing": {
        "title": "净行系",
        "summary": "华严净行相关别译经典。",
        "intro": "收录华严净行相关别译经典。",
        "weight": 40,
    },
    "shidi": {
        "title": "十地系",
        "summary": "华严十地相关别译经典。",
        "intro": "收录华严十地相关别译经典。",
        "weight": 50,
    },
    "rufajie": {
        "title": "入法界系",
        "summary": "华严入法界相关别译经典。",
        "intro": "收录华严入法界相关别译经典。",
        "weight": 60,
    },
    "xingyuan": {
        "title": "行愿系",
        "summary": "华严普贤行愿相关经典。",
        "intro": "收录华严普贤行愿相关经典。",
        "weight": 70,
    },
}

COLLECTIONS = {
    "fo-shuo-pu-sa-ben-ye-jing": {
        "work": "T0281",
        "display_title": "佛说菩萨本业经",
        "tag": "佛说菩萨本业经",
        "slug": "fo-shuo-pu-sa-ben-ye-jing",
        "group": "jingxing",
        "total_juan": 1,
        "weight": 10,
        "summary": "佛说菩萨本业经一卷。",
        "removable_titles": {"佛說菩薩本業經一卷"},
        "removable_bylines": {"吳月氏優婆塞支謙譯"},
    },
    "zhu-pu-sa-qiu-fo-ben-ye-jing": {
        "work": "T0282",
        "display_title": "诸菩萨求佛本业经",
        "tag": "诸菩萨求佛本业经",
        "slug": "zhu-pu-sa-qiu-fo-ben-ye-jing",
        "group": "jingxing",
        "total_juan": 1,
        "weight": 20,
        "summary": "诸菩萨求佛本业经一卷。",
        "removable_titles": {"諸菩薩求佛本業經一卷"},
        "removable_bylines": {"西晉優婆塞聶道真譯"},
    },
    "jian-bei-yi-qie-zhi-de-jing": {
        "work": "T0285",
        "display_title": "渐备一切智德经",
        "tag": "渐备一切智德经",
        "slug": "jian-bei-yi-qie-zhi-de-jing",
        "group": "shidi",
        "total_juan": 5,
        "weight": 10,
        "summary": "渐备一切智德经五卷。",
        "removable_title_patterns": [
            r"^漸備一切智德經卷第[零一二三四五六七八九十百]+(?:一名十住，又名大慧光三昧)?$"
        ],
        "removable_bylines": {"西晉月支三藏竺法護譯"},
    },
    "shi-zhu-jing": {
        "work": "T0286",
        "display_title": "十住经",
        "tag": "十住经",
        "slug": "shi-zhu-jing",
        "group": "shidi",
        "total_juan": 4,
        "weight": 20,
        "summary": "十住经四卷。",
        "removable_title_patterns": [r"^十住經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {
            "後秦龜茲國三藏鳩摩羅什譯",
            "後秦三藏鳩摩羅什譯",
        },
    },
    "fo-shuo-shi-di-jing": {
        "work": "T0287",
        "display_title": "佛说十地经",
        "tag": "佛说十地经",
        "slug": "fo-shuo-shi-di-jing",
        "group": "shidi",
        "total_juan": 9,
        "weight": 30,
        "summary": "佛说十地经九卷。",
        "removable_title_patterns": [r"^佛說十地經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {
            "大唐國僧法界從中印度持此梵本請于闐三藏沙門尸羅達摩於北庭龍興寺譯",
            "大唐于闐三藏沙門尸羅達摩於北庭龍興寺譯",
        },
    },
    "fo-shuo-luo-mo-qie-jing": {
        "work": "T0294",
        "display_title": "佛说罗摩伽经",
        "tag": "佛说罗摩伽经",
        "slug": "fo-shuo-luo-mo-qie-jing",
        "group": "rufajie",
        "total_juan": 3,
        "weight": 10,
        "summary": "佛说罗摩伽经三卷。",
        "removable_title_patterns": [r"^佛說羅摩伽經卷(?:上|中|下)$"],
        "removable_bylines": {"西秦沙門聖堅譯"},
    },
    "da-fang-guang-fo-hua-yan-jing-ru-fa-jie-pin": {
        "work": "T0295",
        "display_title": "大方广佛华严经入法界品",
        "tag": "大方广佛华严经入法界品",
        "slug": "da-fang-guang-fo-hua-yan-jing-ru-fa-jie-pin",
        "group": "rufajie",
        "total_juan": 1,
        "weight": 20,
        "summary": "大方广佛华严经入法界品一卷。",
        "removable_titles": {"大方廣佛華嚴經入法界品"},
        "removable_bylines": {"唐天竺三藏地婆訶羅譯"},
    },
    "wen-shu-shi-li-fa-yuan-jing": {
        "work": "T0296",
        "display_title": "文殊师利发愿经",
        "tag": "文殊师利发愿经",
        "slug": "wen-shu-shi-li-fa-yuan-jing",
        "group": "xingyuan",
        "total_juan": 1,
        "weight": 10,
        "summary": "文殊师利发愿经一卷。",
        "removable_titles": {"文殊師利發願經"},
        "removable_bylines": {"東晉天竺三藏佛陀跋陀羅譯"},
    },
    "pu-xian-pu-sa-xing-yuan-zan": {
        "work": "T0297",
        "display_title": "普贤菩萨行愿赞",
        "tag": "普贤菩萨行愿赞",
        "slug": "pu-xian-pu-sa-xing-yuan-zan",
        "group": "xingyuan",
        "total_juan": 1,
        "weight": 20,
        "summary": "普贤菩萨行愿赞一卷。",
        "removable_titles": {"普賢菩薩行願讚"},
        "removable_bylines": {
            "開府儀同三司特進試鴻臚卿肅國公食邑三千戶賜紫贈司空諡大鑑正號大廣智大興善寺三藏沙門不空奉詔譯"
        },
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def collection_target(config: dict) -> Path:
    return HUAYAN_ROOT / config["group"] / config["slug"]


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


def write_group_index(group_key: str) -> None:
    config = GROUPS[group_key]
    target = HUAYAN_ROOT / group_key
    target.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "---",
            f'title: "{config["title"]}"',
            "date: 2026-05-16",
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
            "date: 2026-05-16",
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
        "date: 2026-05-16",
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
    parser.add_argument("--collection", choices=sorted(COLLECTIONS), required=True)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    config = COLLECTIONS[args.collection]
    start = args.start or 1
    end = args.end or config["total_juan"]
    if start < 1 or end > config["total_juan"] or start > end:
        raise SystemExit(f"卷号范围必须在 1..{config['total_juan']} 内")

    write_group_index(config["group"])
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
