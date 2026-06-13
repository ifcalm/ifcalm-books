#!/usr/bin/env python3
"""Generate Soushen ji, Bowu zhi, and Shenyijing.

Textual policy:
* Soushen ji follows the received 20-volume text on Wikisource and includes
  Gan Bao's preface. It is checked against Kanripo KR3l0099 (WYG).
* Bowu zhi follows the scan-linked 10-volume transcription at Chinese Text
  Project and is checked against Kanripo KR3l0123 (WYG).
* Shenyijing follows the textual boundary of the 47-entry Siku witness
  KR3l0093. Punctuation is taken from the Han Wei congshu transcription at
  Chinese Text Project, whose electronic segmentation produces 48 paragraphs.
* Modern editorial notes, later annotations, and page furniture are removed.
  Unrecoverable lacunae are marked as 〔闕〕.
"""

from __future__ import annotations

import argparse
import re
import shutil
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from generate_zhiguai_classics import (
    CHINESE_NUMERALS,
    OUTPUT_DIR,
    clean_wikitext,
    compare_text,
    fetch_text,
    fetch_wikisource_pages,
    fetch_zip_texts,
    fill_square_gaps,
    first_argument,
    front_matter,
    normalized_characters,
    validate_body,
    write_index,
)


KANRIPO_SOUSHEN_ZIP = (
    "https://github.com/kanripo/KR3l0099/archive/refs/heads/WYG.zip"
)
KANRIPO_BOWU_ZIP = (
    "https://github.com/kanripo/KR3l0123/archive/refs/heads/WYG.zip"
)
KANRIPO_SHENYI_ZIP = (
    "https://github.com/kanripo/KR3l0093/archive/refs/heads/WYG.zip"
)
CTEXT_SHENYI = "https://ctext.org/shenyijing/zh"
CTEXT_BOWU_CHAPTERS = [
    230513,
    633293,
    177346,
    821014,
    431480,
    822622,
    178173,
    33231,
    617352,
    349587,
]

SOUSHEN_DIR = OUTPUT_DIR / "sou-shen-ji"
BOWU_DIR = OUTPUT_DIR / "bo-wu-zhi"
SHENYI_DIR = OUTPUT_DIR / "shen-yi-jing"

BOWU_ROW_COUNTS = [50, 40, 33, 55, 22, 46, 24, 25, 20, 17]

BOWU_HEADINGS = {
    1: [
        ("地理略，自魏氏日已前，夏禹治四方而制之。", []),
        ("地", []),
        ("山", []),
        ("水", []),
        ("山水總論", []),
        ("五方人民", []),
        ("物產", []),
    ],
    2: [
        ("外國", []),
        ("異人", []),
        ("異俗", []),
        ("異產", []),
    ],
    3: [
        ("異獸", []),
        ("異鳥", []),
        ("異蟲", []),
        ("異魚", []),
        ("異草木", []),
    ],
    4: [
        ("物性", []),
        ("物理", []),
        ("物類", []),
        ("藥物", []),
        ("藥論", []),
        ("食忌", []),
        ("藥術", []),
        ("戲術", []),
    ],
    5: [
        ("方士", []),
        ("服食", []),
        ("辯方士", ["辨方士"]),
    ],
    6: [
        ("人名考", ["人名攷"]),
        ("文籍考", []),
        ("地理考", ["地理攷"]),
        ("典禮考", []),
        ("樂考", ["樂攷"]),
        ("服飾考", []),
        ("器名考", []),
        ("物名考", []),
    ],
    7: [("異聞", [])],
    8: [("史補", [])],
    9: [("雜說上", [])],
    10: [("雜說下", [])],
}

# A few CText section labels are absent from the text rows. Their positions
# are fixed by the scan-linked row order and checked against the WYG witness.
BOWU_HEADING_INSERTIONS = {
    2: {33: "異產"},
    3: {0: "異獸", 12: "異鳥", 23: "異魚"},
    4: {0: "物性"},
    6: {25: "典禮考", 37: "物名考"},
}

BOWU_EMENDATIONS = {
    1: {
        "吉兇有征": "吉凶有徵",
        "是奸城也": "是偏域也",
        "後跨京北": "後跨荊北",
        "蜀漢之士": "蜀漢之土",
        "尾間之間": "尾閭之間",
        "遐遺別域": "遐遠別域",
        "二千六百軸": "三千六百軸",
        "淫出少室": "涇出少室",
        "《楥神契》": "《援神契》",
        "叢林氣躄.": "叢林氣躄，",
    },
    10: {
        "不欲今見熊羆": "不欲令見熊羆",
    },
}

SHENYI_EMENDATIONS = {
    "冉阝": "𨚗",
    "獏為": "獏㺔",
    "\ue438": "穀",
    "\ue269": "闠",
    "百谷": "百穀",
    "五谷": "五穀",
    "消谷": "消穀",
    "少則谷不消": "少則穀不消",
    "圣": "聖",
    "好游": "好遊",
    "邯蔗": "甘蔗",
    "在水下土中": "在冰下土中",
    "復未常有孵復成": "復未嘗有毈，復成",
    "名嬰媿": "名嬰蜺",
    "淫𪵳": "淫泆",
    "錯涂": "錯塗",
    "嗡攝": "噏攝",
    "王雞鳴": "玉雞鳴",
    "豪長": "毫長",
    "使審肥美": "使糂肥美",
    "審盡更澡肉": "糂盡更澡肉",
    "不為□所咋并識": "不為物所咋，並識",
    "毛長二尺余": "毛長二尺餘",
    "高百余丈": "高百餘丈",
    "高五丈余": "高五丈餘",
    "其長十余里": "其長十餘里",
    "岸深五丈余": "岸深五丈餘",
    "則凈也": "則淨也",
}


def early_zhiguai_template(name: str, args: list[str]) -> str:
    if name in {"YL", "!", "另"}:
        return first_argument(args, early_zhiguai_template)
    if name == "*":
        return ""
    return ""


def clean_received_wikitext(
    raw: str,
    *,
    remove_bracketed_annotations: bool = False,
) -> str:
    body = clean_wikitext(raw, early_zhiguai_template)
    body = re.sub(r"(?m)^:", "", body)
    body = re.sub(
        r"[（(](?:編者按|註|注)：[^）)]*[）)]",
        "",
        body,
    )
    if remove_bracketed_annotations:
        body = re.sub(r"【[^】]*】", "", body, flags=re.DOTALL)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body


def ensure_no_private_use(body: str, label: str) -> None:
    private = [
        char
        for char in body
        if unicodedata.category(char) in {"Co", "Cs", "Cn"}
    ]
    if private:
        codepoints = ", ".join(f"U+{ord(char):04X}" for char in sorted(set(private)))
        raise ValueError(f"{label} contains private or unassigned characters: {codepoints}")


class CtextParagraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_text_row = False
        self.ctext_cells = 0
        self.capture = False
        self.inline_comment_depth = 0
        self.buffer: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "tr" and (
            (attributes.get("id") or "").startswith("n")
            or "result" in classes
        ):
            self.in_text_row = True
            self.ctext_cells = 0
            self.buffer = []
        elif (
            self.in_text_row
            and tag == "td"
            and "ctext" in (attributes.get("class") or "").split()
        ):
            self.ctext_cells += 1
            self.capture = self.ctext_cells == 2
        elif (
            self.capture
            and tag == "span"
            and "inlinecomment" in classes
        ):
            self.inline_comment_depth += 1
        elif tag == "br" and self.capture:
            # CText scan-linked pages place translations after the first br.
            self.capture = False

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.inline_comment_depth:
            self.inline_comment_depth -= 1
        elif tag == "td" and self.capture:
            self.capture = False
        elif tag == "tr" and self.in_text_row:
            paragraph = "".join(self.buffer).strip()
            if paragraph:
                self.paragraphs.append(paragraph)
            self.in_text_row = False

    def handle_data(self, data: str) -> None:
        if self.capture and not self.inline_comment_depth:
            self.buffer.append(data)


def parse_bowu_html(source_html: str, number: int) -> str:
    parser = CtextParagraphParser()
    parser.feed(source_html)
    rows = parser.paragraphs
    expected_rows = BOWU_ROW_COUNTS[number - 1]
    if len(rows) != expected_rows:
        raise ValueError(
            f"Bowu volume {number}: expected {expected_rows} CText rows, "
            f"found {len(rows)}"
        )

    headings = BOWU_HEADINGS[number]
    insertions = BOWU_HEADING_INSERTIONS.get(number, {})
    seen: set[str] = set()
    parts: list[str] = []
    for row_index, raw_row in enumerate(rows):
        row = re.sub(r"[ \t　\r\n]+", "", raw_row)
        inserted = insertions.get(row_index)
        if inserted and inserted not in seen:
            parts.append(f"## {inserted}")
            seen.add(inserted)

        candidates: list[tuple[str, str]] = []
        for canonical, aliases in headings:
            if canonical in seen:
                continue
            for prefix in [canonical, canonical.rstrip("。"), *aliases]:
                candidates.append((prefix, canonical))
        candidates.sort(key=lambda item: len(item[0]), reverse=True)
        for prefix, canonical in candidates:
            if not row.startswith(prefix):
                continue
            parts.append(f"## {canonical}")
            seen.add(canonical)
            row = row[len(prefix) :]
            break
        if row:
            parts.append(row)

    expected_headings = {canonical for canonical, _ in headings}
    if seen != expected_headings:
        raise ValueError(
            f"Bowu volume {number}: headings mismatch; "
            f"missing {sorted(expected_headings - seen)}, "
            f"extra {sorted(seen - expected_headings)}"
        )

    body = "\n\n".join(parts)
    for old, new in BOWU_EMENDATIONS.get(number, {}).items():
        if old not in body:
            raise ValueError(
                f"Bowu volume {number}: expected source reading not found: {old!r}"
            )
        body = body.replace(old, new)
    body = body.translate(
        str.maketrans(
            {
                "“": "「",
                "”": "」",
                "‘": "『",
                "’": "』",
            }
        )
    )
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def generate_soushen(
    pages: dict[str, str],
    references: dict[int, str],
    minimum_coverage: float,
) -> tuple[str, list[str]]:
    required = set(range(0, 21))
    if not required.issubset(references):
        raise ValueError(
            f"Kanripo Soushen files missing: {sorted(required - set(references))}"
        )

    titles = ["搜神記/序"] + [
        f"搜神記/第{number:02d}卷" for number in range(1, 21)
    ]
    bodies: list[str] = []
    for number, title in enumerate(titles):
        body = clean_received_wikitext(pages[title])
        body, filled, marked = fill_square_gaps(
            body,
            references[number],
            title,
        )
        validate_body(body, title)
        ensure_no_private_use(body, title)
        comparison = compare_text(
            body,
            references[number],
            align=True,
            remove_parentheses=True,
        )
        coverage = min(
            comparison.output_coverage,
            comparison.reference_coverage,
        )
        if coverage < minimum_coverage:
            raise ValueError(
                f"{title}: comparison coverage "
                f"{comparison.output_coverage:.2%}/"
                f"{comparison.reference_coverage:.2%} below "
                f"{minimum_coverage:.0%}"
            )
        label = "preface" if number == 0 else f"{number:02d}/20"
        print(
            f"[Soushen {label}] {len(normalized_characters(body))} chars; "
            f"coverage {comparison.output_coverage:.2%}/"
            f"{comparison.reference_coverage:.2%}; "
            f"gaps filled {filled}, marked {marked}"
        )
        bodies.append(body)
    return bodies[0], bodies[1:]


def generate_bowu(
    source_htmls: list[str],
    references: dict[int, str],
    minimum_coverage: float,
) -> list[str]:
    required = set(range(1, 11))
    if not required.issubset(references):
        raise ValueError(
            f"Kanripo Bowu files missing: {sorted(required - set(references))}"
        )

    bodies: list[str] = []
    if len(source_htmls) != 10:
        raise ValueError(f"expected 10 Bowu source pages, found {len(source_htmls)}")
    for number, source_html in enumerate(source_htmls, start=1):
        title = f"博物志卷{number}"
        body = parse_bowu_html(source_html, number)
        validate_body(body, title)
        ensure_no_private_use(body, title)
        comparison = compare_text(
            body,
            references[number],
            align=True,
            remove_parentheses=True,
        )
        if min(
            comparison.output_coverage,
            comparison.reference_coverage,
        ) < minimum_coverage:
            raise ValueError(
                f"{title}: comparison coverage "
                f"{comparison.output_coverage:.2%}/"
                f"{comparison.reference_coverage:.2%} below "
                f"{minimum_coverage:.0%}"
            )
        print(
            f"[Bowu {number:02d}/10] "
            f"{len(normalized_characters(body))} chars; "
            f"coverage {comparison.output_coverage:.2%}/"
            f"{comparison.reference_coverage:.2%}"
        )
        bodies.append(body)
    return bodies


def generate_shenyi(
    source_html: str,
    reference: str,
    minimum_coverage: float,
) -> tuple[str, int]:
    parser = CtextParagraphParser()
    parser.feed(source_html)
    paragraphs = parser.paragraphs
    if len(paragraphs) != 48:
        raise ValueError(
            f"expected 48 CText Shenyijing paragraphs, found {len(paragraphs)}"
        )

    body = "\n\n".join(paragraphs)
    for old, new in SHENYI_EMENDATIONS.items():
        body = body.replace(old, new)
    body = body.replace("□", "〔闕〕")
    body = body.translate(
        str.maketrans(
            {
                "“": "「",
                "”": "」",
                "‘": "『",
                "’": "』",
            }
        )
    )
    body = re.sub(r"[ \t　]+", "", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    validate_body(body, "神異經")
    ensure_no_private_use(body, "神異經")

    comparison = compare_text(
        body,
        reference,
        align=True,
        remove_parentheses=True,
    )
    coverage = min(
        comparison.output_coverage,
        comparison.reference_coverage,
    )
    if coverage < minimum_coverage:
        raise ValueError(
            "神異經: comparison coverage "
            f"{comparison.output_coverage:.2%}/"
            f"{comparison.reference_coverage:.2%} below "
            f"{minimum_coverage:.0%}"
        )
    lacunae = body.count("〔闕〕")
    print(
        f"[Shenyi] {len(paragraphs)} electronic paragraphs, "
        f"{len(normalized_characters(body))} chars; "
        f"coverage {comparison.output_coverage:.2%}/"
        f"{comparison.reference_coverage:.2%}; "
        f"lacunae {lacunae}"
    )
    return body, lacunae


def write_outputs(
    soushen_preface: str,
    soushen_volumes: list[str],
    bowu_volumes: list[str],
    shenyi: str,
) -> None:
    for directory in (SOUSHEN_DIR, BOWU_DIR, SHENYI_DIR):
        if directory.exists():
            shutil.rmtree(directory)

    write_index(
        SOUSHEN_DIR / "_index.md",
        "搜神记",
        "搜神记，收录序文及传世本二十卷。",
        40,
        "搜神记",
        "《搜神记》按传世二十卷本收录，另收干宝序。"
        "原书三十卷早佚，本次不收入《续搜神记》。",
    )
    (SOUSHEN_DIR / "sou-shen-ji-000.md").write_text(
        front_matter(
            "搜神记 序",
            "《搜神记》干宝序。",
            0,
            "搜神记",
        )
        + soushen_preface
        + "\n",
        encoding="utf-8",
    )
    for number, body in enumerate(soushen_volumes, start=1):
        (SOUSHEN_DIR / f"sou-shen-ji-{number:03d}.md").write_text(
            front_matter(
                f"搜神记 卷{CHINESE_NUMERALS[number]}",
                f"《搜神记》卷{number}。",
                number,
                "搜神记",
            )
            + body
            + "\n",
            encoding="utf-8",
        )

    write_index(
        BOWU_DIR / "_index.md",
        "博物志",
        "博物志，按传世本收录十卷。",
        50,
        "博物志",
        "《博物志》按传世十卷本收录。今本并非张华原书旧貌，"
        "历代已有散佚与后人辑补，本次不据他书引文臆补。",
    )
    for number, body in enumerate(bowu_volumes, start=1):
        (BOWU_DIR / f"bo-wu-zhi-{number:03d}.md").write_text(
            front_matter(
                f"博物志 卷{CHINESE_NUMERALS[number]}",
                f"《博物志》卷{number}。",
                number,
                "博物志",
            )
            + body
            + "\n",
            encoding="utf-8",
        )

    write_index(
        SHENYI_DIR / "_index.md",
        "神异经",
        "神异经，按四库本篇目边界收录一卷。",
        60,
        "神异经",
        "《神异经》以四库本四十七条的篇目边界为准，"
        "参考《汉魏丛书》本断句；两本分合有异，成品电子分为四十八段。"
        "旧题东方朔撰、张华注，作者归属存疑；"
        "不混入《广汉魏丛书》五十八条本的增文。",
    )
    (SHENYI_DIR / "shen-yi-jing-001.md").write_text(
        front_matter(
            "神异经",
            "《神异经》一卷。",
            1,
            "神异经",
        )
        + shenyi
        + "\n",
        encoding="utf-8",
    )
    print("Wrote 32 content files across three early zhiguai collections")


def generate(
    *,
    dry_run: bool = False,
    soushen_minimum: float = 0.88,
    bowu_minimum: float = 0.93,
    shenyi_minimum: float = 0.90,
) -> None:
    soushen_titles = ["搜神記/序"] + [
        f"搜神記/第{number:02d}卷" for number in range(1, 21)
    ]
    pages = fetch_wikisource_pages(soushen_titles)
    soushen_references = fetch_zip_texts(
        KANRIPO_SOUSHEN_ZIP,
        r"/KR3l0099_(\d{3})\.txt$",
    )
    bowu_references = fetch_zip_texts(
        KANRIPO_BOWU_ZIP,
        r"/KR3l0123_(\d{3})\.txt$",
    )
    shenyi_references = fetch_zip_texts(
        KANRIPO_SHENYI_ZIP,
        r"/KR3l0093_(\d{3})\.txt$",
    )
    if 1 not in shenyi_references:
        raise ValueError("Kanripo Shenyijing text file is missing")

    soushen_preface, soushen_volumes = generate_soushen(
        pages,
        soushen_references,
        soushen_minimum,
    )
    bowu_volumes = generate_bowu(
        [
            fetch_text(
                f"https://ctext.org/wiki.pl?chapter={chapter}&if=gb"
            )
            for chapter in CTEXT_BOWU_CHAPTERS
        ],
        bowu_references,
        bowu_minimum,
    )
    shenyi, _ = generate_shenyi(
        fetch_text(CTEXT_SHENYI),
        shenyi_references[1],
        shenyi_minimum,
    )

    if dry_run:
        print("Dry run complete; no files written")
        return
    write_outputs(
        soushen_preface,
        soushen_volumes,
        bowu_volumes,
        shenyi,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--soushen-minimum", type=float, default=0.88)
    parser.add_argument("--bowu-minimum", type=float, default=0.93)
    parser.add_argument("--shenyi-minimum", type=float, default=0.90)
    args = parser.parse_args()
    generate(
        dry_run=args.dry_run,
        soushen_minimum=args.soushen_minimum,
        bowu_minimum=args.bowu_minimum,
        shenyi_minimum=args.shenyi_minimum,
    )


if __name__ == "__main__":
    main()
