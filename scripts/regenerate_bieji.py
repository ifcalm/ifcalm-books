#!/usr/bin/env python3
"""Regenerate 别集 (Du Fu, Li Bai) from chinese-poetry GitHub repo with punctuation."""

from __future__ import annotations

import json, re, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIT_DIR = ROOT / "content" / "posts" / "literature" / "bieji"
UA = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
POETRY_BASE = "https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/%E5%85%A8%E5%94%90%E8%AF%97"

# Source files for each poet
LIBAI_FILES = [0, 1000, 2000, 8000]
DUFU_FILES = [0, 1000, 10000, 11000, 12000]

POETS = {
    "li-bai": {
        "slug": "li-bai",
        "title": "李太白文集",
        "author": "李白",
        "files": LIBAI_FILES,
        "total_vols": 30,
        "summary": "李太白文集，唐李白撰。收录诗约千首，据全唐诗整理。",
        "tags": ["李太白文集", "李白", "别集"],
    },
    "du-fu": {
        "slug": "du-fu",
        "title": "杜工部集",
        "author": "杜甫",
        "files": DUFU_FILES,
        "total_vols": 30,
        "summary": "杜工部集，唐杜甫撰。收录诗约千四百首，据全唐诗整理。",
        "tags": ["杜工部集", "杜甫", "别集"],
    },
}


def download_poems(author: str, file_ids: list[int]) -> list[dict]:
    """Download all poems for an author from chinese-poetry files."""
    all_poems: list[dict] = []
    for fid in file_ids:
        url = f"{POETRY_BASE}/poet.tang.{fid}.json"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            poems = json.loads(r.read())
        author_poems = [p for p in poems if p.get("author") == author]
        all_poems.extend(author_poems)
        print(f"  File {fid}: {len(author_poems)} poems")
        time.sleep(0.5)
    return all_poems


def front_matter(title: str, summary: str, weight: int,
                 tags: list[str], categories: list[str] | None = None) -> str:
    categories = categories or ["集部"]
    tags_str = json.dumps(tags, ensure_ascii=False)
    cats_str = json.dumps(categories, ensure_ascii=False)
    return f"""---
title: "{title}"
date: 2026-05-20
weight: {weight}
tags: {tags_str}
categories: {cats_str}
draft: false
summary: "{summary}"
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""


def format_poem(poem: dict) -> str:
    """Format a single poem as markdown."""
    title = poem.get("title", "无题")
    paragraphs = poem.get("paragraphs", [])
    lines = [f"### {title}", ""]
    for para in paragraphs:
        lines.append(para)
        lines.append("")
    return "\n".join(lines)


def generate_poet(poet_id: str, dry_run: bool = False) -> tuple[int, int]:
    """Generate a poet's collected works from chinese-poetry."""
    info = POETS[poet_id]
    out_dir = LIT_DIR / info["slug"]

    print(f"\n{'='*60}")
    print(f"Generating {info['title']} ({info['author']})")
    print(f"Source: chinese-poetry (GitHub)")
    print(f"Output: {out_dir.relative_to(ROOT)}")

    # Download poems
    print("Downloading poems...")
    poems = download_poems(info["author"], info["files"])
    print(f"Total: {len(poems)} poems")

    if dry_run:
        return len(poems), 0

    # Sort by title for consistent ordering
    poems.sort(key=lambda p: p.get("title", ""))

    # Clear old content
    import shutil
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # Write _index.md
    fm = front_matter(info["title"], info["summary"], 10, info["tags"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_index.md").write_text(fm, encoding="utf-8")

    # Batch poems into volume groups
    total_vols = info["total_vols"]
    poems_per_vol = max(1, len(poems) // total_vols)

    vol = 1
    batch: list[dict] = []
    vol_files: list[Path] = []

    def flush_batch(v: int, poems_batch: list[dict]):
        if not poems_batch:
            return
        g_end = min((v - 1) // 10 * 10 + 10, total_vols)
        group = f"{(v - 1) // 10 * 10 + 1:03d}-{g_end:03d}"
        group_dir = out_dir / group
        group_dir.mkdir(parents=True, exist_ok=True)
        out_file = group_dir / f"{info['slug']}-{v:03d}.md"

        body_parts = [format_poem(p) for p in poems_batch]
        body = "\n".join(body_parts)

        display_title = f"{info['title']} 卷{v}"
        vol_summary = f"{info['title']}卷{v}，共{len(poems_batch)}首。"

        content = front_matter(display_title, vol_summary, v, info["tags"]) + body + "\n"
        out_file.write_text(content, encoding="utf-8")
        vol_files.append(out_file)

    for i, poem in enumerate(poems):
        batch.append(poem)
        # Flush when batch is full or at the end
        if len(batch) >= poems_per_vol or (vol < total_vols and len(batch) >= poems_per_vol):
            flush_batch(vol, batch)
            batch = []
            vol += 1
            if vol > total_vols:
                # Append remaining to last volume
                break

    # Append any remaining to last volume
    if batch and vol <= total_vols:
        flush_batch(total_vols, batch)

    # If we have more poems than volumes can hold, add to last volume
    remaining = poems[total_vols * poems_per_vol:]
    if remaining:
        # Redistribute: recreate all volumes evenly
        shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "_index.md").write_text(fm, encoding="utf-8")

        actual_vols = info["total_vols"]
        poems_per_vol_new = max(1, len(poems) // actual_vols)
        for v in range(1, actual_vols + 1):
            start = (v - 1) * poems_per_vol_new
            end = start + poems_per_vol_new if v < actual_vols else len(poems)
            batch_poems = poems[start:end]
            if batch_poems:
                group = f"{(v - 1) // 10 * 10 + 1:03d}-{min((v - 1) // 10 * 10 + 10, actual_vols):03d}"
                group_dir = out_dir / group
                group_dir.mkdir(parents=True, exist_ok=True)
                out_file = group_dir / f"{info['slug']}-{v:03d}.md"
                body_parts = [format_poem(p) for p in batch_poems]
                body = "\n".join(body_parts)
                display_title = f"{info['title']} 卷{v}"
                vol_summary = f"{info['title']}卷{v}，共{len(batch_poems)}首。"
                content = front_matter(display_title, vol_summary, v, info["tags"]) + body + "\n"
                out_file.write_text(content, encoding="utf-8")
                print(f"  [{v:03d}/{actual_vols}] {len(batch_poems)} poems -> {out_file.relative_to(ROOT)}")

    for f in vol_files:
        print(f"  {f.relative_to(ROOT)}")

    return len(poems), 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poet", choices=["li-bai", "du-fu", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.poet == "all":
        for pid in ["li-bai", "du-fu"]:
            generate_poet(pid, dry_run=args.dry_run)
    else:
        generate_poet(args.poet, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
