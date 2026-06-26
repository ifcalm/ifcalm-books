#!/usr/bin/env python3
"""Generate first-priority Buddhist additions from CBETA/CBData.

Primary source: CBData stable juan endpoint, backed by CBETA XML P5.
Reference/proofreading sources used when selecting this batch:

* CBETA Online / CBData stable API.
* SAT Daizokyo Text Database / Taisho identifiers.

The script validates the Taisho work id, category, and juan count before
writing Markdown. It removes repeated per-juan title/byline boilerplate while
preserving prefaces, section headings, verse blocks, and body paragraphs.
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
BUDDHA_ROOT = ROOT / "content/posts/buddha"
API_URL = "https://cbdata.dila.edu.tw/stable/juans?work={work}&juan={juan}&work_info=1&toc=1"
DATE = "2026-06-26"
DRAFT = True
RANGE_SIZE = 30


GROUP_INDEXES = {
    "lunzang/shijing": {
        "title": "释经论部",
        "summary": "解释经典义理的论书。",
        "intro": "收录解释经典义理的论书。",
        "tag": "佛学",
        "weight": 15,
    },
    "lunzang/pitan": {
        "title": "毘昙部",
        "summary": "阿毗达磨论书。",
        "intro": "收录阿毗达磨论书。",
        "tag": "佛学",
        "weight": 25,
    },
    "lunzang/lunji": {
        "title": "论集部",
        "summary": "诸论集成与综合性论书。",
        "intro": "收录诸论集成与综合性论书。",
        "tag": "佛学",
        "weight": 40,
    },
}


COLLECTIONS = {
    "da-zhi-du-lun": {
        "work": "T1509",
        "display_title": "大智度论",
        "tag": "大智度论",
        "slug": "da-zhi-du-lun",
        "target": "lunzang/shijing/da-zhi-du-lun",
        "total_juan": 100,
        "weight": 10,
        "summary": "大智度论一百卷，龙树造，后秦鸠摩罗什译。",
        "intro": "收录《大智度论》一百卷，龙树造，后秦鸠摩罗什译。",
        "expected_category": "般若部類",
        "range_size": RANGE_SIZE,
        "removable_title_patterns": [
            r"^大智度論卷第[零一二三四五六七八九十百]+$",
        ],
        "removable_bylines": {
            "龍樹菩薩造",
            "後秦龜茲國三藏法師鳩摩羅什奉詔譯",
            "後秦鳩摩羅什譯",
        },
    },
    "yu-jia-shi-di-lun": {
        "work": "T1579",
        "display_title": "瑜伽师地论",
        "tag": "瑜伽师地论",
        "slug": "yu-jia-shi-di-lun",
        "target": "lunzang/yujia/yu-jia-shi-di-lun",
        "total_juan": 100,
        "weight": 5,
        "summary": "瑜伽师地论一百卷，弥勒菩萨说，唐玄奘译。",
        "intro": "收录《瑜伽师地论》一百卷，弥勒菩萨说，唐玄奘译。",
        "expected_category": "瑜伽部類",
        "range_size": RANGE_SIZE,
        "removable_title_patterns": [
            r"^瑜伽師地論卷第[零一二三四五六七八九十百]+$",
        ],
        "removable_bylines": {
            "彌勒菩薩說",
            "三藏法師玄奘奉詔譯",
            "唐玄奘譯",
        },
    },
    "a-pi-da-mo-ju-she-lun": {
        "work": "T1558",
        "display_title": "阿毘达磨俱舍论",
        "tag": "俱舍论",
        "slug": "a-pi-da-mo-ju-she-lun",
        "target": "lunzang/pitan/a-pi-da-mo-ju-she-lun",
        "total_juan": 30,
        "weight": 10,
        "summary": "阿毘达磨俱舍论三十卷，世亲造，唐玄奘译。",
        "intro": "收录《阿毘达磨俱舍论》三十卷，世亲造，唐玄奘译。",
        "expected_category": "毘曇部類",
        "range_size": None,
        "removable_title_patterns": [
            r"^阿毘達磨俱舍論卷第[零一二三四五六七八九十百]+$",
        ],
        "removable_bylines": {
            "尊者世親造",
            "三藏法師玄奘奉詔譯",
            "唐玄奘譯",
        },
    },
    "cheng-shi-lun": {
        "work": "T1646",
        "display_title": "成实论",
        "tag": "成实论",
        "slug": "cheng-shi-lun",
        "target": "lunzang/lunji/cheng-shi-lun",
        "total_juan": 16,
        "weight": 10,
        "summary": "成实论十六卷，诃梨跋摩造，姚秦鸠摩罗什译。",
        "intro": "收录《成实论》十六卷，诃梨跋摩造，姚秦鸠摩罗什译。",
        "expected_category": "論集部類",
        "range_size": None,
        "removable_title_patterns": [
            r"^成實論卷第[零一二三四五六七八九十百]+$",
        ],
        "removable_bylines": {
            "訶梨跋摩造",
            "姚秦三藏鳩摩羅什譯",
            "姚秦鳩摩羅什譯",
        },
    },
    "zong-jing-lu": {
        "work": "T2016",
        "display_title": "宗镜录",
        "tag": "宗镜录",
        "slug": "zong-jing-lu",
        "target": "zongpai/chan/yongming/zong-jing-lu",
        "total_juan": 100,
        "weight": 5,
        "summary": "宗镜录一百卷，宋延寿集。",
        "intro": "收录《宗镜录》一百卷，宋延寿集。",
        "expected_category": "禪宗部類",
        "range_size": RANGE_SIZE,
        "removable_title_patterns": [
            r"^宗鏡錄卷第[零一二三四五六七八九十百]+$",
        ],
        "removable_bylines": {
            "大宋吳越國慧日永明寺主智覺禪師延壽集",
            "宋延壽集",
        },
    },
    "da-tang-xi-yu-ji": {
        "work": "T2087",
        "display_title": "大唐西域记",
        "tag": "大唐西域记",
        "slug": "da-tang-xi-yu-ji",
        "target": "shizhuan/da-tang-xi-yu-ji",
        "total_juan": 12,
        "weight": 30,
        "summary": "大唐西域记十二卷，唐玄奘译，辩机撰。",
        "intro": "收录《大唐西域记》十二卷，唐玄奘译，辩机撰。",
        "expected_category": "史傳部類",
        "range_size": None,
        "max_paragraph_chars": 520,
        "removable_title_patterns": [
            r"^大唐西域記卷第[零一二三四五六七八九十百]+(?:[零一二三四五六七八九十百]+國)?$",
        ],
        "removable_bylines": {
            "三藏法師玄奘奉詔譯",
            "大總持寺沙門辯機撰",
            "唐玄奘譯辯機撰",
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


def front_matter(title: str, summary: str, tag: str, weight: int) -> str:
    return "\n".join(
        [
            "---",
            f"title: {dump_string(title)}",
            f"date: {DATE}",
            f"weight: {weight}",
            f"tags: {json.dumps([tag], ensure_ascii=False)}",
            f"draft: {'true' if DRAFT else 'false'}",
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
    content = front_matter(title, summary, tag, weight) + body.rstrip() + "\n"
    (path / "_index.md").write_text(content, encoding="utf-8")


def write_group_indexes() -> None:
    for relative, config in GROUP_INDEXES.items():
        path = BUDDHA_ROOT / relative
        if (path / "_index.md").exists():
            continue
        write_index(
            path,
            config["title"],
            config["summary"],
            config["tag"],
            config["weight"],
            config["intro"],
        )


def target_path(config: dict) -> Path:
    return BUDDHA_ROOT / config["target"]


def range_dir(config: dict, juan: int) -> tuple[int, int, str] | None:
    size = config.get("range_size")
    if not size:
        return None
    start = ((juan - 1) // size) * size + 1
    end = min(start + size - 1, config["total_juan"])
    return start, end, f"{start:03d}-{end:03d}"


def juan_path(config: dict, juan: int) -> Path:
    base = target_path(config)
    range_info = range_dir(config, juan)
    if range_info:
        base = base / range_info[2]
    return base / f"{config['slug']}-{juan:03d}.md"


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
        for old, new in config.get("text_replacements", {}).items():
            text = text.replace(old, new)
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
    target = target_path(config)
    write_index(
        target,
        config["display_title"],
        config["summary"],
        config["tag"],
        config["weight"],
        config["intro"],
    )


def write_range_indexes(config: dict) -> None:
    size = config.get("range_size")
    if not size:
        return
    for start in range(1, config["total_juan"] + 1, size):
        end = min(start + size - 1, config["total_juan"])
        target = target_path(config) / f"{start:03d}-{end:03d}"
        title = f"{config['display_title']} 卷第{chinese_number(start)}至卷第{chinese_number(end)}"
        summary = f"{config['display_title']}卷第{chinese_number(start)}至卷第{chinese_number(end)}"
        write_index(target, title, summary, config["tag"], start, "")


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
        elif block_type == "paragraph" and config.get("max_paragraph_chars"):
            lines.extend(split_long_paragraph(text, config["max_paragraph_chars"]))
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def split_long_paragraph(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    parts: list[str] = []
    current: list[str] = []
    for char in text:
        current.append(char)
        if char in "。！？；" and len("".join(current)) >= max_chars:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    return parts or [text]


def write_juan(config: dict, juan: int) -> Path:
    blocks = fetch_blocks(config, juan)
    path = juan_path(config, juan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(config, juan, blocks), encoding="utf-8")
    return path


def generate_collection(config: dict, start: int, end: int, workers: int) -> None:
    target = target_path(config)
    if target.exists():
        shutil.rmtree(target)
    write_collection_index(config)
    write_range_indexes(config)
    juans = list(range(start, end + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(write_juan, config, juan): juan for juan in juans}
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            juan = future_map[future]
            path = future.result()
            print(
                f"[{completed:03d}/{len(juans):03d}] "
                f"{config['display_title']} 卷{juan:03d} -> {path}"
            )


def validate_generated(config: dict) -> None:
    files = sorted(
        path
        for path in target_path(config).rglob("*.md")
        if path.name != "_index.md"
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
        if f'tags: ["{config["tag"]}"]' not in text[:400]:
            raise RuntimeError(f"{path}: tag 不符合预期")
        if "categories:" in text[:400]:
            raise RuntimeError(f"{path}: 不应包含 categories")
        if "source:" in text[:400] or "source_url:" in text[:400] or "source_license:" in text[:400]:
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
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int, default=6)
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
            start = args.start or 1
            end = args.end or config["total_juan"]
            if start < 1 or end > config["total_juan"] or start > end:
                raise SystemExit(
                    f"{config['display_title']} 卷号范围必须在 1..{config['total_juan']} 内"
                )
            if start != 1 or end != config["total_juan"]:
                raise SystemExit("本脚本只支持整部生成，避免留下半部收录。")
            generate_collection(config, start, end, args.workers)

    for config in selected.values():
        validate_generated(config)
    print(f"Validated {len(selected)} collection(s).")


if __name__ == "__main__":
    main()
