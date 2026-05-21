#!/usr/bin/env python3
"""Generate 诸子百家 content from Wikisource.

Usage:
    python scripts/generate_zhuzi.py --all
    python scripts/generate_zhuzi.py --text xunzi
    python scripts/generate_zhuzi.py --list
"""

from __future__ import annotations

import argparse, json, re, sys, time, urllib.request, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext

ROOT = Path(__file__).resolve().parents[1]
ZHUZI_DIR = ROOT / "content" / "posts" / "zhuzi"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"

TEXTS: dict[str, dict] = {
    "xunzi":         {"slug": "xunzi", "title": "荀子", "wiki_title": "荀子", "type": "subpages", "wiki_prefix": "荀子/", "summary": "荀子三十二篇，战国荀况撰，儒家重要典籍。", "tags": ["荀子", "儒家", "诸子"]},
    "mozi":          {"slug": "mozi", "title": "墨子", "wiki_title": "墨子", "type": "subpages", "wiki_prefix": "墨子/", "summary": "墨子五十三篇，战国墨翟及其弟子撰，墨家经典。", "tags": ["墨子", "墨家", "诸子"]},
    "hanfeizi":      {"slug": "hanfeizi", "title": "韩非子", "wiki_title": "韓非子", "type": "subpages", "wiki_prefix": "韓非子/", "summary": "韩非子五十五篇，战国韩非撰，法家集大成之作。", "tags": ["韩非子", "法家", "诸子"]},
    "sunzi-bingfa":  {"slug": "sunzi-bingfa", "title": "孙子兵法", "wiki_title": "孫子兵法", "type": "single", "summary": "孙子兵法十三篇，春秋孙武撰，兵家经典。", "tags": ["孙子兵法", "兵家", "诸子"]},
    "shangjun-shu":  {"slug": "shangjun-shu", "title": "商君书", "wiki_title": "商君書", "type": "subpages", "wiki_prefix": "商君書/", "summary": "商君书二十六篇，战国商鞅及其后学撰，法家著作。", "tags": ["商君书", "法家", "诸子"]},
    "guiguzi":       {"slug": "guiguzi", "title": "鬼谷子", "wiki_title": "鬼谷子", "type": "subpages", "wiki_prefix": "鬼谷子/", "summary": "鬼谷子十四篇，传为战国鬼谷子撰，纵横家经典。", "tags": ["鬼谷子", "纵横家", "诸子"]},
    "lvshi-chunqiu": {"slug": "lvshi-chunqiu", "title": "吕氏春秋", "wiki_title": "呂氏春秋", "type": "subpages", "wiki_prefix": "呂氏春秋/", "summary": "吕氏春秋二十六卷，秦吕不韦编，杂家代表作。", "tags": ["吕氏春秋", "杂家", "诸子"]},
    "huainanzi":     {"slug": "huainanzi", "title": "淮南子", "wiki_title": "淮南子", "type": "subpages", "wiki_prefix": "淮南子/", "summary": "淮南子二十一卷，汉刘安编，杂家代表作。", "tags": ["淮南子", "杂家", "诸子"]},
    "gongsun-longzi":{"slug": "gongsun-longzi", "title": "公孙龙子", "wiki_title": "公孫龍子", "type": "subpages", "wiki_prefix": "公孫龍子/", "summary": "公孙龙子六篇，战国公孙龙撰，名家经典。", "tags": ["公孙龙子", "名家", "诸子"]},
    "wenzi":         {"slug": "wenzi", "title": "文子", "wiki_title": "文子", "type": "subpages", "wiki_prefix": "文子/", "summary": "文子十二卷，传为战国文子撰，道家经典。", "tags": ["文子", "道家", "诸子"]},
    "wuzi":          {"slug": "wuzi", "title": "吴子", "wiki_title": "吳子", "type": "single", "summary": "吴子六篇，战国吴起撰，兵家武经七书之一。", "tags": ["吴子", "兵家", "诸子"]},
    "sima-fa":       {"slug": "sima-fa", "title": "司马法", "wiki_title": "司馬法", "type": "single", "summary": "司马法五篇，传为司马穰苴撰，兵家武经七书之一。", "tags": ["司马法", "兵家", "诸子"]},
    "liu-tao":       {"slug": "liu-tao", "title": "六韬", "wiki_title": "六韜", "type": "single", "summary": "六韬六卷，传为姜太公撰，兵家武经七书之一。", "tags": ["六韬", "兵家", "诸子"]},
    "san-lue":       {"slug": "san-lue", "title": "三略", "wiki_title": "三略", "type": "single", "summary": "三略三卷，传为黄石公撰，兵家武经七书之一。", "tags": ["三略", "兵家", "诸子"]},
    "weiliaozi":     {"slug": "weiliaozi", "title": "尉缭子", "wiki_title": "尉繚子/全覽", "type": "single", "summary": "尉缭子二十四篇，战国尉缭撰，兵家武经七书之一。", "tags": ["尉缭子", "兵家", "诸子"]},
    "shishuo-xinyu": {"slug": "shishuo-xinyu", "title": "世说新语", "wiki_title": "世說新語", "type": "subpages", "wiki_prefix": "世說新語/", "summary": "世说新语三十六篇，南朝宋刘义庆编，志人小说集大成之作。", "tags": ["世说新语", "小说家", "诸子"]},
    "huangdi-neijing-suwen": {"slug": "huangdi-neijing-suwen", "title": "黄帝内经·素问", "wiki_title": "黃帝內經", "type": "subpages", "wiki_prefix": "黃帝內經/素問", "summary": "黄帝内经素问二十四卷，医家经典，中医理论奠基之作。", "tags": ["黄帝内经", "素问", "医家", "诸子"]},
    "huangdi-neijing-lingshu": {"slug": "huangdi-neijing-lingshu", "title": "黄帝内经·灵枢", "wiki_title": "黃帝內經", "type": "subpages", "wiki_prefix": "黃帝內經/靈樞", "summary": "黄帝内经灵枢十二卷，医家经典，针灸经络理论奠基之作。", "tags": ["黄帝内经", "灵枢", "医家", "诸子"]},
    "shanghan-lun": {"slug": "shanghan-lun", "title": "伤寒论", "wiki_title": "傷寒論", "type": "single", "summary": "伤寒论十卷，汉张仲景撰，辨证论治之祖，中医临床奠基之作。", "tags": ["伤寒论", "张仲景", "医家", "诸子"]},
    "jingui-yaolue": {"slug": "jingui-yaolue", "title": "金匮要略", "wiki_title": "金匱要略", "type": "single", "summary": "金匮要略三卷，汉张仲景撰，杂病证治之祖，方书之典范。", "tags": ["金匮要略", "张仲景", "医家", "诸子"]},
    "shanhai-jing":  {"slug": "shanhai-jing", "title": "山海经", "wiki_title": "山海經", "type": "subpages", "wiki_prefix": "山海經/", "summary": "山海经十八卷，先秦奇书，中国神话地理之源头。", "tags": ["山海经", "地理", "神话", "诸子"]},
}


PAGE_ORDERS: dict[str, list[str]] = {
    "xunzi": [
        "勸學篇", "修身篇", "不苟篇", "榮辱篇", "非相篇", "非十二子篇",
        "仲尼篇", "儒效篇", "王制篇", "富國篇", "王霸篇", "君道篇",
        "臣道篇", "致士篇", "議兵篇", "彊國篇", "天論篇", "正論篇",
        "禮論篇", "樂論篇", "解蔽篇", "正名篇", "性惡篇", "君子篇",
        "成相篇", "賦篇", "大略篇", "宥坐篇", "子道篇", "法行篇",
        "哀公篇", "堯問篇", "荀子序",
    ],
    "mozi": [
        "親士", "修身", "所染", "法儀", "七患", "辭過", "三辯",
        "尚賢上", "尚賢中", "尚賢下", "尚同上", "尚同中", "尚同下",
        "兼愛上", "兼愛中", "兼愛下", "非攻上", "非攻中", "非攻下",
        "節用上", "節用中", "節葬下", "天志上", "天志中", "天志下",
        "明鬼下", "非樂上", "非命上", "非命中", "非命下", "非儒下",
        "經上", "經下", "經說上", "經說下", "大取", "小取", "耕柱",
        "貴義", "公孟", "魯問", "公輸", "備城門", "備高臨", "備梯",
        "備水", "備突", "備穴", "備蛾傅", "迎敵祠", "旗幟", "號令",
        "雜守",
    ],
    "hanfeizi": [
        "初見秦", "存韓", "難言", "愛臣", "主道", "有度", "二柄",
        "揚權", "八姦", "十過", "孤憤", "說難", "和氏", "奸劫弑臣",
        "亡徵", "三守", "備內", "南面", "飾邪", "解老", "喻老",
        "說林上", "說林下", "觀行", "安危", "守道", "用人", "功名",
        "大體", "內儲說上七術", "內儲說下六微", "外儲說左上",
        "外儲說左下", "外儲說右上", "外儲說右下", "難一", "難二",
        "難三", "難四", "難勢", "問辯", "問田", "定法", "說疑",
        "詭使", "六反", "八說", "八經", "五蠹", "顯學", "忠孝",
        "人主", "飭令", "心度", "制分",
    ],
    "shangjun-shu": ["卷一", "卷二", "卷三", "卷四", "卷五"],
    "guiguzi": ["序", "卷01", "卷02", "卷03", "跋", "鬼谷子篇目考", "鬼谷子附録"],
    "lvshi-chunqiu": [
        "卷一", "卷二", "卷三", "卷四", "卷五", "卷六", "卷七",
        "卷八", "卷九", "卷十", "卷十一", "卷十二", "卷十三",
        "卷十四", "卷十五", "卷十六", "卷十七", "卷十八", "卷十九",
        "卷二十", "卷二十一", "卷二十二", "卷二十三", "卷二十四",
        "卷二十五", "卷二十六",
    ],
    "huainanzi": [
        "敘目", "原道訓", "俶真訓", "天文訓", "墜形訓", "時則訓",
        "覽冥訓", "精神訓", "本經訓", "主術訓", "繆稱訓", "齊俗訓",
        "道應訓", "氾論訓", "詮言訓", "兵略訓", "說山訓", "說林訓",
        "人間訓", "脩務訓", "泰族訓", "要略",
    ],
    "gongsun-longzi": ["原序", "1", "2", "3", "4", "5", "6"],
    "wenzi": [
        "卷一", "卷二", "卷三", "卷四", "卷五", "卷六",
        "卷七", "卷八", "卷九", "卷十", "卷十一", "卷十二",
    ],
    "shishuo-xinyu": [
        "序", "德行", "言語", "政事", "文學", "方正", "雅量", "識鑒",
        "賞譽", "品藻", "規箴", "捷悟", "夙惠", "豪爽", "容止",
        "自新", "企羡", "傷逝", "棲逸", "賢媛", "術解", "巧蓺",
        "寵禮", "任誕", "簡傲", "排調", "輕詆", "假譎", "黜免",
        "儉嗇", "汰侈", "忿狷", "讒險", "尤悔", "紕漏", "惑溺",
        "仇隟",
    ],
    "huangdi-neijing-suwen": [
        "第一卷", "第二卷", "第三卷", "第四卷", "第五卷", "第六卷",
        "第七卷", "第八卷", "第九卷", "第十卷", "第十一卷", "第十二卷",
        "第十三卷", "第十四卷", "第十五卷", "第十六卷", "第十七卷",
        "第十八卷", "第十九卷", "第二十卷", "第二十一卷", "第二十二卷",
        "第二十三卷", "第二十四卷",
    ],
    "huangdi-neijing-lingshu": [
        "第一卷", "第二卷", "第三卷", "第四卷", "第五卷", "第六卷",
        "第七卷", "第八卷", "第九卷", "第十卷", "第十一卷", "第十二卷",
    ],
    "shanhai-jing": [
        "郭璞序", "南山經", "西山經", "北山經", "東山經", "中山經",
        "海外南經", "海外西經", "海外北經", "海外東經", "海內南經",
        "海內西經", "海內北經", "海內東經", "大荒東經", "大荒南經",
        "大荒西經", "大荒北經", "海內經",
    ],
}


TITLE_OVERRIDES: dict[str, dict[str, str]] = {
    "gongsun-longzi": {
        "1": "跡府第一",
        "2": "白馬論第二",
        "3": "指物論第三",
        "4": "通變論第四",
        "5": "堅白論第五",
        "6": "名實論第六",
    },
    "lvshi-chunqiu": {
        "卷一": "卷一·孟春紀",
        "卷二": "卷二·仲春紀",
    },
}


EXCLUDED_PAGES: dict[str, set[str]] = {
    "mozi": {"全覽"},
    "hanfeizi": {
        "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
        "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
        "八奸", "忠考", "揚榷", "外儲說", "韓非子全文",
    },
    "huainanzi": {"墬形訓"},
    "shishuo-xinyu": {"全覽"},
}


CHINESE_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


def api_query(params: dict) -> dict:
    base = "https://zh.wikisource.org/w/api.php?format=json&"
    url = base + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def redirect_target(raw: str) -> str | None:
    match = re.match(r"#REDIRECT\s+(?:\[\[)?([^\]\n#]+)", raw.strip(), flags=re.I)
    if not match:
        return None
    return match.group(1).strip()


def fetch_raw(title: str, retries: int = 3, redirects: int = 3) -> str:
    url = "https://zh.wikisource.org/w/index.php?title={}&action=raw".format(urllib.parse.quote(title))
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8")
                target = redirect_target(raw)
                if target and redirects:
                    return fetch_raw(target, retries=retries, redirects=redirects - 1)
                return raw
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(5 * (attempt + 1))
            else:
                raise


def discover_subpages(prefix: str) -> list[str]:
    pages: list[str] = []
    params = {"action": "query", "list": "allpages", "apprefix": prefix, "aplimit": 500}
    while True:
        data = api_query(params)
        for p in data.get("query", {}).get("allpages", []):
            pages.append(p["title"])
        if "continue" in data:
            params.update(data["continue"])
        else:
            break
    return sorted(pages)


def chinese_number_value(text: str) -> int | None:
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total = 0
    section = 0
    number = 0
    for char in text:
        if char in CHINESE_DIGITS:
            number = CHINESE_DIGITS[char]
        elif char == "十":
            section += (number or 1) * 10
            number = 0
        elif char == "百":
            section += (number or 1) * 100
            number = 0
        else:
            return None
    total += section + number
    return total


def natural_page_key(page_title: str, prefix: str) -> tuple[int, int | str]:
    suffix = page_title.replace(prefix, "", 1)
    if suffix.isdigit():
        return (0, int(suffix))
    match = re.search(r"第?([零〇一二兩三四五六七八九十百]+)卷|卷([零〇一二兩三四五六七八九十百]+)", suffix)
    if match:
        value = chinese_number_value(match.group(1) or match.group(2))
        if value is not None:
            return (0, value)
    return (1, suffix)


def clean_existing_pages(out_dir: Path) -> None:
    for path in out_dir.glob("*.md"):
        if path.name != "_index.md":
            path.unlink()


def ordered_subpages(text_id: str, pages: list[str], prefix: str) -> list[str]:
    excluded = EXCLUDED_PAGES.get(text_id, set())
    filtered = [page for page in pages if page.replace(prefix, "", 1) not in excluded]

    order = PAGE_ORDERS.get(text_id)
    if not order:
        return sorted(filtered, key=lambda page: natural_page_key(page, prefix))

    by_suffix = {page.replace(prefix, "", 1): page for page in filtered}
    ordered: list[str] = []
    missing: list[str] = []
    for suffix in order:
        page = by_suffix.pop(suffix, None)
        if page is None:
            missing.append(suffix)
        else:
            ordered.append(page)

    if missing:
        print(f"  Missing expected pages: {', '.join(missing)}")
    if by_suffix:
        print(f"  Ignoring unexpected pages: {', '.join(sorted(by_suffix))}")
    return ordered


def final_clean(text: str) -> str:
    text = re.sub(r'</?onlyinclude>', '', text)
    text = re.sub(r'</?poem>', '', text)
    text = re.sub(r'^Category:.*$', '', text, flags=re.M)
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    text = text.replace('{{', '')
    text = text.replace('}}', '')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def front_matter(title: str, summary: str, weight: int,
                 tags: list[str] | None = None,
                 categories: list[str] | None = None) -> str:
    tags = tags or ["诸子"]
    categories = categories or ["子部", "诸子"]
    return f"""---
title: "{title}"
date: 2026-05-20
weight: {weight}
tags: {json.dumps(tags, ensure_ascii=False)}
categories: {json.dumps(categories, ensure_ascii=False)}
draft: false
summary: "{summary}"
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def write_index(directory: Path, title: str, summary: str, weight: int,
                tags: list[str] | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "_index.md").write_text(
        front_matter(title, summary, weight, tags, ["子部", "诸子"]), encoding="utf-8")


def write_page(path: Path, title: str, summary: str, weight: int,
               body: str, tags: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = front_matter(title, summary, weight, tags, ["子部", "诸子"])
    path.write_text(fm + body + "\n", encoding="utf-8")


def generate_subpages(text_id: str, dry_run: bool = False) -> tuple[int, int]:
    info = TEXTS[text_id]
    out_dir = ZHUZI_DIR / info["slug"]
    prefix = info["wiki_prefix"]
    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']}) -> {out_dir.relative_to(ROOT)}")
    pages = ordered_subpages(text_id, discover_subpages(prefix), prefix)
    print(f"  Found {len(pages)} sub-pages")
    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])
        clean_existing_pages(out_dir)
    success, fail = 0, 0
    for i, page_title in enumerate(pages, start=1):
        chapter_name = page_title.replace(prefix, "")
        chapter_name = TITLE_OVERRIDES.get(text_id, {}).get(chapter_name, chapter_name)
        out_file = out_dir / f"{info['slug']}-{i:03d}.md"
        try:
            raw = fetch_raw(page_title)
            body = final_clean(clean_wikitext(raw))
            if not body.strip():
                fail += 1; continue
            if not dry_run:
                write_page(out_file, chapter_name, f"{info['title']}：{chapter_name}", i, body, info["tags"])
            print(f"  [{i:03d}/{len(pages)}] {chapter_name} ({len(body)} chars)")
            success += 1; time.sleep(1)
        except Exception as e:
            print(f"  [{i:03d}/{len(pages)}] {chapter_name}: FAILED ({e})")
            fail += 1
    print(f"  Done: {success} ok, {fail} fail")
    return success, fail


def generate_single(text_id: str, dry_run: bool = False) -> tuple[int, int]:
    info = TEXTS[text_id]
    out_dir = ZHUZI_DIR / info["slug"]
    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['wiki_title']}) -> {out_dir.relative_to(ROOT)}")
    raw = fetch_raw(info["wiki_title"])
    body = final_clean(clean_wikitext(raw))
    out_file = out_dir / f"{info['slug']}.md"
    if not dry_run:
        write_index(out_dir, info["title"], info["summary"], 10, info["tags"])
        clean_existing_pages(out_dir)
        write_page(out_file, info["title"], info["summary"], 1, body, info["tags"])
    print(f"  OK ({len(body)} chars)")
    return 1, 0


def _make_gen(tid):
    if TEXTS[tid]["type"] == "subpages":
        return lambda dry_run=False: generate_subpages(tid, dry_run)
    return lambda dry_run=False: generate_single(tid, dry_run)

GENERATORS = {k: _make_gen(k) for k in TEXTS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="Single text by id")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.list:
        for tid, info in TEXTS.items():
            print(f"  {tid:20s} {info['title']:8s} [{info['type']:10s}]")
        return
    if args.text:
        gen = GENERATORS.get(args.text)
        if not gen: return print(f"Unknown: {args.text}")
        gen(dry_run=args.dry_run)
    elif args.all:
        ok = fail = 0
        for tid in TEXTS:
            o, f = GENERATORS[tid](dry_run=args.dry_run)
            ok += o; fail += f
        print(f"\n{'='*60}\nALL DONE: {ok} ok, {fail} fail")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
