#!/usr/bin/env python3
"""Create 集部 directory skeleton under content/posts/literature/."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIT_DIR = ROOT / "content" / "posts" / "literature"

SUBCATEGORIES = {
    "chuci": {"title": "楚辞类", "weight": 10, "summary": "楚辞及相关注本研究。"},
    "zongji": {"title": "总集类", "weight": 20, "summary": "历代诗文总集，汇编多人作品。"},
    "shiwenping": {"title": "诗文评类", "weight": 30, "summary": "文学理论与批评著作。"},
    "ciqu": {"title": "词曲类", "weight": 40, "summary": "词曲总集与理论著作。"},
    "bieji": {"title": "别集类", "weight": 50, "summary": "历代文人个人作品集。"},
}

TEXT_DIRS = {
    "chuci": ["chu-ci"],
    "zongji": ["wen-xuan", "gu-wen-guan-zhi", "yu-tai-xin-yong", "yue-fu-shi-ji"],
    "shiwenping": ["wenxin-diaolong", "shi-pin", "ren-jian-ci-hua", "sui-yuan-shi-hua"],
    "ciqu": ["hua-jian-ji"],
    "bieji": ["du-fu", "li-bai"],
}


def write_frontmatter(
    path: Path,
    title: str,
    weight: int,
    summary: str,
    tags: list[str],
    categories: list[str],
) -> None:
    import json

    content = f"""---
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    LIT_DIR.mkdir(parents=True, exist_ok=True)

    # Top-level _index.md
    write_frontmatter(
        LIT_DIR / "_index.md",
        "集部",
        6,
        "集部，中国古代文学分类之一，收录诗文总集、别集、文学批评等。",
        ["集部"],
        ["集部"],
    )
    print("  Created literature/_index.md")

    # Subcategory _index.md files
    for slug, info in SUBCATEGORIES.items():
        write_frontmatter(
            LIT_DIR / slug / "_index.md",
            info["title"],
            info["weight"],
            info["summary"],
            ["集部"],
            ["集部"],
        )
        print(f"  Created literature/{slug}/_index.md")

        # Text directories
        for text_slug in TEXT_DIRS.get(slug, []):
            (LIT_DIR / slug / text_slug).mkdir(parents=True, exist_ok=True)
            print(f"  Created literature/{slug}/{text_slug}/")

    print(f"\nDone. Literature structure created under {LIT_DIR}")


if __name__ == "__main__":
    main()
