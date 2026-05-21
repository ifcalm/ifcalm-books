#!/usr/bin/env python3
"""Clean Wikisource raw wikitext into plain markdown for 二十四史."""

from __future__ import annotations

import re


def remove_balanced(text: str, open_str: str, close_str: str) -> str:
    """Remove balanced open/close pairs, including content between them."""
    while open_str in text:
        start = text.index(open_str)
        depth = 0
        end = None
        olen = len(open_str)
        clen = len(close_str)
        for i in range(start, len(text) - clen + 1):
            if text[i:i + olen] == open_str:
                depth += 1
            elif text[i:i + clen] == close_str:
                depth -= 1
                if depth == 0:
                    end = i + clen
                    break
        if end is None:
            break
        text = text[:start] + text[end:]
    return text


def clean_wikitext(text: str) -> str:
    """Transform Wikisource wikitext into clean markdown."""

    # ── Phase 1: Remove structural templates ──
    structural = (
        "header2", "header", "textquality", "footer", "reflist",
        "wikipedia", "東漢作品", "西晉作品", "唐朝作品", "元朝作品",
        "明朝作品", "清朝作品", "南北朝作品", "北宋作品", "南宋作品",
        "北齊作品", "南朝梁", "南朝宋", "五代作品", "後晉作品",
        "宋朝作品", "元朝作品", "南北朝", "notice", "edition",
    )
    for name in structural:
        text = remove_balanced(text, "{{" + name, "}}")

    # ── Phase 2: Clean -{...}- language variants ──
    # These cannot be nested, so a simple greedy regex works.
    # Remove zh-prefixed variants entirely (they're alternate renderings).
    text = re.sub(r'-\{zh[^}]*\}-', '', text)
    # For other variants, keep the content.
    text = re.sub(r'-\{([^{}]+)\}-', r'\1', text)

    # ── Phase 3: Expand inline templates ──
    # {{ProperNoun|X}} or {{ProperNoun|X|Y}} → X
    text = re.sub(r'\{\{ProperNoun\|([^|}]+)(?:\|[^|}]+)?\}\}', r'\1', text)
    # {{WavyBookMark|X}} → 《X》
    text = re.sub(r'\{\{WavyBookMark\|([^|}]+)\}\}', r'《\1》', text)
    # {{YL|X}} → X
    text = re.sub(r'\{\{YL\|([^|}]+)\}\}', r'\1', text)
    # {{標|X}} → X
    text = re.sub(r'\{\{標\|([^|}]+)\}\}', r'\1', text)
    # {{*|X}} → X
    text = re.sub(r'\{\{\*\|([^|}]+)\}\}', r'\1', text)
    # {{注意|text=X}} or {{注意|X}} → > X
    text = re.sub(r'\{\{注意\|text=([^}]+)\}\}', r'> \1', text)
    text = re.sub(r'\{\{注意\|([^}]+)\}\}', r'> \1', text)
    # {{!}} → |
    text = text.replace('{{!}}', '|')

    # ── Phase 4: Remove remaining simple templates ──
    # Non-nested {{X}} or {{X|Y}} — strip them.
    text = re.sub(r'\{\{[^{}|]+\}\}', '', text)
    # Any remaining balanced {{...}} pairs.
    text = remove_balanced(text, "{{", "}}")

    # ── Phase 5: HTML elements ──
    text = re.sub(r'<ref\b[^>]*>.*?</ref>', '', text, flags=re.S)
    text = re.sub(r'<ref\b[^>]*?/>', '', text)
    text = re.sub(r'</?div[^>]*>', '', text)
    text = re.sub(r'</?br\s*/?>', '', text)
    text = re.sub(r'</?span[^>]*>', '', text)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = re.sub(r'__\w+__', '', text)

    # ── Phase 6: Wikilinks ──
    # [[target|display]] → display; [[target]] → target
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)

    # ── Phase 7: Headings ──
    # == X == → ### X  (add 1 level so page title is h1, category heading h2, section h3)
    def convert_heading(m: re.Match[str]) -> str:
        marks, title = m.group(1), m.group(2).strip()
        level = min(len(marks) + 1, 6)
        return "#" * level + " " + title

    text = re.sub(r'^(={2,6})\s*(.+?)\s*\1\s*$', convert_heading, text, flags=re.M)

    # ── Phase 8: Inline markup & whitespace ──
    text = re.sub(r"'''?", '', text)  # bold/italic
    text = text.replace('　', '')  # full-width space
    text = text.replace('​', '')  # zero-width space
    text = text.replace('&nbsp;', ' ')

    # Final safety pass: remove any remaining -{...}- patterns
    text = re.sub(r'-\{[^}]+\}-', '', text)

    # Normalize blank lines
    lines = [line.rstrip() for line in text.splitlines()]
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
