#!/usr/bin/env python3
"""Generate high-priority protective sutra groups from CBETA/CBData.

Primary source: CBData stable juan endpoint, backed by CBETA XML P5.
Reference/proofreading source: SAT Taisho identifiers for T0245, T0246,
T0663, T0664, and T0665.

The script preserves prefaces and section headings, removes repeated per-juan
title/byline boilerplate, and validates the Taisho work id, category, and juan
count before writing Markdown.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
import shutil
from pathlib import Path

from generate_bore_from_cbdata import CbetaJuanParser, chinese_number, fetch_text


ROOT = Path(__file__).resolve().parents[1]
JINGZANG_ROOT = ROOT / "content/posts/buddha/jingzang"
API_URL = "https://cbdata.dila.edu.tw/stable/juans?work={work}&juan={juan}&work_info=1&toc=1"
DATE = "2026-06-26"


GROUPS = {
    "jingji/jinguangming": {
        "title": "金光明经系",
        "summary": "经集部中金光明经典的三种重要汉译与合本。",
        "intro": "收录经集部中金光明经典的三种重要汉译与合本。",
        "tag": "佛学",
        "weight": 100,
    },
    "jingji/renwang": {
        "title": "仁王经系",
        "summary": "经集部中仁王般若护国经典的两种重要汉译。",
        "intro": "收录经集部中仁王般若护国经典的两种重要汉译。",
        "tag": "佛学",
        "weight": 110,
    },
}


COLLECTIONS = {
    "jin-guang-ming-jing": {
        "work": "T0663",
        "display_title": "金光明经",
        "tag": "金光明经",
        "slug": "jin-guang-ming-jing",
        "target": "jingji/jinguangming/jin-guang-ming-jing",
        "total_juan": 4,
        "weight": 10,
        "summary": "金光明经四卷，北凉昙无谶译。",
        "intro": "收录《金光明经》四卷，北凉昙无谶译。",
        "expected_category": "經集部類",
        "removable_title_patterns": [
            r"^金光明經卷第?[一二三四五六七八九十百零]+$",
        ],
        "removable_bylines": {
            "北涼三藏法師曇無讖譯",
            "北涼曇無讖譯",
        },
    },
    "he-bu-jin-guang-ming-jing": {
        "work": "T0664",
        "display_title": "合部金光明经",
        "tag": "合部金光明经",
        "slug": "he-bu-jin-guang-ming-jing",
        "target": "jingji/jinguangming/he-bu-jin-guang-ming-jing",
        "total_juan": 8,
        "weight": 20,
        "summary": "合部金光明经八卷，隋宝贵合。",
        "intro": "收录《合部金光明经》八卷，隋宝贵合。",
        "expected_category": "經集部類",
        "removable_title_patterns": [
            r"^合部金光明經卷第?[一二三四五六七八九十百零]+$",
        ],
        "removable_bylines": {
            "隋大興善寺沙門釋寶貴合北涼天竺三藏曇無讖譯",
            "隋大興善寺沙門釋寶貴合梁三藏真諦譯",
            "隋大興善寺沙門釋寶貴合隋闍那崛多譯",
            "隋大興善寺沙門釋寶貴合北涼三藏曇無讖譯",
            "隋寶貴合",
        },
    },
    "jin-guang-ming-zui-sheng-wang-jing": {
        "work": "T0665",
        "display_title": "金光明最胜王经",
        "tag": "金光明最胜王经",
        "slug": "jin-guang-ming-zui-sheng-wang-jing",
        "target": "jingji/jinguangming/jin-guang-ming-zui-sheng-wang-jing",
        "total_juan": 10,
        "weight": 30,
        "summary": "金光明最胜王经十卷，唐义净译。",
        "intro": "收录《金光明最胜王经》十卷，唐义净译。",
        "expected_category": "經集部類",
        "removable_title_patterns": [
            r"^金光明最勝王經卷第?[一二三四五六七八九十百零]+$",
        ],
        "removable_bylines": {
            "大唐三藏沙門義淨奉制譯",
            "唐義淨譯",
        },
    },
    "fo-shuo-ren-wang-bo-re-bo-luo-mi-jing": {
        "work": "T0245",
        "display_title": "佛说仁王般若波罗蜜经",
        "tag": "佛说仁王般若波罗蜜经",
        "slug": "fo-shuo-ren-wang-bo-re-bo-luo-mi-jing",
        "target": "jingji/renwang/fo-shuo-ren-wang-bo-re-bo-luo-mi-jing",
        "total_juan": 2,
        "weight": 10,
        "summary": "佛说仁王般若波罗蜜经二卷，后秦鸠摩罗什译。",
        "intro": "收录《佛说仁王般若波罗蜜经》二卷，后秦鸠摩罗什译。",
        "expected_category": "般若部類",
        "removable_title_patterns": [
            r"^佛說仁王般若波羅蜜經卷[上下]$",
        ],
        "removable_bylines": {
            "姚秦三藏鳩摩羅什譯",
            "後秦鳩摩羅什譯",
        },
    },
    "ren-wang-hu-guo-bo-re-bo-luo-mi-duo-jing": {
        "work": "T0246",
        "display_title": "仁王护国般若波罗蜜多经",
        "tag": "仁王护国般若波罗蜜多经",
        "slug": "ren-wang-hu-guo-bo-re-bo-luo-mi-duo-jing",
        "target": "jingji/renwang/ren-wang-hu-guo-bo-re-bo-luo-mi-duo-jing",
        "total_juan": 2,
        "weight": 20,
        "summary": "仁王护国般若波罗蜜多经二卷，唐不空译。",
        "intro": "收录《仁王护国般若波罗蜜多经》二卷，唐不空译。",
        "expected_category": "般若部類",
        "removable_title_patterns": [
            r"^仁王護國般若波羅蜜多經卷[上下]$",
        ],
        "removable_bylines": {
            "開府儀同三司特進試鴻臚卿肅國公食邑三千戶賜紫贈司空謚大鑒正號大廣智大興善寺三藏沙門不空奉詔譯",
            "開府儀同三司特進試鴻臚卿肅國公食邑三千戶賜紫贈司空諡大鑒正號大廣智大興善寺三藏沙門不空奉詔譯",
            "唐不空譯",
        },
    },
}


FORBIDDEN_BODY_PATTERNS = [
    (re.compile(r"\{\{|\}\}"), "raw template braces"),
    (re.compile(r"\[\[|\]\]"), "raw wiki link"),
    (re.compile(r"<[^>]+>"), "raw HTML tag"),
    (re.compile(r"Category:|分類:|分类:", re.I), "category line"),
    (re.compile(r"CBETA|CBReader|大正藏"), "source boilerplate"),
    (re.compile(r"�"), "replacement character"),
    (re.compile(r"[\ue000-\uf8ff]"), "private-use character"),
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def dump_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def target_path(config: dict) -> Path:
    return JINGZANG_ROOT / config["target"]


def front_matter(title: str, summary: str, tag: str, weight: int) -> str:
    return "\n".join(
        [
            "---",
            f"title: {dump_string(title)}",
            f"date: {DATE}",
            f"weight: {weight}",
            f"tags: {json.dumps([tag], ensure_ascii=False)}",
            "draft: true",
            f"summary: {dump_string(summary)}",
            "showToc: false",
            "tocOpen: false",
            "ShowShareButtons: false",
            "---",
            "",
        ]
    )


def write_index(path: Path, title: str, summary: str, tag: str, weight: int, body: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "_index.md").write_text(
        front_matter(title, summary, tag, weight) + body.strip() + "\n",
        encoding="utf-8",
    )


def write_group_indexes() -> None:
    for rel_target, config in GROUPS.items():
        write_index(
            JINGZANG_ROOT / rel_target,
            config["title"],
            config["summary"],
            config["tag"],
            config["weight"],
            config["intro"],
        )


def is_removable_block(config: dict, block_type: str, text: str) -> bool:
    normalized = normalize_text(text)
    if block_type == "byline" and normalized in {
        normalize_text(item) for item in config["removable_bylines"]
    }:
        return True
    if block_type == "paragraph":
        return any(
            re.fullmatch(pattern, normalized)
            for pattern in config["removable_title_patterns"]
        )
    return False


def clean_blocks(
    config: dict,
    blocks: list[tuple[str, str | None, str]],
) -> list[tuple[str, str | None, str]]:
    cleaned = []
    for block_type, level, text in blocks:
        if is_removable_block(config, block_type, text):
            continue
        cleaned.append((block_type, level, text))
    return cleaned


def fetch_blocks(config: dict, juan: int) -> list[tuple[str, str | None, str]]:
    raw = fetch_text(API_URL.format(work=config["work"], juan=juan))
    data = json.loads(raw)
    work_info = data.get("work_info") or {}
    if work_info.get("work") != config["work"]:
        raise RuntimeError(
            f"{config['display_title']} 卷{juan}: unexpected work {work_info.get('work')}"
        )
    if int(work_info.get("juan") or 0) != config["total_juan"]:
        raise RuntimeError(
            f"{config['display_title']} CBETA 卷数 {work_info.get('juan')} "
            f"!= expected {config['total_juan']}"
        )
    if work_info.get("category") != config["expected_category"]:
        raise RuntimeError(
            f"{config['display_title']} CBETA 部类 {work_info.get('category')} "
            f"!= expected {config['expected_category']}"
        )

    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"{config['display_title']} 卷{juan}: API 返回为空")

    parser = CbetaJuanParser()
    parser.feed(html.unescape(results[0]))
    if not parser.blocks:
        raise RuntimeError(f"{config['display_title']} 卷{juan}: 未解析到正文段落")
    blocks = clean_blocks(config, parser.blocks)
    if not blocks:
        raise RuntimeError(f"{config['display_title']} 卷{juan}: 清洗后为空")
    return blocks


def write_collection_index(config: dict) -> None:
    write_index(
        target_path(config),
        config["display_title"],
        config["summary"],
        config["tag"],
        config["weight"],
        config["intro"],
    )


def render_markdown(config: dict, juan: int, blocks: list[tuple[str, str | None, str]]) -> str:
    title = f"{config['display_title']} 卷第{chinese_number(juan)}"
    summary = f"{config['display_title']}卷第{chinese_number(juan)}"
    lines = [front_matter(title, summary, config["tag"], juan)]
    for block_type, level, text in blocks:
        if block_type == "head":
            try:
                heading_level = max(2, min(6, int(level or 2) + 1))
            except ValueError:
                heading_level = 3
            lines.append("#" * heading_level + " " + text)
        elif block_type == "verse":
            lines.append("  \n".join(text.splitlines()))
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def juan_path(config: dict, juan: int) -> Path:
    return target_path(config) / f"{config['slug']}-{juan:03d}.md"


def write_juan(config: dict, juan: int) -> Path:
    blocks = fetch_blocks(config, juan)
    path = juan_path(config, juan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(config, juan, blocks), encoding="utf-8")
    return path


def generate_collection(config: dict, workers: int) -> None:
    target = target_path(config)
    if target.exists():
        shutil.rmtree(target)
    write_collection_index(config)
    juans = list(range(1, config["total_juan"] + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(write_juan, config, juan): juan for juan in juans}
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            juan = future_map[future]
            path = future.result()
            print(
                f"[{completed:02d}/{len(juans):02d}] "
                f"{config['display_title']} 卷{juan:03d} -> {path}"
            )


def validate_generated(config: dict) -> None:
    files = sorted(
        path for path in target_path(config).glob("*.md") if path.name != "_index.md"
    )
    if len(files) != config["total_juan"]:
        raise RuntimeError(
            f"{config['display_title']} 正文文件数 {len(files)} "
            f"!= expected {config['total_juan']}"
        )

    expected_names = {
        juan_path(config, juan).relative_to(target_path(config)).as_posix()
        for juan in range(1, config["total_juan"] + 1)
    }
    actual_names = {path.relative_to(target_path(config)).as_posix() for path in files}
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing or extra:
        raise RuntimeError(
            f"{config['display_title']} 文件序列异常: missing={missing}, extra={extra}"
        )

    for path in files:
        text = path.read_text(encoding="utf-8")
        front = text.split("---", 2)[1] if text.startswith("---") else ""
        if f'tags: ["{config["tag"]}"]' not in front:
            raise RuntimeError(f"{path}: tag 不符合预期")
        if "categories:" in front:
            raise RuntimeError(f"{path}: 不应包含 categories")
        if "source:" in front or "source_url:" in front or "source_license:" in front:
            raise RuntimeError(f"{path}: 不应包含 source front matter")
        body = text.split("---", 2)[2] if text.startswith("---") else text
        for pattern, label in FORBIDDEN_BODY_PATTERNS:
            if pattern.search(body):
                raise RuntimeError(f"{path}: found {label}")
        if len(body.strip()) < 20:
            raise RuntimeError(f"{path}: 正文过短")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=sorted(COLLECTIONS), help="Only generate one collection.")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    selected = (
        {args.collection: COLLECTIONS[args.collection]}
        if args.collection
        else COLLECTIONS
    )

    if not args.validate_only:
        write_group_indexes()
        for config in selected.values():
            generate_collection(config, args.workers)

    for config in selected.values():
        validate_generated(config)
    print(f"Validated {len(selected)} collection(s).")


if __name__ == "__main__":
    main()
