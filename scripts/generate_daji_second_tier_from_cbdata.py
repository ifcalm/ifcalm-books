#!/usr/bin/env python3
"""Generate second-tier Daji collections from CBETA's stable juan endpoint."""

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
    "xukongzang": {
        "title": "虚空藏系",
        "summary": "大集部中虚空藏相关经典。",
        "intro": "收录大集部中虚空藏相关经典。",
        "weight": 40,
    },
    "danxing": {
        "title": "单行经",
        "summary": "大集部中未另归专题支脉的重要单行经。",
        "intro": "收录大集部中未另归专题支脉的重要单行经。",
        "weight": 50,
    },
}

COLLECTIONS = {
    "da-ji-da-xu-kong-zang-pu-sa-suo-wen-jing": {
        "work": "T0404",
        "display_title": "大集大虚空藏菩萨所问经",
        "tag": "大集大虚空藏菩萨所问经",
        "slug": "da-ji-da-xu-kong-zang-pu-sa-suo-wen-jing",
        "group": "xukongzang",
        "total_juan": 8,
        "weight": 10,
        "summary": "大集大虚空藏菩萨所问经八卷。",
        "removable_title_patterns": [
            r"^大集大虛空藏菩薩所問經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {
            "開府儀同三司特進試鴻臚卿肅國公食邑三千戶賜紫贈司空謚大鑑正號大廣智大興善寺三藏沙門不空奉詔譯"
        },
    },
    "xu-kong-zang-pu-sa-jing": {
        "work": "T0405",
        "display_title": "虚空藏菩萨经",
        "tag": "虚空藏菩萨经",
        "slug": "xu-kong-zang-pu-sa-jing",
        "group": "xukongzang",
        "total_juan": 1,
        "weight": 20,
        "summary": "虚空藏菩萨经一卷。",
        "removable_titles": {"虛空藏菩薩經"},
        "removable_bylines": {"姚秦罽賓三藏佛陀耶舍譯"},
    },
    "fo-shuo-xu-kong-zang-pu-sa-shen-zhou-jing": {
        "work": "T0406",
        "display_title": "佛说虚空藏菩萨神咒经",
        "tag": "佛说虚空藏菩萨神咒经",
        "slug": "fo-shuo-xu-kong-zang-pu-sa-shen-zhou-jing",
        "group": "xukongzang",
        "total_juan": 1,
        "weight": 30,
        "summary": "佛说虚空藏菩萨神咒经一卷。",
        "removable_titles": {"佛說虛空藏菩薩神呪經"},
        "removable_bylines": set(),
    },
    "xu-kong-zang-pu-sa-shen-zhou-jing": {
        "work": "T0407",
        "display_title": "虚空藏菩萨神咒经",
        "tag": "虚空藏菩萨神咒经",
        "slug": "xu-kong-zang-pu-sa-shen-zhou-jing",
        "group": "xukongzang",
        "total_juan": 1,
        "weight": 40,
        "summary": "虚空藏菩萨神咒经一卷。",
        "removable_titles": {"虛空藏菩薩神呪經"},
        "removable_bylines": {"宋罽賓國三藏曇摩蜜多譯"},
    },
    "xu-kong-yun-pu-sa-jing": {
        "work": "T0408",
        "display_title": "虚空孕菩萨经",
        "tag": "虚空孕菩萨经",
        "slug": "xu-kong-yun-pu-sa-jing",
        "group": "xukongzang",
        "total_juan": 2,
        "weight": 50,
        "summary": "虚空孕菩萨经二卷。",
        "removable_title_patterns": [r"^虛空孕菩薩經卷(?:上|下)$"],
        "removable_bylines": {"隋天竺三藏闍那崛多譯"},
    },
    "guan-xu-kong-zang-pu-sa-jing": {
        "work": "T0409",
        "display_title": "观虚空藏菩萨经",
        "tag": "观虚空藏菩萨经",
        "slug": "guan-xu-kong-zang-pu-sa-jing",
        "group": "xukongzang",
        "total_juan": 1,
        "weight": 60,
        "summary": "观虚空藏菩萨经一卷。",
        "removable_titles": {"觀虛空藏菩薩經"},
        "removable_bylines": {"宋罽賓三藏曇摩蜜多譯"},
    },
    "da-ai-jing": {
        "work": "T0398",
        "display_title": "大哀经",
        "tag": "大哀经",
        "slug": "da-ai-jing",
        "group": "danxing",
        "total_juan": 8,
        "weight": 10,
        "summary": "大哀经八卷。",
        "removable_title_patterns": [r"^大哀經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"西晉月氏三藏竺法護譯"},
    },
    "bao-nv-suo-wen-jing": {
        "work": "T0399",
        "display_title": "宝女所问经",
        "tag": "宝女所问经",
        "slug": "bao-nv-suo-wen-jing",
        "group": "danxing",
        "total_juan": 4,
        "weight": 20,
        "summary": "宝女所问经四卷。",
        "removable_title_patterns": [r"^寶女所問經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"西晉月支三藏竺法護譯"},
    },
    "fo-shuo-hai-yi-pu-sa-suo-wen-jing-yin-fa-men-jing": {
        "work": "T0400",
        "display_title": "佛说海意菩萨所问净印法门经",
        "tag": "佛说海意菩萨所问净印法门经",
        "slug": "fo-shuo-hai-yi-pu-sa-suo-wen-jing-yin-fa-men-jing",
        "group": "danxing",
        "total_juan": 18,
        "weight": 30,
        "summary": "佛说海意菩萨所问净印法门经十八卷。",
        "removable_title_patterns": [
            r"^佛說海意菩薩所問淨印法門經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {
            "譯經三藏朝散大夫試鴻臚卿光梵大師賜紫沙門臣惟淨等奉詔譯",
            "西天譯經三藏朝散大夫試鴻臚卿傳梵大師賜紫沙門臣法護等奉詔譯",
        },
        "preserve_byline_juans": {1, 4, 7, 10, 13, 16},
    },
    "fo-shuo-wu-yan-tong-zi-jing": {
        "work": "T0401",
        "display_title": "佛说无言童子经",
        "tag": "佛说无言童子经",
        "slug": "fo-shuo-wu-yan-tong-zi-jing",
        "group": "danxing",
        "total_juan": 2,
        "weight": 40,
        "summary": "佛说无言童子经二卷。",
        "removable_title_patterns": [r"^佛說無言童子經卷(?:上|下)$"],
        "removable_bylines": {"西晉月支三藏竺法護譯"},
    },
    "bao-xing-tuo-luo-ni-jing": {
        "work": "T0402",
        "display_title": "宝星陀罗尼经",
        "tag": "宝星陀罗尼经",
        "slug": "bao-xing-tuo-luo-ni-jing",
        "group": "danxing",
        "total_juan": 10,
        "weight": 50,
        "summary": "宝星陀罗尼经十卷。",
        "removable_title_patterns": [
            r"^寶星陀羅尼經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {"唐天竺三藏波羅頗蜜多羅譯"},
    },
    "a-cha-mo-pu-sa-jing": {
        "work": "T0403",
        "display_title": "阿差末菩萨经",
        "tag": "阿差末菩萨经",
        "slug": "a-cha-mo-pu-sa-jing",
        "group": "danxing",
        "total_juan": 7,
        "weight": 60,
        "summary": "阿差末菩萨经七卷。",
        "removable_title_patterns": [r"^阿差末菩薩經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"西晉月氏國三藏竺法護譯"},
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def collection_target(config: dict) -> Path:
    return DAJI_ROOT / config["group"] / config["slug"]


def drop_repeated_title_and_byline(config: dict, blocks, juan: int):
    cleaned = []
    removable_titles = {normalize_text(item) for item in config.get("removable_titles", set())}
    removable_title_res = [re.compile(pattern) for pattern in config.get("removable_title_patterns", [])]
    removable_bylines = {normalize_text(item) for item in config["removable_bylines"]}
    preserve_byline = juan in config.get("preserve_byline_juans", set())

    for block_type, level, text in blocks:
        normalized = normalize_text(text)
        if block_type == "paragraph" and (
            normalized in removable_titles
            or any(regex.fullmatch(normalized) for regex in removable_title_res)
        ):
            continue
        if block_type == "byline" and normalized in removable_bylines and not preserve_byline:
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
    return drop_repeated_title_and_byline(config, parser.blocks, juan)


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
