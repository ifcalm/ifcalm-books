#!/usr/bin/env python3
"""Generate Daoist immortal-biography texts from Wikisource pages.

The generated pages are checked against CText/Kanripo table-of-contents data in
the script constants before writing, so obvious omissions surface early.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMMORTALS_DIR = ROOT / "content" / "posts" / "taoism" / "immortals"
SHENXIAN_DIR = IMMORTALS_DIR / "shenxian-zhuan"
XUXIAN_DIR = IMMORTALS_DIR / "xuxian-zhuan"
YONGCHENG_DIR = IMMORTALS_DIR / "yongcheng-jixian-lu"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"

SHENXIAN_VOLUME_NUMERALS = [
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
]

ARABIC_TO_CHINESE_NUMERAL = {
    1: "一",
    2: "二",
    3: "三",
    4: "四",
    5: "五",
    6: "六",
    7: "七",
    8: "八",
    9: "九",
    10: "十",
}

SHENXIAN_EXPECTED_HEADINGS = {
    "一": ["廣成子", "若士", "沈文泰", "彭祖", "白石生", "黃山君", "鳳綱"],
    "二": ["皇初平", "呂恭", "沈建", "華子期", "樂子長", "衛叔卿", "魏伯陽"],
    "三": ["沈羲", "陳世安", "李八伯", "李阿", "王遠", "伯山甫"],
    "四": [
        "墨子",
        "劉政",
        "孫博",
        "班孟",
        "玉子",
        "天門子",
        "九靈子",
        "北極子",
        "絕洞子",
        "太陽子",
        "太陽女",
        "太陰女",
        "太玄女",
        "南極子",
        "黃盧子",
    ],
    "五": ["馬鳴生", "陰長生", "茅君", "張道陵", "欒巴"],
    "六": [
        "淮南王",
        "李少君",
        "王真",
        "陳長",
        "劉綱",
        "樊夫人",
        "東陵聖母",
        "孔元",
        "王烈",
        "涉正",
        "焦先",
        "孫登",
    ],
    "七": [
        "東郭延",
        "靈壽光",
        "劉京",
        "嚴青",
        "帛和",
        "趙瞿",
        "宮嵩",
        "容成公",
        "董仲君",
        "倩平吉",
        "王仲都",
        "程偉妻",
        "薊子訓",
    ],
    "八": ["葛玄", "左慈", "王遙", "陳永伯", "太山老父", "巫炎", "河上公", "劉根"],
    "九": ["壺公", "尹軌", "介象"],
    "十": ["董奉", "李根", "李意期", "王興", "黃敬", "魯女生", "甘始", "封君達"],
}

YONGCHENG_EXPECTED_HEADINGS = {
    "01": ["聖母元君", "金母元君"],
    "02": ["上元夫人", "昭靈李夫人", "三元馮夫人", "南極王夫人"],
    "03": ["雲華夫人", "太微玄清左夫人", "東華上房靈妃", "紫微王夫人"],
    "04": ["太真夫人", "麻姑"],
    "05": ["雲林右英夫人", "嬰母", "鉤弋夫人", "湘江二妃", "洛川宓妃", "陽都女", "杜蘭香"],
    "06": [
        "盱母",
        "九天玄女",
        "孫夫人",
        "蠶女",
        "彭女",
        "弄玉",
        "園客妻",
        "昌容",
        "漢中酒婦",
        "女幾",
        "河間王女",
        "采女",
        "太陽女",
        "太陰女",
        "太玄女",
        "樊夫人",
        "東陵聖母",
        "西河少女",
    ],
    "07": [
        "梁母",
        "鮑姑",
        "孫寒華",
        "李奚子",
        "韓西華",
        "竇瓊英",
        "劉春龍",
        "趙素臺",
        "傅禮和",
        "黃景華",
        "張微子",
        "丁淑英",
        "王法進",
        "王氏",
        "花姑",
        "徐仙姑",
        "緱仙姑",
        "廣陵茶姥",
    ],
    "08": ["南溟夫人", "邊洞玄", "黃觀福", "陽平治", "神姑", "王奉仙", "薛玄同"],
    "09": [
        "魏夫人",
        "明星玉女",
        "南陽公主",
        "程偉妻",
        "張玉蘭",
        "王妙想",
        "成公智瓊",
        "龐女",
        "褒女",
        "李真多",
        "魯妙典",
    ],
    "10": ["驪山姥", "楊正見", "董上仙", "謝自然", "戚玄符", "王氏女", "周爰友", "太玄玉女", "薛女真", "玉姜", "江妃二女"],
}

XUXIAN_EXPECTED_HEADINGS = {
    "上": [
        "玄真子",
        "藍釆和",
        "朱孺子",
        "宜君王老",
        "侯道華",
        "馬自然",
        "鄔通微",
        "許磧",
        "金可記",
        "宋玄白",
        "賀自真",
        "賣藥翁",
        "鄧去奢",
        "謝自然",
        "裴玄靜",
        "戚逍遙",
    ],
    "中": [
        "孫思邈",
        "張果",
        "許宣平",
        "劉商",
        "劉譜",
        "羅萬象",
        "李玨",
        "王可交",
        "李昇",
        "葉千韶",
        "徐釣者",
        "錢朗",
    ],
    "下": ["司馬承禎", "曹德休", "閭丘方遠", "聶師道", "殷文祥", "譚峭", "杜昇", "羊愔"],
}

DONGXIAN_EXPECTED_HEADINGS = [
    "元君",
    "九元子",
    "長桑公子",
    "龔仲陽",
    "上黃先生",
    "蒲先生",
    "茅蒙",
    "常生子",
    "長存子",
    "蔡瓊",
    "張穆子",
    "童子先生",
    "九源丈人",
    "穀希子",
    "王仲高",
    "陽生",
    "西門君惠",
    "玄都先生",
    "黃列子",
    "公孫卿",
    "蔡長孺",
    "延明子高",
    "崔野子",
    "靈子真",
    "宛丘先生",
    "馬榮",
    "任敦",
    "敬玄子",
    "帛舉",
    "徐道季",
    "趙叔期",
    "毛伯道",
    "莊伯微",
    "劉道偉",
    "匡俗",
    "盧耽",
    "範豺",
    "傅先生",
    "石坦",
    "鄭思遠",
    "郭志生",
    "介琰",
    "徐福",
    "車子侯",
    "蘇耽",
    "張巨君",
    "馮伯達",
    "韓越",
    "郭璞",
    "戴孟",
    "郭文舉",
    "姚光",
    "徐彎",
    "丁令威",
    "王嘉",
    "寇謙之",
    "董幼",
    "劉丱",
    "王質",
]


def request_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_wikisource_pages(titles: list[str]) -> dict[str, str]:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "revisions",
            "titles": "|".join(titles),
            "rvprop": "content",
            "format": "json",
            "formatversion": "2",
        }
    )
    data = request_json(f"https://zh.wikisource.org/w/api.php?{params}")
    pages: dict[str, str] = {}
    for page in data["query"]["pages"]:
        content = page.get("revisions", [{"content": ""}])[0]["content"]
        pages[page["title"]] = content
    missing = [title for title in titles if not pages.get(title)]
    if missing:
        raise RuntimeError(f"missing Wikisource pages: {', '.join(missing)}")
    return pages


def strip_balanced_template(text: str, template_name: str | None = None) -> str:
    pattern = "{{" + (template_name or "")
    while pattern in text:
        start = text.index(pattern)
        depth = 0
        end = None
        for i in range(start, len(text) - 1):
            pair = text[i : i + 2]
            if pair == "{{":
                depth += 1
            elif pair == "}}":
                depth -= 1
                if depth == 0:
                    end = i + 2
                    break
        if end is None:
            break
        text = text[:start] + text[end:]
    return text


def normalize_blank_lines(text: str) -> str:
    text = text.replace("\u3000", "").replace("\u200b", "")
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_wikitext(text: str) -> str:
    for template in [
        "Header",
        "header",
        "PD-old",
        "檢索",
        "SKQS header",
        "SKQS read all header",
        "SKQS read all footer",
    ]:
        text = strip_balanced_template(text, template)
    def pua_repl(match: re.Match[str]) -> str:
        value = match.group(1)
        if any("\ue000" <= char <= "\uf8ff" for char in value):
            return "□"
        return value

    text = re.sub(r"\{\{PUA\|([^{}]*)\}\}", pua_repl, text)
    text = re.sub(r"\{\{SK notes\|([^{}]*)\}\}", r"\1", text)
    text = re.sub(r"\{\{SK anchor\|([^{}]*)\}\}", r"==\1==", text)
    text = re.sub(r"\{\{YL\|([^{}]*)\}\}", r"\1", text)
    text = text.replace("{{SKchar|3575}}", "葛")
    text = text.replace("{{SKchar|3429}}", "補")
    text = text.replace("{{SKchar|3435}}", "復")
    text = text.replace("{{SKchar|3752}}", "選")
    text = text.replace("{{SKchar|3932}}", "鬼")
    text = text.replace("{{SKchar|3814}}", "太")
    text = text.replace("{{SKchar|1841}}", "龜")
    text = text.replace("{{SKchar|2641}}", "寄")
    text = text.replace("{{SKchar|3946}}", "錫")
    text = re.sub(r"\{\{[^{}]+\}\}", "", text)
    text = text.replace("__TOC__", "")
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"</?poem>", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*/)?([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^|\]]+)\]\]", r"\1", text)
    text = re.sub(r"-\{([^{}]+)\}-", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"#\d+", "", text)
    text = re.sub(r"^續仙傳卷[上中下]竟$", "", text, flags=re.M)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    return normalize_blank_lines(text)


def convert_headings(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        marks, title = match.group(1), match.group(2).strip()
        level = "#" * (len(marks) + 1)
        return f"{level} {title}"

    return re.sub(r"^(={2,4})\s*(.*?)\s*\1$", repl, text, flags=re.M)


def apply_collation_notes(title: str, text: str) -> str:
    """Apply small readings confirmed against the Siku/Kanripo base edition."""
    if title == "神仙傳/卷二":
        text = text.replace("皇初平者，但谿人也。", "皇初平者，丹谿人也。")
    return text


def headings(text: str) -> list[str]:
    return [
        match.group(2).strip()
        for match in re.finditer(r"^(={2,4})\s*(.*?)\s*\1$", text, flags=re.M)
        if match.group(2).strip()
    ]


def section_headings(text: str, marks: str) -> list[str]:
    pattern = rf"^({re.escape(marks)})\s*(.*?)\s*\1$"
    return [
        match.group(2).strip()
        for match in re.finditer(pattern, text, flags=re.M)
        if match.group(2).strip()
    ]


def front_matter(
    title: str,
    summary: str,
    weight: int,
    tags: list[str] | None = None,
    show_toc: bool = True,
) -> str:
    tag_values = tags or ["道家", "仙传"]
    tag_text = ", ".join(f'"{tag}"' for tag in tag_values)
    toc = "true" if show_toc else "false"
    return f"""---
title: "{title}"
date: 2026-05-14
weight: {weight}
tags: [{tag_text}]
draft: false
summary: "{summary}"
showToc: {toc}
tocOpen: false
ShowShareButtons: false
---
"""


def write_page(
    path: Path,
    title: str,
    summary: str,
    weight: int,
    body: str,
    tags: list[str] | None = None,
    show_toc: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(title, summary, weight, tags, show_toc) + "\n" + body.strip() + "\n",
        encoding="utf-8",
    )


def write_category_index() -> None:
    write_page(
        IMMORTALS_DIR / "_index.md",
        "仙传",
        "仙真传记、神仙谱录与道教人物传记。",
        60,
        "收录仙真传记、神仙谱录与道教人物传记。",
        show_toc=False,
    )


def write_liexian(raw: str) -> None:
    raw_headings = headings(raw)
    if len(raw_headings) != 71 or raw_headings[-1] != "贊":
        raise RuntimeError(f"unexpected Liexian heading set: {len(raw_headings)} headings")
    body = convert_headings(clean_wikitext(raw))
    write_page(
        IMMORTALS_DIR / "liexian-zhuan.md",
        "列仙传",
        "赤松子者，神农时雨师也。",
        10,
        body,
        tags=["道家", "仙传", "列仙传"],
    )


def shenxian_preface(raw: str) -> str:
    cleaned = clean_wikitext(raw)
    match = re.search(r"==序==\s*(.*?)\s*==目錄==", cleaned, flags=re.S)
    if not match:
        raise RuntimeError("could not extract Shenxian preface")
    return convert_headings("==序==\n" + match.group(1).strip())


def write_shenxian_index() -> None:
    write_page(
        SHENXIAN_DIR / "_index.md",
        "神仙传",
        "晋葛洪撰，十卷，记神仙人物传记。",
        20,
        "《神仙传》晋葛洪撰，按序与十卷分篇收录。",
        tags=["道家", "仙传", "神仙传"],
        show_toc=False,
    )


def write_shenxian(raw_pages: dict[str, str]) -> None:
    write_shenxian_index()
    write_page(
        SHENXIAN_DIR / "00-preface.md",
        "神仙传 序",
        "洪著内篇，论神仙之事，凡二十卷。",
        1,
        shenxian_preface(raw_pages["神仙傳"]),
        tags=["道家", "仙传", "神仙传"],
    )
    for index, numeral in enumerate(SHENXIAN_VOLUME_NUMERALS, 1):
        title = f"神仙傳/卷{numeral}"
        raw = raw_pages[title]
        raw_headings = headings(raw)
        expected = SHENXIAN_EXPECTED_HEADINGS[numeral]
        if raw_headings != expected:
            raise RuntimeError(f"unexpected Shenxian headings in 卷{numeral}: {raw_headings}")
        body = convert_headings(apply_collation_notes(title, clean_wikitext(raw)))
        write_page(
            SHENXIAN_DIR / f"{index:02d}.md",
            f"神仙传 卷{numeral}",
            f"神仙传卷{numeral}。",
            index + 1,
            body,
            tags=["道家", "仙传", "神仙传"],
        )


def write_xuxian_index() -> None:
    write_page(
        XUXIAN_DIR / "_index.md",
        "续仙传",
        "唐沈汾撰，三卷，续记神仙传记。",
        25,
        "《续仙传》唐沈汾撰，按上、中、下三卷分篇收录。",
        tags=["道家", "仙传", "续仙传"],
        show_toc=False,
    )


def xuxian_volume_body(raw: str, volume: str) -> str:
    next_volume = {"上": "中", "中": "下", "下": None}[volume]
    start = f"==續仙傳卷{volume}=="
    if next_volume:
        end = f"==續仙傳卷{next_volume}=="
        match = re.search(rf"{re.escape(start)}(.*?){re.escape(end)}", raw, flags=re.S)
    else:
        match = re.search(rf"{re.escape(start)}(.*)", raw, flags=re.S)
    if not match:
        raise RuntimeError(f"could not extract 續仙傳卷{volume}")
    body = match.group(1).split(f"續仙傳卷{volume}竟", 1)[0]
    body = re.sub(r"\n\s*宜君王老\s*\n\s*王老", "\n===宜君王老===\n王老", body)
    body = clean_wikitext(body)
    body = re.sub(r"^===\s*(.*?)\s*===$", r"==\1==", body, flags=re.M)
    return convert_headings(body)


def write_xuxian(raw: str) -> None:
    write_xuxian_index()
    for index, volume in enumerate(["上", "中", "下"], 1):
        body = xuxian_volume_body(raw, volume)
        local_headings = re.findall(r"^###\s+(.+)$", body, flags=re.M)
        expected = XUXIAN_EXPECTED_HEADINGS[volume]
        if local_headings != expected:
            raise RuntimeError(f"unexpected 續仙傳卷{volume} headings: {local_headings}")
        write_page(
            XUXIAN_DIR / f"{index:02d}.md",
            f"续仙传 卷{volume}",
            f"续仙传卷{volume}。",
            index,
            body,
            tags=["道家", "仙传", "续仙传"],
        )


def write_yongcheng_index() -> None:
    write_page(
        YONGCHENG_DIR / "_index.md",
        "墉城集仙录",
        "唐杜光庭集，记古今女仙得道升仙事。",
        30,
        "《墉城集仙录》唐杜光庭集，按序与十卷分篇收录。",
        tags=["道家", "仙传", "墉城集仙录"],
        show_toc=False,
    )


def write_yongcheng(raw_pages: dict[str, str]) -> None:
    write_yongcheng_index()
    write_page(
        YONGCHENG_DIR / "00-preface.md",
        "墉城集仙录 序",
        "纪古今女子得道升仙之事也。",
        1,
        clean_wikitext(raw_pages["墉城集仙錄序"]),
        tags=["道家", "仙传", "墉城集仙录"],
    )
    for index in range(1, 11):
        number = f"{index:02d}"
        title = f"墉城集仙錄/卷{number}"
        raw = raw_pages[title]
        raw_headings = headings(raw)
        expected = YONGCHENG_EXPECTED_HEADINGS[number]
        if raw_headings != expected:
            raise RuntimeError(f"unexpected Yongcheng headings in 卷{number}: {raw_headings}")
        body = convert_headings(clean_wikitext(raw))
        numeral = ARABIC_TO_CHINESE_NUMERAL[index]
        write_page(
            YONGCHENG_DIR / f"{number}.md",
            f"墉城集仙录 卷{numeral}",
            f"墉城集仙录卷{numeral}。",
            index + 1,
            body,
            tags=["道家", "仙传", "墉城集仙录"],
        )


def write_dongxian(raw: str) -> None:
    raw_headings = headings(raw)
    if raw_headings != DONGXIAN_EXPECTED_HEADINGS:
        raise RuntimeError(f"unexpected 洞仙傳 headings: {raw_headings}")
    body = clean_wikitext(raw)
    body = body.replace("○洞仙傳", "").strip()
    body = convert_headings(body)
    write_page(
        IMMORTALS_DIR / "dongxian-zhuan.md",
        "洞仙传",
        "《洞仙传》佚文，今据《云笈七签》卷一百一十所载收录。",
        40,
        body,
        tags=["道家", "仙传", "洞仙传"],
    )


def main() -> None:
    titles = ["列仙傳", "神仙傳"] + [
        f"神仙傳/卷{numeral}" for numeral in SHENXIAN_VOLUME_NUMERALS
    ] + ["續仙傳", "雲笈七籤/110", "墉城集仙錄序"] + [
        f"墉城集仙錄/卷{index:02d}" for index in range(1, 11)
    ]
    pages = fetch_wikisource_pages(titles)
    write_category_index()
    write_liexian(pages["列仙傳"])
    write_shenxian(pages)
    write_xuxian(pages["續仙傳"])
    write_yongcheng(pages)
    write_dongxian(pages["雲笈七籤/110"])


if __name__ == "__main__":
    main()
