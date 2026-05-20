#!/usr/bin/env python3
"""Migrate confucius/ flat files to subdirectory structure and create _index.md."""

from pathlib import Path
import json, shutil

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / "content" / "posts" / "confucius"

# Create top-level _index.md
index_fm = """---
title: "经部"
date: 2026-05-20
weight: 1
tags: ["经部"]
categories: ["经部"]
draft: false
summary: "经部，收录儒家十三经等经典文献。"
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""
CONF.mkdir(parents=True, exist_ok=True)
(CONF / "_index.md").write_text(index_fm, encoding="utf-8")

# Migration plan: which files go to which subdirectory
MIGRATION = {
    "da-xue.md": "da-xue",
    "lun-yu.md": "lun-yu",
    "mengzi-gaozi.md": "mengzi",
    "mengzi-gongsunchou.md": "mengzi",
    "mengzi-jingxin.md": "mengzi",
    "mengzi-lianghuiwang.md": "mengzi",
    "mengzi-lilou.md": "mengzi",
    "mengzi-tenwengong.md": "mengzi",
    "mengzi-wanzhang.md": "mengzi",
}

SUBDIR_INFO = {
    "da-xue": {"title": "大学", "weight": 20, "summary": "大学之道，在明明德。"},
    "lun-yu": {"title": "论语", "weight": 30, "summary": "学而时习之，不亦说乎。"},
    "mengzi": {"title": "孟子", "weight": 50, "summary": "孟子七篇，战国孟轲撰。"},
}

# Create subdirectories and _index.md files
for slug, info in SUBDIR_INFO.items():
    subdir = CONF / slug
    subdir.mkdir(parents=True, exist_ok=True)
    fm = f"""---
title: "{info['title']}"
date: 2026-05-20
weight: {info['weight']}
tags: ["经部", "{info['title']}"]
categories: ["经部"]
draft: false
summary: "{info['summary']}"
showToc: false
tocOpen: false
ShowShareButtons: false
---

"""
    (subdir / "_index.md").write_text(fm, encoding="utf-8")

# Move files to subdirectories
for filename, subdir_name in MIGRATION.items():
    src = CONF / filename
    dst = CONF / subdir_name / filename
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))
        print(f"  Moved: {filename} -> {subdir_name}/{filename}")
    elif not src.exists():
        print(f"  Skip (not found): {filename}")

print("Migration complete.")
