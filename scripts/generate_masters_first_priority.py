#!/usr/bin/env python3
"""Generate the first priority 子部 works from Wikisource.

This batch collects:

* 荀子: 荀子序 plus the received 32 chapters.
* 墨子: the 53 extant chapters listed on Wikisource.
* 韩非子: the received 55 chapters, excluding wrapper and duplicate pages.

Wikisource is used as the structured primary source; CText pages are retained as
the proofreading references in this script's source metadata.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext, remove_balanced


ROOT = Path(__file__).resolve().parents[1]
MASTERS_DIR = ROOT / "content" / "posts" / "masters"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
CONTENT_DATE = "2026-06-19"
FETCH_DELAY = 0.05


@dataclass(frozen=True)
class Chapter:
    wiki_suffix: str
    title: str
    slug: str


@dataclass(frozen=True)
class Work:
    key: str
    title: str
    slug: str
    summary: str
    wiki_base: str
    primary_url: str
    proofreading_url: str
    weight: int
    chapters: tuple[Chapter, ...]


XUNZI_CHAPTERS = (
    Chapter("荀子序", "荀子序", "xunzi-xu"),
    Chapter("勸學篇", "勸學篇", "quan-xue"),
    Chapter("修身篇", "修身篇", "xiu-shen"),
    Chapter("不苟篇", "不苟篇", "bu-gou"),
    Chapter("榮辱篇", "榮辱篇", "rong-ru"),
    Chapter("非相篇", "非相篇", "fei-xiang"),
    Chapter("非十二子篇", "非十二子篇", "fei-shi-er-zi"),
    Chapter("仲尼篇", "仲尼篇", "zhong-ni"),
    Chapter("儒效篇", "儒效篇", "ru-xiao"),
    Chapter("王制篇", "王制篇", "wang-zhi"),
    Chapter("富國篇", "富國篇", "fu-guo"),
    Chapter("王霸篇", "王霸篇", "wang-ba"),
    Chapter("君道篇", "君道篇", "jun-dao"),
    Chapter("臣道篇", "臣道篇", "chen-dao"),
    Chapter("致士篇", "致士篇", "zhi-shi"),
    Chapter("議兵篇", "議兵篇", "yi-bing"),
    Chapter("彊國篇", "彊國篇", "qiang-guo"),
    Chapter("天論篇", "天論篇", "tian-lun"),
    Chapter("正論篇", "正論篇", "zheng-lun"),
    Chapter("禮論篇", "禮論篇", "li-lun"),
    Chapter("樂論篇", "樂論篇", "yue-lun"),
    Chapter("解蔽篇", "解蔽篇", "jie-bi"),
    Chapter("正名篇", "正名篇", "zheng-ming"),
    Chapter("性惡篇", "性惡篇", "xing-e"),
    Chapter("君子篇", "君子篇", "jun-zi"),
    Chapter("成相篇", "成相篇", "cheng-xiang"),
    Chapter("賦篇", "賦篇", "fu"),
    Chapter("大略篇", "大略篇", "da-lue"),
    Chapter("宥坐篇", "宥坐篇", "you-zuo"),
    Chapter("子道篇", "子道篇", "zi-dao"),
    Chapter("法行篇", "法行篇", "fa-xing"),
    Chapter("哀公篇", "哀公篇", "ai-gong"),
    Chapter("堯問篇", "堯問篇", "yao-wen"),
)


MOZI_CHAPTERS = (
    Chapter("親士", "親士", "qin-shi"),
    Chapter("修身", "修身", "xiu-shen"),
    Chapter("所染", "所染", "suo-ran"),
    Chapter("法儀", "法儀", "fa-yi"),
    Chapter("七患", "七患", "qi-huan"),
    Chapter("辭過", "辭過", "ci-guo"),
    Chapter("三辯", "三辯", "san-bian"),
    Chapter("尚賢上", "尚賢上", "shang-xian-shang"),
    Chapter("尚賢中", "尚賢中", "shang-xian-zhong"),
    Chapter("尚賢下", "尚賢下", "shang-xian-xia"),
    Chapter("尚同上", "尚同上", "shang-tong-shang"),
    Chapter("尚同中", "尚同中", "shang-tong-zhong"),
    Chapter("尚同下", "尚同下", "shang-tong-xia"),
    Chapter("兼愛上", "兼愛上", "jian-ai-shang"),
    Chapter("兼愛中", "兼愛中", "jian-ai-zhong"),
    Chapter("兼愛下", "兼愛下", "jian-ai-xia"),
    Chapter("非攻上", "非攻上", "fei-gong-shang"),
    Chapter("非攻中", "非攻中", "fei-gong-zhong"),
    Chapter("非攻下", "非攻下", "fei-gong-xia"),
    Chapter("節用上", "節用上", "jie-yong-shang"),
    Chapter("節用中", "節用中", "jie-yong-zhong"),
    Chapter("節葬下", "節葬下", "jie-zang-xia"),
    Chapter("天志上", "天志上", "tian-zhi-shang"),
    Chapter("天志中", "天志中", "tian-zhi-zhong"),
    Chapter("天志下", "天志下", "tian-zhi-xia"),
    Chapter("明鬼下", "明鬼下", "ming-gui-xia"),
    Chapter("非樂上", "非樂上", "fei-yue-shang"),
    Chapter("非命上", "非命上", "fei-ming-shang"),
    Chapter("非命中", "非命中", "fei-ming-zhong"),
    Chapter("非命下", "非命下", "fei-ming-xia"),
    Chapter("非儒下", "非儒下", "fei-ru-xia"),
    Chapter("經上", "經上", "jing-shang"),
    Chapter("經下", "經下", "jing-xia"),
    Chapter("經說上", "經說上", "jing-shuo-shang"),
    Chapter("經說下", "經說下", "jing-shuo-xia"),
    Chapter("大取", "大取", "da-qu"),
    Chapter("小取", "小取", "xiao-qu"),
    Chapter("耕柱", "耕柱", "geng-zhu"),
    Chapter("貴義", "貴義", "gui-yi"),
    Chapter("公孟", "公孟", "gong-meng"),
    Chapter("魯問", "魯問", "lu-wen"),
    Chapter("公輸", "公輸", "gong-shu"),
    Chapter("備城門", "備城門", "bei-cheng-men"),
    Chapter("備高臨", "備高臨", "bei-gao-lin"),
    Chapter("備梯", "備梯", "bei-ti"),
    Chapter("備水", "備水", "bei-shui"),
    Chapter("備突", "備突", "bei-tu"),
    Chapter("備穴", "備穴", "bei-xue"),
    Chapter("備蛾傅", "備蛾傅", "bei-e-fu"),
    Chapter("迎敵祠", "迎敵祠", "ying-di-ci"),
    Chapter("旗幟", "旗幟", "qi-zhi"),
    Chapter("號令", "號令", "hao-ling"),
    Chapter("雜守", "雜守", "za-shou"),
)


HANFEIZI_CHAPTERS = (
    Chapter("初見秦", "初見秦", "chu-jian-qin"),
    Chapter("存韓", "存韓", "cun-han"),
    Chapter("難言", "難言", "nan-yan"),
    Chapter("愛臣", "愛臣", "ai-chen"),
    Chapter("主道", "主道", "zhu-dao"),
    Chapter("有度", "有度", "you-du"),
    Chapter("二柄", "二柄", "er-bing"),
    Chapter("揚權", "揚權", "yang-quan"),
    Chapter("八姦", "八姦", "ba-jian"),
    Chapter("十過", "十過", "shi-guo"),
    Chapter("孤憤", "孤憤", "gu-fen"),
    Chapter("說難", "說難", "shuo-nan"),
    Chapter("和氏", "和氏", "he-shi"),
    Chapter("奸劫弑臣", "奸劫弑臣", "jian-jie-shi-chen"),
    Chapter("亡徵", "亡徵", "wang-zheng"),
    Chapter("三守", "三守", "san-shou"),
    Chapter("備內", "備內", "bei-nei"),
    Chapter("南面", "南面", "nan-mian"),
    Chapter("飾邪", "飾邪", "shi-xie"),
    Chapter("解老", "解老", "jie-lao"),
    Chapter("喻老", "喻老", "yu-lao"),
    Chapter("說林上", "說林上", "shuo-lin-shang"),
    Chapter("說林下", "說林下", "shuo-lin-xia"),
    Chapter("觀行", "觀行", "guan-xing"),
    Chapter("安危", "安危", "an-wei"),
    Chapter("守道", "守道", "shou-dao"),
    Chapter("用人", "用人", "yong-ren"),
    Chapter("功名", "功名", "gong-ming"),
    Chapter("大體", "大體", "da-ti"),
    Chapter("內儲說上七術", "內儲說上七術", "nei-chu-shuo-shang-qi-shu"),
    Chapter("內儲說下六微", "內儲說下六微", "nei-chu-shuo-xia-liu-wei"),
    Chapter("外儲說左上", "外儲說左上", "wai-chu-shuo-zuo-shang"),
    Chapter("外儲說左下", "外儲說左下", "wai-chu-shuo-zuo-xia"),
    Chapter("外儲說右上", "外儲說右上", "wai-chu-shuo-you-shang"),
    Chapter("外儲說右下", "外儲說右下", "wai-chu-shuo-you-xia"),
    Chapter("難一", "難一", "nan-yi"),
    Chapter("難二", "難二", "nan-er"),
    Chapter("難三", "難三", "nan-san"),
    Chapter("難四", "難四", "nan-si"),
    Chapter("難勢", "難勢", "nan-shi"),
    Chapter("問辯", "問辯", "wen-bian"),
    Chapter("問田", "問田", "wen-tian"),
    Chapter("定法", "定法", "ding-fa"),
    Chapter("說疑", "說疑", "shuo-yi"),
    Chapter("詭使", "詭使", "gui-shi"),
    Chapter("六反", "六反", "liu-fan"),
    Chapter("八說", "八說", "ba-shuo"),
    Chapter("八經", "八經", "ba-jing"),
    Chapter("五蠹", "五蠹", "wu-du"),
    Chapter("顯學", "顯學", "xian-xue"),
    Chapter("忠孝", "忠孝", "zhong-xiao"),
    Chapter("人主", "人主", "ren-zhu"),
    Chapter("飭令", "飭令", "chi-ling"),
    Chapter("心度", "心度", "xin-du"),
    Chapter("制分", "制分", "zhi-fen"),
)


WORKS = {
    "xunzi": Work(
        "xunzi",
        "荀子",
        "xunzi",
        "荀子三十二篇，战国荀况撰，儒家重要典籍。",
        "荀子",
        "https://zh.wikisource.org/wiki/荀子",
        "https://ctext.org/xunzi/zh",
        1,
        XUNZI_CHAPTERS,
    ),
    "mozi": Work(
        "mozi",
        "墨子",
        "mozi",
        "墨子现存五十三篇，墨家经典。",
        "墨子",
        "https://zh.wikisource.org/wiki/墨子",
        "https://ctext.org/mozi/zh",
        2,
        MOZI_CHAPTERS,
    ),
    "hanfeizi": Work(
        "hanfeizi",
        "韩非子",
        "hanfeizi",
        "韩非子五十五篇，法家集大成之作。",
        "韓非子",
        "https://zh.wikisource.org/wiki/韓非子",
        "https://ctext.org/hanfeizi/zh",
        3,
        HANFEIZI_CHAPTERS,
    ),
}


def dump_yaml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(title: str, summary: str, weight: int, tag: str, *, draft: bool) -> str:
    return f"""---
title: {dump_yaml(title)}
date: {CONTENT_DATE}
weight: {weight}
tags: {json.dumps([tag], ensure_ascii=False)}
draft: {"true" if draft else "false"}
summary: {dump_yaml(summary)}
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def fetch_raw(title: str) -> str:
    query = urllib.parse.quote(title)
    url = f"https://zh.wikisource.org/w/index.php?title={query}&action=raw"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def strip_notes(raw: str) -> str:
    text = raw
    text = re.sub(r"\{\{[Tt]extquality\|[^{}]*\}\}", "", text)
    text = re.sub(r"^\[\[Category:[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"^\[\[[a-z][a-z-]{1,12}:[^\n]*$", "", text, flags=re.M)
    for name in ("header2", "Header2", "header", "Header", "footer", "Footer"):
        while "{{" + name in text:
            next_text = remove_balanced(text, "{{" + name, "}}")
            if next_text == text:
                break
            text = next_text
    while "{{*|" in text:
        next_text = remove_balanced(text, "{{*|", "}}")
        if next_text == text:
            break
        text = next_text
    text = re.sub(r"\{\{另\|([^|}]+)\|[^}]+\}\}", r"\1", text)
    return text


def clean_body(raw: str) -> str:
    text = strip_notes(raw)
    text = clean_wikitext(text)
    text = re.sub(r"</?onlyinclude>", "", text)
    text = re.sub(r"</?poem>", "", text)
    text = re.sub(r"</?[a-zA-Z][^>\n]*>", "", text)
    text = re.sub(r"^Category:.*$", "", text, flags=re.M)
    text = re.sub(r"^\[\[[a-z][a-z-]{1,12}:.*$", "", text, flags=re.M)
    text = re.sub(r"^[a-z][a-z-]{1,12}:[^\n]*$", "", text, flags=re.M)
    text = re.sub(r"\{\{[^}]+\}\}", "", text)
    text = text.replace("{{", "").replace("}}", "")
    lines = [line.strip() for line in text.splitlines()]
    kept: list[str] = []
    for line in lines:
        if not line:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if line.startswith(("Gototop", "Footer", "Header", "Textquality", "textquality")):
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def write_index(path: Path, title: str, summary: str, weight: int, tag: str, body: str = "") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "_index.md").write_text(
        front_matter(title, summary, weight, tag, draft=True) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def write_page(path: Path, title: str, summary: str, weight: int, tag: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        front_matter(title, summary, weight, tag, draft=False) + body.rstrip() + "\n",
        encoding="utf-8",
    )


def clean_generated_files(path: Path) -> None:
    if not path.exists():
        return
    for child in path.glob("*.md"):
        if child.name != "_index.md":
            child.unlink()


def generate_work(work: Work, *, clean: bool = False) -> None:
    out_dir = MASTERS_DIR / work.slug
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    write_index(out_dir, work.title, work.summary, work.weight, work.title)
    clean_generated_files(out_dir)

    for index, chapter in enumerate(work.chapters, start=1):
        raw = fetch_raw(f"{work.wiki_base}/{chapter.wiki_suffix}")
        body = clean_body(raw)
        if not body:
            raise ValueError(f"Empty body for {work.title}/{chapter.title}")
        write_page(
            out_dir / f"{chapter.slug}.md",
            f"{work.title}-{chapter.title}",
            f"{work.title}：{chapter.title}",
            index,
            work.title,
            body,
        )
        time.sleep(FETCH_DELAY)
    print(f"Generated {work.title}: {len(work.chapters)} files")


def generated_paths() -> list[Path]:
    paths = [MASTERS_DIR / "_index.md"]
    for work in WORKS.values():
        paths.append(MASTERS_DIR / work.slug / "_index.md")
        paths.extend(MASTERS_DIR / work.slug / f"{chapter.slug}.md" for chapter in work.chapters)
    return paths


def validate() -> None:
    missing = [path for path in generated_paths() if not path.exists()]
    if missing:
        raise ValueError("Missing generated files:\n" + "\n".join(str(path) for path in missing))

    artifact = re.compile(
        r"\{\{|\}\}|\[\[|\]\]|<[^>]+>|Category:|textquality|Textquality|"
        r"Gototop|Header|Footer|onlyinclude|href=|�|[\ue000-\uf8ff]|"
        r"^[a-z][a-z-]{1,12}:",
        flags=re.M,
    )
    forbidden_front = re.compile(r"^(categories|source|source_url|source_license):", flags=re.M)
    expected_counts = {"xunzi": 33, "mozi": 53, "hanfeizi": 55}

    for path in generated_paths():
        content = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", content, flags=re.S)
        if not match:
            raise ValueError(f"Missing front matter: {path}")
        front = match.group(1)
        body = content[match.end():].strip()
        expected_draft = "true" if path.name == "_index.md" else "false"
        if f"draft: {expected_draft}" not in front:
            raise ValueError(f"Unexpected draft state in {path}")
        if forbidden_front.search(front):
            raise ValueError(f"Forbidden front matter in {path}")
        if path.name != "_index.md" and not body:
            raise ValueError(f"Empty body in {path}")
        if artifact.search(body):
            raise ValueError(f"Source artifact in {path}")

    for key, expected in expected_counts.items():
        count = len([path for path in (MASTERS_DIR / WORKS[key].slug).glob("*.md") if path.name != "_index.md"])
        if count != expected:
            raise ValueError(f"Unexpected count for {key}: {count}, expected {expected}")
    print("Masters first priority local check passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Generate all first priority works")
    parser.add_argument("--text", choices=sorted(WORKS), help="Generate one work")
    parser.add_argument("--clean", action="store_true", help="Remove target work directory before writing")
    parser.add_argument("--check", action="store_true", help="Check generated output")
    args = parser.parse_args()

    if args.check:
        validate()
        return 0

    if not args.all and not args.text:
        parser.print_help()
        return 0

    write_index(
        MASTERS_DIR,
        "子部",
        "子部，收录诸子百家、兵家、杂家等先秦两汉诸子典籍。",
        6,
        "子部",
        "子部先收诸子百家代表性典籍。",
    )

    if args.all:
        for work in WORKS.values():
            generate_work(work, clean=args.clean)
        return 0

    generate_work(WORKS[args.text], clean=args.clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
