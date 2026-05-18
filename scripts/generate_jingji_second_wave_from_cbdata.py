#!/usr/bin/env python3
"""Generate the second structured Jingji groups from CBETA's stable juan endpoint."""

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
JINGJI_ROOT = ROOT / "content/posts/buddha/jingzang/jingji"

GROUPS = {
    "wenshu": {
        "title": "文殊系",
        "summary": "经集部中文殊师利及其相关问法、行法经典。",
        "intro": "收录经集部中文殊师利及其相关问法、行法经典。",
        "weight": 40,
    },
    "weimo": {
        "title": "维摩系",
        "summary": "经集部中维摩诘经典的三种重要异译。",
        "intro": "收录经集部中维摩诘经典的三种重要异译。",
        "weight": 50,
    },
}

COLLECTIONS = {
    "wen-shu-shi-li-wen-pu-sa-shu-jing": {
        "work": "T0458",
        "display_title": "文殊师利问菩萨署经",
        "tag": "文殊师利问菩萨署经",
        "slug": "wen-shu-shi-li-wen-pu-sa-shu-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 10,
        "summary": "文殊师利问菩萨署经一卷。",
        "removable_titles": {"文殊師利問菩薩署經"},
        "removable_bylines": {"後漢月氏三藏支婁迦讖譯"},
    },
    "fo-shuo-wen-shu-hui-guo-jing": {
        "work": "T0459",
        "display_title": "佛说文殊悔过经",
        "tag": "佛说文殊悔过经",
        "slug": "fo-shuo-wen-shu-hui-guo-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 20,
        "summary": "佛说文殊悔过经一卷。",
        "removable_titles": {"佛說文殊悔過經"},
        "removable_bylines": {"西晉月氏國三藏竺法護譯"},
    },
    "fo-shuo-wen-shu-shi-li-jing-lv-jing": {
        "work": "T0460",
        "display_title": "佛说文殊师利净律经",
        "tag": "佛说文殊师利净律经",
        "slug": "fo-shuo-wen-shu-shi-li-jing-lv-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 30,
        "summary": "佛说文殊师利净律经一卷。",
        "removable_titles": {"佛說文殊師利淨律經"},
        "removable_bylines": {"西晉月氏國三藏竺法護譯"},
    },
    "fo-shuo-wen-shu-shi-li-xian-bao-zang-jing": {
        "work": "T0461",
        "display_title": "佛说文殊师利现宝藏经",
        "tag": "佛说文殊师利现宝藏经",
        "slug": "fo-shuo-wen-shu-shi-li-xian-bao-zang-jing",
        "group": "wenshu",
        "total_juan": 2,
        "weight": 40,
        "summary": "佛说文殊师利现宝藏经二卷。",
        "removable_title_patterns": [r"^佛說文殊師利現寶藏經卷(?:上|下)$"],
        "removable_bylines": {"西晉月氏三藏竺法護譯"},
    },
    "da-fang-guang-bao-qie-jing": {
        "work": "T0462",
        "display_title": "大方广宝箧经",
        "tag": "大方广宝箧经",
        "slug": "da-fang-guang-bao-qie-jing",
        "group": "wenshu",
        "total_juan": 3,
        "weight": 50,
        "summary": "大方广宝箧经三卷。",
        "removable_title_patterns": [r"^大方廣寶篋經卷(?:上|中|下)$"],
        "removable_bylines": {"宋天竺三藏求那跋陀羅譯"},
    },
    "fo-shuo-wen-shu-shi-li-ban-nie-pan-jing": {
        "work": "T0463",
        "display_title": "佛说文殊师利般涅槃经",
        "tag": "佛说文殊师利般涅槃经",
        "slug": "fo-shuo-wen-shu-shi-li-ban-nie-pan-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 60,
        "summary": "佛说文殊师利般涅槃经一卷。",
        "removable_titles": {"佛說文殊師利般涅槃經"},
        "removable_bylines": {"西晉居士聶道真譯"},
    },
    "wen-shu-shi-li-wen-pu-ti-jing": {
        "work": "T0464",
        "display_title": "文殊师利问菩提经",
        "tag": "文殊师利问菩提经",
        "slug": "wen-shu-shi-li-wen-pu-ti-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 70,
        "summary": "文殊师利问菩提经一卷。",
        "removable_titles": {"文殊師利問菩提經一名伽耶山頂經"},
        "removable_bylines": {"姚秦龜茲三藏鳩摩羅什譯"},
    },
    "jia-ye-shan-ding-jing": {
        "work": "T0465",
        "display_title": "伽耶山顶经",
        "tag": "伽耶山顶经",
        "slug": "jia-ye-shan-ding-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 80,
        "summary": "伽耶山顶经一卷。",
        "removable_titles": {"伽耶山頂經"},
        "removable_bylines": {"元魏天竺三藏菩提流支譯"},
    },
    "fo-shuo-xiang-tou-jing-she-jing": {
        "work": "T0466",
        "display_title": "佛说象头精舍经",
        "tag": "佛说象头精舍经",
        "slug": "fo-shuo-xiang-tou-jing-she-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 90,
        "summary": "佛说象头精舍经一卷。",
        "removable_titles": {"佛說象頭精舍經"},
        "removable_bylines": {"隋天竺三藏毘尼多流支譯"},
    },
    "da-cheng-jia-ye-shan-ding-jing": {
        "work": "T0467",
        "display_title": "大乘伽耶山顶经",
        "tag": "大乘伽耶山顶经",
        "slug": "da-cheng-jia-ye-shan-ding-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 100,
        "summary": "大乘伽耶山顶经一卷。",
        "removable_titles": {"大乘伽耶山頂經"},
        "removable_bylines": {"大唐天竺三藏菩提流志譯"},
    },
    "wen-shu-shi-li-wen-jing": {
        "work": "T0468",
        "display_title": "文殊师利问经",
        "tag": "文殊师利问经",
        "slug": "wen-shu-shi-li-wen-jing",
        "group": "wenshu",
        "total_juan": 2,
        "weight": 110,
        "summary": "文殊师利问经二卷。",
        "removable_title_patterns": [r"^文殊師利問經卷(?:上|下)$"],
        "removable_bylines": {"梁扶南國三藏僧伽婆羅譯"},
    },
    "wen-shu-wen-jing-zi-mu-pin-di-shi-si": {
        "work": "T0469",
        "display_title": "文殊问经字母品第十四",
        "tag": "文殊问经字母品第十四",
        "slug": "wen-shu-wen-jing-zi-mu-pin-di-shi-si",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 120,
        "summary": "文殊问经字母品第十四一卷。",
        "removable_titles": {"文殊問經字母品第十四"},
        "removable_bylines": {
            "開府儀同三司特進試鴻臚卿肅國公，食邑三千戶，賜紫贈司空，謚大鑒，正號大廣智，大興善寺三藏沙門不空，奉詔譯"
        },
    },
    "fo-shuo-wen-shu-shi-li-xun-xing-jing": {
        "work": "T0470",
        "display_title": "佛说文殊师利巡行经",
        "tag": "佛说文殊师利巡行经",
        "slug": "fo-shuo-wen-shu-shi-li-xun-xing-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 130,
        "summary": "佛说文殊师利巡行经一卷。",
        "removable_titles": {"佛說文殊師利巡行經"},
        "removable_bylines": {"元魏天竺三藏菩提流支譯"},
    },
    "fo-shuo-wen-shu-shi-li-xing-jing": {
        "work": "T0471",
        "display_title": "佛说文殊师利行经",
        "tag": "佛说文殊师利行经",
        "slug": "fo-shuo-wen-shu-shi-li-xing-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 140,
        "summary": "佛说文殊师利行经一卷。",
        "removable_titles": {"佛說文殊尸利行經"},
        "removable_bylines": {"隋天竺三藏豆那掘多譯"},
    },
    "fo-shuo-da-cheng-shan-jian-bian-hua-wen-shu-shi-li-wen-fa-jing": {
        "work": "T0472",
        "display_title": "佛说大乘善见变化文殊师利问法经",
        "tag": "佛说大乘善见变化文殊师利问法经",
        "slug": "fo-shuo-da-cheng-shan-jian-bian-hua-wen-shu-shi-li-wen-fa-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 150,
        "summary": "佛说大乘善见变化文殊师利问法经一卷。",
        "removable_titles": {"佛說大乘善見變化文殊師利問法經"},
        "removable_bylines": {
            "西天中印度，惹爛馱囉國密林寺，三藏明教大師，賜紫沙門臣天息災奉詔譯"
        },
    },
    "fo-shuo-miao-ji-xiang-pu-sa-suo-wen-da-cheng-fa-luo-jing": {
        "work": "T0473",
        "display_title": "佛说妙吉祥菩萨所问大乘法螺经",
        "tag": "佛说妙吉祥菩萨所问大乘法螺经",
        "slug": "fo-shuo-miao-ji-xiang-pu-sa-suo-wen-da-cheng-fa-luo-jing",
        "group": "wenshu",
        "total_juan": 1,
        "weight": 160,
        "summary": "佛说妙吉祥菩萨所问大乘法螺经一卷。",
        "removable_titles": {"佛說妙吉祥菩薩所問大乘法螺經"},
        "removable_bylines": {
            "西天譯經三藏、朝散大夫、試光祿卿、明教大師臣法賢奉詔譯"
        },
    },
    "fo-shuo-wei-mo-jie-jing": {
        "work": "T0474",
        "display_title": "佛说维摩诘经",
        "tag": "佛说维摩诘经",
        "slug": "fo-shuo-wei-mo-jie-jing",
        "group": "weimo",
        "total_juan": 2,
        "weight": 10,
        "summary": "佛说维摩诘经二卷。",
        "removable_title_patterns": [r"^佛說維摩詰經卷(?:上|下).*$"],
        "removable_bylines": {"吳月氏優婆塞支謙譯"},
    },
    "wei-mo-jie-suo-shuo-jing": {
        "work": "T0475",
        "display_title": "维摩诘所说经",
        "tag": "维摩诘所说经",
        "slug": "wei-mo-jie-suo-shuo-jing",
        "group": "weimo",
        "total_juan": 3,
        "weight": 20,
        "summary": "维摩诘所说经三卷。",
        "removable_title_patterns": [r"^維摩詰所說經一名不可思議解脫(?:上|中|下)卷$"],
        "removable_bylines": {"姚秦三藏鳩摩羅什譯"},
    },
    "shuo-wu-gou-cheng-jing": {
        "work": "T0476",
        "display_title": "说无垢称经",
        "tag": "说无垢称经",
        "slug": "shuo-wu-gou-cheng-jing",
        "group": "weimo",
        "total_juan": 6,
        "weight": 30,
        "summary": "说无垢称经六卷。",
        "removable_title_patterns": [r"^說無垢稱經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"大唐三藏法師玄奘奉詔譯"},
    },
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def collection_target(config: dict) -> Path:
    return JINGJI_ROOT / config["group"] / config["slug"]


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


def write_group_index(group_key: str) -> None:
    config = GROUPS[group_key]
    target = JINGJI_ROOT / group_key
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
    parser.add_argument("--group", choices=sorted(GROUPS))
    parser.add_argument("--collection", choices=sorted(COLLECTIONS))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    selected = sum(bool(item) for item in [args.group, args.collection, args.all])
    if selected != 1:
        raise SystemExit("请且仅请指定 --group、--collection 或 --all")

    if args.all:
        configs = list(COLLECTIONS.values())
    elif args.group:
        configs = [config for config in COLLECTIONS.values() if config["group"] == args.group]
    else:
        configs = [COLLECTIONS[args.collection]]

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
