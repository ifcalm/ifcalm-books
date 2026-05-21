#!/usr/bin/env python3
"""Validate generated 诸子 pages against generate_zhuzi.py ordering rules."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import generate_zhuzi


ROOT = Path(__file__).resolve().parents[1]
ZHUZI_DIR = ROOT / "content" / "posts" / "zhuzi"


def page_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^title: "(.*)"$', text, flags=re.M)
    if not match:
        raise ValueError(f"missing title: {path.relative_to(ROOT)}")
    return match.group(1)


def expected_titles(text_id: str) -> list[str]:
    info = generate_zhuzi.TEXTS[text_id]
    if info["type"] != "subpages":
        return [info["title"]]
    titles = generate_zhuzi.PAGE_ORDERS.get(text_id)
    if not titles:
        return []
    overrides = generate_zhuzi.TITLE_OVERRIDES.get(text_id, {})
    return [overrides.get(title, title) for title in titles]


def main() -> None:
    issues: list[str] = []
    for text_id, info in generate_zhuzi.TEXTS.items():
        directory = ZHUZI_DIR / info["slug"]
        files = sorted(path for path in directory.glob("*.md") if path.name != "_index.md")
        expected = expected_titles(text_id)
        if not expected:
            continue
        actual = [page_title(path) for path in files]
        if actual != expected:
            issues.append(
                f"{text_id}: titles differ\n"
                f"  expected: {expected}\n"
                f"  actual:   {actual}"
            )

    if issues:
        print("Zhuzi order validation failed:")
        for issue in issues:
            print("- " + issue)
        sys.exit(1)
    print("Zhuzi order validation ok.")


if __name__ == "__main__":
    main()
