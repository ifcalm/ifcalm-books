#!/usr/bin/env python3
"""Generate 史记 (130 volumes) from Wikisource into content/posts/history/shi-ji/."""

from __future__ import annotations

import sys, time, urllib.request, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import clean_wikitext

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "content" / "posts" / "history" / "shi-ji"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
API_RAW = "https://zh.wikisource.org/w/index.php?title={}&action=raw"

# Volume titles for frontmatter (to give each volume a descriptive name)
# Key: volume number, Value: Chinese title
VOLUME_TITLES: dict[int, str] = {
    1: "五帝本紀第一",
    2: "夏本紀第二",
    3: "殷本紀第三",
    4: "周本紀第四",
    5: "秦本紀第五",
    6: "秦始皇本紀第六",
    7: "項羽本紀第七",
    8: "高祖本紀第八",
    9: "呂太后本紀第九",
    10: "孝文本紀第十",
    11: "孝景本紀第十一",
    12: "孝武本紀第十二",
    13: "三代世表第一",
    14: "十二諸侯年表第二",
    15: "六國年表第三",
    16: "秦楚之際月表第四",
    17: "漢興以來諸侯王年表第五",
    18: "高祖功臣侯者年表第六",
    19: "惠景閒侯者年表第七",
    20: "建元以來侯者年表第八",
    21: "建元已來王子侯者年表第九",
    22: "漢興以來將相名臣年表第十",
    23: "禮書第一",
    24: "樂書第二",
    25: "律書第三",
    26: "曆書第四",
    27: "天官書第五",
    28: "封禪書第六",
    29: "河渠書第七",
    30: "平準書第八",
    31: "吳太伯世家第一",
    32: "齊太公世家第二",
    33: "魯周公世家第三",
    34: "燕召公世家第四",
    35: "管蔡世家第五",
    36: "陳杞世家第六",
    37: "衛康叔世家第七",
    38: "宋微子世家第八",
    39: "晉世家第九",
    40: "楚世家第十",
    41: "越王句踐世家第十一",
    42: "鄭世家第十二",
    43: "趙世家第十三",
    44: "魏世家第十四",
    45: "韓世家第十五",
    46: "田敬仲完世家第十六",
    47: "孔子世家第十七",
    48: "陳涉世家第十八",
    49: "外戚世家第十九",
    50: "楚元王世家第二十",
    51: "荊燕世家第二十一",
    52: "齊悼惠王世家第二十二",
    53: "蕭相國世家第二十三",
    54: "曹相國世家第二十四",
    55: "留侯世家第二十五",
    56: "陳丞相世家第二十六",
    57: "絳侯周勃世家第二十七",
    58: "梁孝王世家第二十八",
    59: "五宗世家第二十九",
    60: "三王世家第三十",
    61: "伯夷列傳第一",
    62: "管晏列傳第二",
    63: "老子韓非列傳第三",
    64: "司馬穰苴列傳第四",
    65: "孫子吳起列傳第五",
    66: "伍子胥列傳第六",
    67: "仲尼弟子列傳第七",
    68: "商君列傳第八",
    69: "蘇秦列傳第九",
    70: "張儀列傳第十",
    71: "樗里子甘茂列傳第十一",
    72: "穰侯列傳第十二",
    73: "白起王翦列傳第十三",
    74: "孟子荀卿列傳第十四",
    75: "孟嘗君列傳第十五",
    76: "平原君虞卿列傳第十六",
    77: "魏公子列傳第十七",
    78: "春申君列傳第十八",
    79: "范睢蔡澤列傳第十九",
    80: "樂毅列傳第二十",
    81: "廉頗藺相如列傳第二十一",
    82: "田單列傳第二十二",
    83: "魯仲連鄒陽列傳第二十三",
    84: "屈原賈生列傳第二十四",
    85: "呂不韋列傳第二十五",
    86: "刺客列傳第二十六",
    87: "李斯列傳第二十七",
    88: "蒙恬列傳第二十八",
    89: "張耳陳餘列傳第二十九",
    90: "魏豹彭越列傳第三十",
    91: "黥布列傳第三十一",
    92: "淮陰侯列傳第三十二",
    93: "韓信盧綰列傳第三十三",
    94: "田儋列傳第三十四",
    95: "樊酈滕灌列傳第三十五",
    96: "張丞相列傳第三十六",
    97: "酈生陸賈列傳第三十七",
    98: "傅靳蒯成列傳第三十八",
    99: "劉敬叔孫通列傳第三十九",
    100: "季布欒布列傳第四十",
    101: "袁盎鼂錯列傳第四十一",
    102: "張釋之馮唐列傳第四十二",
    103: "萬石張叔列傳第四十三",
    104: "田叔列傳第四十四",
    105: "扁鵲倉公列傳第四十五",
    106: "吳王濞列傳第四十六",
    107: "魏其武安侯列傳第四十七",
    108: "韓長孺列傳第四十八",
    109: "李將軍列傳第四十九",
    110: "匈奴列傳第五十",
    111: "衛將軍驃騎列傳第五十一",
    112: "平津侯主父列傳第五十二",
    113: "南越列傳第五十三",
    114: "東越列傳第五十四",
    115: "朝鮮列傳第五十五",
    116: "西南夷列傳第五十六",
    117: "司馬相如列傳第五十七",
    118: "淮南衡山列傳第五十八",
    119: "循吏列傳第五十九",
    120: "汲鄭列傳第六十",
    121: "儒林列傳第六十一",
    122: "酷吏列傳第六十二",
    123: "大宛列傳第六十三",
    124: "游俠列傳第六十四",
    125: "佞幸列傳第六十五",
    126: "滑稽列傳第六十六",
    127: "日者列傳第六十七",
    128: "龜策列傳第六十八",
    129: "貨殖列傳第六十九",
    130: "太史公自序第七十",
}


def fetch_raw(title: str) -> str:
    url = API_RAW.format(urllib.parse.quote(title))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def front_matter(title: str, summary: str, weight: int) -> str:
    return f"""---
title: "{title}"
date: 2026-05-19
weight: {weight}
tags: ["史记", "西汉", "司马迁"]
categories: ["史部"]
draft: false
summary: "{summary}"
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def volume_group_dir(vol: int, total: int = 130, chunk: int = 30) -> str:
    start = ((vol - 1) // chunk) * chunk + 1
    end = min(start + chunk - 1, total)
    return f"{start:03d}-{end:03d}"


def main() -> None:
    total = 130
    for vol in range(1, total + 1):
        group = volume_group_dir(vol)
        out_file = OUT_DIR / group / f"shi-ji-{vol:03d}.md"
        out_file.parent.mkdir(parents=True, exist_ok=True)

        if out_file.exists():
            print(f"[{vol:03d}/{total}] Skipping (exists): {out_file.relative_to(ROOT)}")
            continue

        title = f"史記/卷{vol:03d}"
        vol_name = VOLUME_TITLES.get(vol, f"卷{vol}")
        display_title = f"史记 卷{vol}"
        summary = f"史记卷{vol}：{vol_name}。"

        print(f"[{vol:03d}/{total}] Fetching {title} ...", end=" ", flush=True)
        try:
            raw = fetch_raw(title)
        except Exception as e:
            print(f"FAILED: {e}")
            time.sleep(2)
            continue

        clean = clean_wikitext(raw)
        content = front_matter(display_title, summary, vol) + clean + "\n"
        out_file.write_text(content, encoding="utf-8")
        print(f"OK ({len(clean)} chars) -> {out_file.relative_to(ROOT)}")
        time.sleep(0.5)  # be polite to Wikisource


if __name__ == "__main__":
    main()
