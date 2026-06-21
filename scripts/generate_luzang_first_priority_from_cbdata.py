#!/usr/bin/env python3
"""Generate first-priority Vinaya texts from CBETA/CBData.

This batch fills the previously empty 律藏 section with:

* 四分律 (T1428), 60 juan.
* 梵网经 (T1484), 2 juan.

CBData's stable juan endpoint is used as the primary source. The endpoint
returns parsed CBETA text with work metadata, which lets the script validate the
Taisho number, category, and expected juan count before writing Markdown.
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
LUZANG_ROOT = ROOT / "content/posts/buddha/luzang"
API_URL = "https://cbdata.dila.edu.tw/stable/juans?work={work}&juan={juan}&work_info=1&toc=1"
DATE = "2026-06-21"
DRAFT = True


COLLECTIONS = {
    "sifen-lv": {
        "work": "T1428",
        "display_title": "四分律",
        "tag": "四分律",
        "slug": "sifen-lv",
        "target": "sifen-lv",
        "total_juan": 60,
        "weight": 10,
        "summary": "四分律六十卷，姚秦佛陀耶舍共竺佛念等译。",
        "intro": "收录《四分律》六十卷，姚秦佛陀耶舍共竺佛念等译。",
        "expected_category": "律部類",
        "range_size": 30,
        "removable_title_patterns": [
            r"^四分律卷第?[零一二三四五六七八九十百]+(?:初分|第二分|第三分|第四分)?(?:之[零一二三四五六七八九十百]+)?$",
        ],
        "removable_bylines": {
            "姚秦罽賓三藏佛陀耶舍共竺佛念等譯",
            "姚秦佛陀耶舍共竺佛念等譯",
        },
    },
    "fan-wang-jing": {
        "work": "T1484",
        "display_title": "梵网经",
        "tag": "梵网经",
        "slug": "fan-wang-jing",
        "target": "fan-wang-jing",
        "total_juan": 2,
        "weight": 20,
        "summary": "梵网经二卷，后秦鸠摩罗什译。",
        "intro": "收录《梵网经》二卷，后秦鸠摩罗什译。",
        "expected_category": "律部類",
        "range_size": None,
        "removable_title_patterns": [
            r"^梵網經盧舍那佛說菩薩心地戒品第十卷[上下]$",
        ],
        "removable_bylines": {
            "後秦龜茲國三藏鳩摩羅什譯",
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


def range_dir(juan: int, size: int | None) -> tuple[int, int, str] | None:
    if not size:
        return None
    start = ((juan - 1) // size) * size + 1
    end = min(start + size - 1, 60)
    return start, end, f"{start:03d}-{end:03d}"


def target_path(config: dict) -> Path:
    return LUZANG_ROOT / config["target"]


def juan_path(config: dict, juan: int) -> Path:
    base = target_path(config)
    range_info = range_dir(juan, config.get("range_size"))
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


def clean_blocks(config: dict, blocks: list[tuple[str, str | None, str]]) -> list[tuple[str, str | None, str]]:
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
        raise RuntimeError(f"{config['display_title']} 卷{juan}: unexpected work {work_info.get('work')}")
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


def write_luzang_index() -> None:
    LUZANG_ROOT.mkdir(parents=True, exist_ok=True)
    content = (
        front_matter("律藏", "佛教戒律与毗尼文献。", "佛学", 20)
        + "收录佛教戒律与毗尼文献。\n"
    )
    (LUZANG_ROOT / "_index.md").write_text(content, encoding="utf-8")


def write_collection_index(config: dict) -> None:
    target = target_path(config)
    target.mkdir(parents=True, exist_ok=True)
    content = (
        front_matter(config["display_title"], config["summary"], config["tag"], config["weight"])
        + config["intro"]
        + "\n"
    )
    (target / "_index.md").write_text(content, encoding="utf-8")


def write_range_indexes(config: dict) -> None:
    size = config.get("range_size")
    if not size:
        return
    for start in range(1, config["total_juan"] + 1, size):
        end = min(start + size - 1, config["total_juan"])
        target = target_path(config) / f"{start:03d}-{end:03d}"
        target.mkdir(parents=True, exist_ok=True)
        title = f"{config['display_title']} 卷第{chinese_number(start)}至卷第{chinese_number(end)}"
        summary = f"{config['display_title']}卷第{chinese_number(start)}至卷第{chinese_number(end)}"
        content = front_matter(title, summary, config["tag"], start)
        (target / "_index.md").write_text(content, encoding="utf-8")


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
    write_range_indexes(config)
    juans = list(range(1, config["total_juan"] + 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(write_juan, config, juan): juan for juan in juans}
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            juan = future_map[future]
            path = future.result()
            print(f"[{completed:02d}/{len(juans):02d}] {config['display_title']} 卷{juan:03d} -> {path}")


def parse_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    front = {}
    for line in text[4:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            front[key.strip()] = value.strip()
    return front, text[end + 5 :]


def expected_files(config: dict) -> list[Path]:
    return [juan_path(config, juan) for juan in range(1, config["total_juan"] + 1)]


def validate_page(path: Path, expected_tag: str, check_body: bool = True) -> list[str]:
    problems = []
    rel = path.relative_to(ROOT)
    front, body = parse_front_matter(path)
    if not front:
        return [f"{rel}: missing front matter"]
    if "categories" in front:
        problems.append(f"{rel}: categories should not be present")
    if front.get("tags") != json.dumps([expected_tag], ensure_ascii=False):
        problems.append(f"{rel}: unexpected tags {front.get('tags')}")
    if front.get("draft") != "true":
        problems.append(f"{rel}: expected draft true")
    if front.get("showToc") != "false":
        problems.append(f"{rel}: expected showToc false")
    if not check_body:
        return problems
    body = body.strip()
    if len(body) < 100:
        problems.append(f"{rel}: body too short")
    for pattern, label in FORBIDDEN_BODY_PATTERNS:
        if pattern.search(body):
            problems.append(f"{rel}: residual {label}")
            break
    for lineno, line in enumerate(body.splitlines(), start=1):
        if len(line) > 3000:
            problems.append(f"{rel}: line {lineno} too long ({len(line)} chars)")
            break
    return problems


def check_collection(config: dict, source_check: bool) -> int:
    problems = []
    target = target_path(config)
    index_file = target / "_index.md"
    if not index_file.exists():
        problems.append(f"{config['display_title']}: missing _index.md")
    else:
        problems.extend(validate_page(index_file, config["tag"], check_body=False))

    actual = sorted(path for path in target.rglob("*.md") if path.name != "_index.md")
    expected = expected_files(config)
    if set(actual) != set(expected):
        problems.append(
            f"{config['display_title']}: file list mismatch, "
            f"expected {len(expected)} files, got {len(actual)} files"
        )

    for juan, path in enumerate(expected, start=1):
        if not path.exists():
            problems.append(f"{path.relative_to(ROOT)}: missing")
            continue
        problems.extend(validate_page(path, config["tag"]))
        front, body = parse_front_matter(path)
        if front.get("weight") != str(juan):
            problems.append(f"{path.relative_to(ROOT)}: expected weight {juan}")
        if source_check:
            fresh = render_markdown(config, juan, fetch_blocks(config, juan))
            _, fresh_body = parse_front_matter_text(fresh)
            if body.strip() != fresh_body.strip():
                problems.append(f"{path.relative_to(ROOT)}: differs from cleaned source")

    if problems:
        print(f"CHECK FAILED: {config['display_title']}")
        for problem in problems[:80]:
            print(f"  - {problem}")
        if len(problems) > 80:
            print(f"  ... and {len(problems) - 80} more")
        return 1
    print(f"CHECK OK: {config['display_title']} {config['total_juan']} content files")
    return 0


def parse_front_matter_text(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    front = {}
    for line in text[4:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            front[key.strip()] = value.strip()
    return front, text[end + 5 :]


def selected_collections(collection: str | None) -> dict[str, dict]:
    if collection:
        return {collection: COLLECTIONS[collection]}
    return COLLECTIONS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=sorted(COLLECTIONS), help="Only process one collection")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--check", action="store_true", help="Validate local generated Markdown")
    parser.add_argument("--source-check", action="store_true", help="Regenerate cleaned source and compare")
    args = parser.parse_args()

    selected = selected_collections(args.collection)
    if args.check or args.source_check:
        status = 0
        for config in selected.values():
            status |= check_collection(config, source_check=args.source_check)
        return status

    write_luzang_index()
    for config in selected.values():
        generate_collection(config, workers=args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
