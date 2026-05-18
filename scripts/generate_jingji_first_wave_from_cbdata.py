#!/usr/bin/env python3
"""Generate the first structured Jingji groups from CBETA's stable juan endpoint."""

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
    "foming": {
        "title": "佛名系",
        "summary": "经集部中称名、佛名、诸佛功德与诸佛护念相关经典。",
        "intro": "收录经集部中称名、佛名、诸佛功德与诸佛护念相关经典。",
        "weight": 10,
    },
    "yaoshi": {
        "title": "药师系",
        "summary": "经集部中药师如来本愿相关经典。",
        "intro": "收录经集部中药师如来本愿相关经典。",
        "weight": 20,
    },
    "mile": {
        "title": "弥勒系",
        "summary": "经集部中弥勒上生、下生与成佛相关经典。",
        "intro": "收录经集部中弥勒上生、下生与成佛相关经典。",
        "weight": 30,
    },
}


def title_pattern(title: str) -> str:
    return rf"^{re.escape(title)}(?:卷第[零一二三四五六七八九十百]+|卷[上中下]|卷(?:上|下)|一卷)?$"


COLLECTIONS = {
    "xian-jie-jing": {
        "work": "T0425",
        "display_title": "贤劫经",
        "tag": "贤劫经",
        "slug": "xian-jie-jing",
        "group": "foming",
        "total_juan": 8,
        "weight": 10,
        "summary": "贤劫经八卷。",
        "removable_title_patterns": [
            r"^賢劫經卷第[零一二三四五六七八九十百]+(?:亦名颰陀劫三昧，晉曰賢劫定意經)?$"
        ],
        "removable_bylines": {"西晉月氏三藏竺法護譯"},
    },
    "fo-shuo-qian-fo-yin-yuan-jing": {
        "work": "T0426",
        "display_title": "佛说千佛因缘经",
        "tag": "佛说千佛因缘经",
        "slug": "fo-shuo-qian-fo-yin-yuan-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 20,
        "summary": "佛说千佛因缘经一卷。",
        "removable_titles": {"佛說千佛因緣經"},
        "removable_bylines": {"後秦龜茲國三藏鳩摩羅什譯"},
    },
    "fo-shuo-ba-ji-xiang-shen-zhou-jing": {
        "work": "T0427",
        "display_title": "佛说八吉祥神咒经",
        "tag": "佛说八吉祥神咒经",
        "slug": "fo-shuo-ba-ji-xiang-shen-zhou-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 30,
        "summary": "佛说八吉祥神咒经一卷。",
        "removable_titles": {"佛說八吉祥神呪經"},
        "removable_bylines": {"吳月氏優婆塞支謙譯"},
    },
    "fo-shuo-ba-yang-shen-zhou-jing": {
        "work": "T0428",
        "display_title": "佛说八阳神咒经",
        "tag": "佛说八阳神咒经",
        "slug": "fo-shuo-ba-yang-shen-zhou-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 40,
        "summary": "佛说八阳神咒经一卷。",
        "removable_titles": {"佛說八陽神呪經"},
        "removable_bylines": {"西晉月氏三藏竺法護譯"},
    },
    "fo-shuo-ba-bu-fo-ming-jing": {
        "work": "T0429",
        "display_title": "佛说八部佛名经",
        "tag": "佛说八部佛名经",
        "slug": "fo-shuo-ba-bu-fo-ming-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 50,
        "summary": "佛说八部佛名经一卷。",
        "removable_titles": {"佛說八部佛名經"},
        "removable_bylines": {"元魏天竺婆羅門瞿曇般若流支譯"},
    },
    "ba-ji-xiang-jing": {
        "work": "T0430",
        "display_title": "八吉祥经",
        "tag": "八吉祥经",
        "slug": "ba-ji-xiang-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 60,
        "summary": "八吉祥经一卷。",
        "removable_titles": {"八吉祥經"},
        "removable_bylines": {"梁扶南三藏僧伽婆羅譯"},
    },
    "ba-fo-ming-hao-jing": {
        "work": "T0431",
        "display_title": "八佛名号经",
        "tag": "八佛名号经",
        "slug": "ba-fo-ming-hao-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 70,
        "summary": "八佛名号经一卷。",
        "removable_titles": {"八佛名號經"},
        "removable_bylines": {"隋天竺三藏闍那崛多譯"},
    },
    "fo-shuo-shi-ji-xiang-jing": {
        "work": "T0432",
        "display_title": "佛说十吉祥经",
        "tag": "佛说十吉祥经",
        "slug": "fo-shuo-shi-ji-xiang-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 80,
        "summary": "佛说十吉祥经一卷。",
        "removable_titles": {"佛說十吉祥經"},
        "removable_bylines": {"失譯人名今附秦錄"},
    },
    "fo-shuo-bao-wang-jing": {
        "work": "T0433",
        "display_title": "佛说宝网经",
        "tag": "佛说宝网经",
        "slug": "fo-shuo-bao-wang-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 90,
        "summary": "佛说宝网经一卷。",
        "removable_titles": {"佛說寶網經"},
        "removable_bylines": {"西晉月氏三藏竺法護譯"},
    },
    "fo-shuo-cheng-yang-zhu-fo-gong-de-jing": {
        "work": "T0434",
        "display_title": "佛说称扬诸佛功德经",
        "tag": "佛说称扬诸佛功德经",
        "slug": "fo-shuo-cheng-yang-zhu-fo-gong-de-jing",
        "group": "foming",
        "total_juan": 3,
        "weight": 100,
        "summary": "佛说称扬诸佛功德经三卷。",
        "removable_title_patterns": [r"^佛說稱揚諸佛功德經卷(?:上|中|下)$"],
        "removable_bylines": {"元魏天竺三藏吉迦夜譯"},
    },
    "fo-shuo-mie-shi-fang-ming-jing": {
        "work": "T0435",
        "display_title": "佛说灭十方冥经",
        "tag": "佛说灭十方冥经",
        "slug": "fo-shuo-mie-shi-fang-ming-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 110,
        "summary": "佛说灭十方冥经一卷。",
        "removable_title_patterns": [r"^佛說滅十方冥經一卷$"],
        "removable_bylines": {"西晉月氏國三藏竺法護譯"},
    },
    "shou-chi-qi-fo-ming-hao-suo-sheng-gong-de-jing": {
        "work": "T0436",
        "display_title": "受持七佛名号所生功德经",
        "tag": "受持七佛名号所生功德经",
        "slug": "shou-chi-qi-fo-ming-hao-suo-sheng-gong-de-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 120,
        "summary": "受持七佛名号所生功德经一卷。",
        "removable_titles": {"受持七佛名號所生功德經"},
        "removable_bylines": {"大唐三藏法師玄奘奉詔譯"},
    },
    "da-cheng-bao-yue-tong-zi-wen-fa-jing": {
        "work": "T0437",
        "display_title": "大乘宝月童子问法经",
        "tag": "大乘宝月童子问法经",
        "slug": "da-cheng-bao-yue-tong-zi-wen-fa-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 130,
        "summary": "大乘宝月童子问法经一卷。",
        "removable_titles": {"大乘寶月童子問法經"},
        "removable_bylines": {"西天譯經三藏朝散大夫試鴻臚少卿傳法大師臣施護奉詔譯"},
    },
    "fo-shuo-da-cheng-da-fang-guang-fo-guan-jing": {
        "work": "T0438",
        "display_title": "佛说大乘大方广佛冠经",
        "tag": "佛说大乘大方广佛冠经",
        "slug": "fo-shuo-da-cheng-da-fang-guang-fo-guan-jing",
        "group": "foming",
        "total_juan": 2,
        "weight": 140,
        "summary": "佛说大乘大方广佛冠经二卷。",
        "removable_title_patterns": [r"^佛說大乘大方廣佛冠經卷(?:上|下)$"],
        "removable_bylines": {"西天譯經三藏朝散大夫試鴻臚卿傳梵大師賜紫沙門臣法護等奉詔譯"},
    },
    "fo-shuo-zhu-fo-jing": {
        "work": "T0439",
        "display_title": "佛说诸佛经",
        "tag": "佛说诸佛经",
        "slug": "fo-shuo-zhu-fo-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 150,
        "summary": "佛说诸佛经一卷。",
        "removable_titles": {"佛說諸佛經"},
        "removable_bylines": {"西天譯經三藏朝散大夫試鴻臚卿傳法大師臣施護奉詔譯"},
    },
    "fo-shuo-fo-ming-jing-12": {
        "work": "T0440",
        "display_title": "佛说佛名经（十二卷本）",
        "tag": "佛说佛名经（十二卷本）",
        "slug": "fo-shuo-fo-ming-jing-12",
        "group": "foming",
        "total_juan": 12,
        "weight": 160,
        "summary": "佛说佛名经十二卷。",
        "removable_title_patterns": [r"^佛說佛名經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": {"三藏菩提流支在胡相國秦太上文宣公第譯"},
    },
    "fo-shuo-fo-ming-jing-30": {
        "work": "T0441",
        "display_title": "佛说佛名经（三十卷本）",
        "tag": "佛说佛名经（三十卷本）",
        "slug": "fo-shuo-fo-ming-jing-30",
        "group": "foming",
        "total_juan": 30,
        "weight": 170,
        "summary": "佛说佛名经三十卷。",
        "removable_title_patterns": [r"^佛說佛名經卷第[零一二三四五六七八九十百]+$"],
        "removable_bylines": set(),
    },
    "shi-fang-qian-wu-bai-fo-ming-jing": {
        "work": "T0442",
        "display_title": "十方千五百佛名经",
        "tag": "十方千五百佛名经",
        "slug": "shi-fang-qian-wu-bai-fo-ming-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 180,
        "summary": "十方千五百佛名经一卷。",
        "removable_titles": {"十方千五百佛名經"},
        "removable_bylines": set(),
    },
    "wu-qian-wu-bai-fo-ming-shen-zhou-chu-zhang-mie-zui-jing": {
        "work": "T0443",
        "display_title": "五千五百佛名神咒除障灭罪经",
        "tag": "五千五百佛名神咒除障灭罪经",
        "slug": "wu-qian-wu-bai-fo-ming-shen-zhou-chu-zhang-mie-zui-jing",
        "group": "foming",
        "total_juan": 8,
        "weight": 190,
        "summary": "五千五百佛名神咒除障灭罪经八卷。",
        "removable_title_patterns": [
            r"^五千五百佛名神呪除障滅罪經卷第[零一二三四五六七八九十百]+$"
        ],
        "removable_bylines": {"大隋北印度三藏闍那崛譯"},
    },
    "fo-shuo-bai-fo-ming-jing": {
        "work": "T0444",
        "display_title": "佛说百佛名经",
        "tag": "佛说百佛名经",
        "slug": "fo-shuo-bai-fo-ming-jing",
        "group": "foming",
        "total_juan": 1,
        "weight": 200,
        "summary": "佛说百佛名经一卷。",
        "removable_titles": {"佛說百佛名經"},
        "removable_bylines": {"隋天竺三藏那連提耶舍譯"},
    },
    "fo-shuo-bu-si-yi-gong-de-zhu-fo-suo-hu-nian-jing": {
        "work": "T0445",
        "display_title": "佛说不思议功德诸佛所护念经",
        "tag": "佛说不思议功德诸佛所护念经",
        "slug": "fo-shuo-bu-si-yi-gong-de-zhu-fo-suo-hu-nian-jing",
        "group": "foming",
        "total_juan": 2,
        "weight": 210,
        "summary": "佛说不思议功德诸佛所护念经二卷。",
        "removable_title_patterns": [
            r"^佛說不思議功德諸佛所護念經卷(?:上|下)$"
        ],
        "removable_bylines": {"曹魏代失譯人名"},
    },
    "fo-shuo-yao-shi-ru-lai-ben-yuan-jing": {
        "work": "T0449",
        "display_title": "佛说药师如来本愿经",
        "tag": "佛说药师如来本愿经",
        "slug": "fo-shuo-yao-shi-ru-lai-ben-yuan-jing",
        "group": "yaoshi",
        "total_juan": 1,
        "weight": 10,
        "summary": "佛说药师如来本愿经一卷。",
        "removable_titles": {"佛說藥師如來本願經"},
        "removable_bylines": {"隋天竺三藏達摩笈多譯"},
    },
    "yao-shi-liu-li-guang-ru-lai-ben-yuan-gong-de-jing": {
        "work": "T0450",
        "display_title": "药师琉璃光如来本愿功德经",
        "tag": "药师琉璃光如来本愿功德经",
        "slug": "yao-shi-liu-li-guang-ru-lai-ben-yuan-gong-de-jing",
        "group": "yaoshi",
        "total_juan": 1,
        "weight": 20,
        "summary": "药师琉璃光如来本愿功德经一卷。",
        "removable_titles": {"藥師琉璃光如來本願功德經"},
        "removable_bylines": {"大唐、三藏法師玄奘奉詔譯"},
    },
    "yao-shi-liu-li-guang-qi-fo-ben-yuan-gong-de-jing": {
        "work": "T0451",
        "display_title": "药师琉璃光七佛本愿功德经",
        "tag": "药师琉璃光七佛本愿功德经",
        "slug": "yao-shi-liu-li-guang-qi-fo-ben-yuan-gong-de-jing",
        "group": "yaoshi",
        "total_juan": 2,
        "weight": 30,
        "summary": "药师琉璃光七佛本愿功德经二卷。",
        "removable_title_patterns": [r"^藥師琉璃光七佛本願功德經卷(?:上|下)$"],
        "removable_bylines": {"大唐三藏沙門義淨於佛光內寺譯"},
    },
    "fo-shuo-guan-mi-le-pu-sa-shang-sheng-dou-shuai-tian-jing": {
        "work": "T0452",
        "display_title": "佛说观弥勒菩萨上生兜率天经",
        "tag": "佛说观弥勒菩萨上生兜率天经",
        "slug": "fo-shuo-guan-mi-le-pu-sa-shang-sheng-dou-shuai-tian-jing",
        "group": "mile",
        "total_juan": 1,
        "weight": 10,
        "summary": "佛说观弥勒菩萨上生兜率天经一卷。",
        "removable_titles": {"佛說觀彌勒菩薩上生兜率天經"},
        "removable_bylines": {"宋居士沮渠京聲譯"},
    },
    "fo-shuo-mi-le-xia-sheng-jing": {
        "work": "T0453",
        "display_title": "佛说弥勒下生经",
        "tag": "佛说弥勒下生经",
        "slug": "fo-shuo-mi-le-xia-sheng-jing",
        "group": "mile",
        "total_juan": 1,
        "weight": 20,
        "summary": "佛说弥勒下生经一卷。",
        "removable_titles": {"佛說彌勒下生經"},
        "removable_bylines": {"西晉月氏三藏竺法護譯"},
    },
    "fo-shuo-mi-le-xia-sheng-cheng-fo-jing-qin": {
        "work": "T0454",
        "display_title": "佛说弥勒下生成佛经（秦译）",
        "tag": "佛说弥勒下生成佛经（秦译）",
        "slug": "fo-shuo-mi-le-xia-sheng-cheng-fo-jing-qin",
        "group": "mile",
        "total_juan": 1,
        "weight": 30,
        "summary": "佛说弥勒下生成佛经秦译本一卷。",
        "removable_titles": {"佛說彌勒下生成佛經"},
        "removable_bylines": {"後秦龜茲國三藏鳩摩羅什譯"},
    },
    "fo-shuo-mi-le-xia-sheng-cheng-fo-jing-tang": {
        "work": "T0455",
        "display_title": "佛说弥勒下生成佛经（唐译）",
        "tag": "佛说弥勒下生成佛经（唐译）",
        "slug": "fo-shuo-mi-le-xia-sheng-cheng-fo-jing-tang",
        "group": "mile",
        "total_juan": 1,
        "weight": 40,
        "summary": "佛说弥勒下生成佛经唐译本一卷。",
        "removable_titles": {"佛說彌勒下生成佛經"},
        "removable_bylines": {"唐三藏法師義淨奉制譯"},
    },
    "fo-shuo-mi-le-da-cheng-fo-jing": {
        "work": "T0456",
        "display_title": "佛说弥勒大成佛经",
        "tag": "佛说弥勒大成佛经",
        "slug": "fo-shuo-mi-le-da-cheng-fo-jing",
        "group": "mile",
        "total_juan": 1,
        "weight": 50,
        "summary": "佛说弥勒大成佛经一卷。",
        "removable_titles": {"佛說彌勒大成佛經"},
        "removable_bylines": {"姚秦龜茲國三藏鳩摩羅什譯"},
    },
    "fo-shuo-mi-le-lai-shi-jing": {
        "work": "T0457",
        "display_title": "佛说弥勒来时经",
        "tag": "佛说弥勒来时经",
        "slug": "fo-shuo-mi-le-lai-shi-jing",
        "group": "mile",
        "total_juan": 1,
        "weight": 60,
        "summary": "佛说弥勒来时经一卷。",
        "removable_titles": {"佛說彌勒來時經"},
        "removable_bylines": {"失譯人名附東晉錄"},
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
