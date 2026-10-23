#!/usr/bin/env python3
"""Rebuild/check the simplified Zhuangzi from pinned, collated witnesses.

Install scripts/requirements-zhuangzi.txt, then run --check or --write.
Primary readings follow the fixed Wikisource revisions in the manifest;
Kanripo is an independent digital witness, not a source of silent substitutions.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from opencc import OpenCC
from rapidfuzz.distance import Levenshtein


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts/data/zhuangzi_sources.json"
DEFAULT_CACHE = Path.home() / ".cache/ifcalm-books/zhuangzi"
CONVERTER = OpenCC("t2s")
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
SKIP = (
    "table, small, .variant-tooltip, .reference, .references, .noprint, .noexport, "
    ".licenseContainer, .acContainer, .ws-noexport, .ws-noinclude, .navbox, "
    ".headerContainer, .sisitem, .catlinks, script, style, .annotation, .note"
)
# Chapter-specific exceptions have exact anchors, reasons, and source links.
# Keep them in data so new-source corrections survive future regeneration.
EDITORIAL_REPAIRS: dict[int, list[tuple[str, str]]] = {}
for repair in json.loads((ROOT / "scripts/data/zhuangzi_editorial_repairs.json").read_text(encoding="utf-8"))["repairs"]:
    EDITORIAL_REPAIRS.setdefault(repair["chapter"], []).append((repair["before"], repair["after"]))
REGRESSIONS = {
    1: ["若夫乘天地之正", "至人无己，神人无功，圣人无名", "洴澼絖"],
    2: ["庸也者，用也", "通也者，得也"],
    11: ["贱而不可不任者，物也", "天道之与人道也，相去远矣，不可不察也"],
    13: ["夫帝王之德，以天地为宗", "君先而臣从", "赏罚已明"],
    14: ["夫至乐者，先应之以人事"],
    18: ["食之䲡䱔", "得水则为㡭"],
    27: ["言无言，终身言，未尝言；终身不言，未尝不言"],
}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch(url: str, cache: Path, offline: bool) -> str:
    path = cache / (digest(url) + ".txt")
    if path.exists():
        return path.read_text(encoding="utf-8")
    if offline:
        raise ValueError(f"Missing cached witness: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        text = response.read().decode("utf-8")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def wiki_paragraphs(raw: str) -> list[str]:
    soup = BeautifulSoup(raw, "html.parser")
    containers = soup.select(".mw-parser-output")
    if not containers:
        raise ValueError("Missing Wikisource content container")
    content = max(containers, key=lambda tag: len(tag.get_text()))
    for node in content.select(SKIP):
        node.decompose()
    paragraphs = []
    for node in content.find_all("p"):
        if node.find("img"):
            raise ValueError("Unresolved image inside source text; resolve glyph before generation")
        text = re.sub(r"\s+", "", node.get_text()).replace("\u200b", "")
        if text:
            paragraphs.append(text)
    if not paragraphs:
        raise ValueError("Empty Wikisource text")
    return paragraphs


def kanripo_body(raw: str) -> str:
    if "#+PROPERTY: ID KR5c0126" not in raw:
        raise ValueError("Unexpected Kanripo work")
    text = re.sub(r"^#.*$|^\*+[^\n]*", "", raw, flags=re.M)
    text = re.sub(r"<pb:[^>]+>", "", text)
    text = text.replace("¶", "")
    return re.sub(r"\s+", "", text)


def letters(text: str) -> str:
    return "".join(char for char in CONVERTER.convert(text) if unicodedata.category(char).startswith("L"))


def validate_body(number: int, text: str) -> None:
    if re.search(r"[A-Za-z\ue000-\uf8ff\ufffd\u200b]|\{\{|\[\[|<[^>]+>|一作「", text):
        raise ValueError(f"Chapter {number}: residual source/encoding artifact")
    if "□" in text or len(letters(text)) < 500:
        raise ValueError(f"Chapter {number}: empty, truncated, or unresolved text")
    stack = []
    opening = {"」": "「", "』": "『", "）": "（"}
    for char in text:
        if char in opening.values():
            stack.append(char)
        elif char in opening:
            if not stack or stack.pop() != opening[char]:
                raise ValueError(f"Chapter {number}: malformed quotation/parenthesis nesting")
    if stack:
        raise ValueError(f"Chapter {number}: unclosed quotation/parenthesis")
    for phrase in REGRESSIONS.get(number, []):
        if phrase not in text:
            raise ValueError(f"Chapter {number}: missing regression passage {phrase}")
    if number == 14 and "刻意尚行" in text:
        raise ValueError("天运 still contains 刻意")


def prepare(chapter: dict, cache: Path, offline: bool) -> dict:
    wiki = fetch(chapter["wiki_url"], cache, offline)
    if str(chapter["wiki_revision"]) not in wiki:
        raise ValueError(f"Chapter {chapter['number']}: unrecognized revision")
    paragraphs = wiki_paragraphs(wiki)
    primary = "\n\n".join(paragraphs)
    if digest(primary) != chapter["wiki_text_sha256"]:
        raise ValueError(f"Chapter {chapter['number']}: primary text drift; review before updating manifest")
    text = CONVERTER.convert(primary)
    for before, after in EDITORIAL_REPAIRS.get(chapter["number"], []):
        if text.count(before) != 1:
            raise ValueError(f"Chapter {chapter['number']}: editorial repair no longer unique")
        text = text.replace(before, after)
    validate_body(chapter["number"], text)
    secondary = fetch(chapter["kanripo_url"], cache, offline)
    if digest(secondary) != chapter["kanripo_sha256"]:
        raise ValueError(f"Chapter {chapter['number']}: secondary witness checksum mismatch")
    return {"chapter": chapter, "text": text, "paragraphs": len(paragraphs),
            "wiki_raw_sha256": digest(wiki), "secondary": kanripo_body(secondary)}


def front_matter(path: Path, chapter: dict) -> str:
    original = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", original, re.S)
    if not match:
        raise ValueError(f"Missing front matter: {path}")
    fm = match.group(1)
    fm = re.sub(r"^title:.*$", f'title: "庄子-{chapter["title"]}"', fm, flags=re.M)
    fm = re.sub(r"^summary:.*$", "summary: " + json.dumps(chapter["summary"], ensure_ascii=False), fm, flags=re.M)
    fm = re.sub(r"^weight:.*\n?", "", fm, flags=re.M)
    if re.search(r"^draft:", fm, re.M):
        fm = re.sub(r"^draft:.*$", "draft: false", fm, flags=re.M)
    else:
        fm += "\ndraft: false"
    return "---\n" + fm.rstrip() + f'\nweight: {chapter["number"]}\n---\n\n'


def collation(prepared: list[dict]) -> dict:
    rows = []
    for result in prepared:
        chapter = result["chapter"]
        primary, secondary = letters(result["text"]), letters(result["secondary"])
        differences = []
        for op in Levenshtein.opcodes(primary, secondary):
            if op.tag == "equal":
                continue
            differences.append({
                "kind": op.tag, "offset": op.src_start,
                "primary": primary[op.src_start:op.src_end],
                "secondary": secondary[op.dest_start:op.dest_end],
                "before": primary[max(0, op.src_start - 15):op.src_start],
                "after": primary[op.src_end:op.src_end + 15],
            })
        rows.append({"number": chapter["number"], "title": chapter["title"], "path": chapter["path"],
                     "paragraphs": result["paragraphs"], "primary_chars": len(primary),
                     "secondary_chars": len(secondary), "wiki_url": chapter["wiki_url"],
                     "wiki_text_sha256": chapter["wiki_text_sha256"],
                     "wiki_raw_sha256": result["wiki_raw_sha256"],
                     "kanripo_url": chapter["kanripo_url"],
                     "kanripo_sha256": chapter["kanripo_sha256"],
                     "differences": differences})
    return {"policy": "Primary readings retained. Differences are version/collation candidates, not automatic errors.", "chapters": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--preview-dir", type=Path, help="Write candidate pages outside content first")
    parser.add_argument("--collation-report", type=Path)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    chapters = manifest["chapters"]
    if [c["number"] for c in chapters] != list(range(1, 34)):
        raise ValueError("Expected 33 chapters in received order")
    actual = {str(p.relative_to(ROOT)) for p in (ROOT / "content/posts/taoism/zhuangzi").glob("*.md") if p.name != "_index.md"}
    if actual != {c["path"] for c in chapters}:
        raise ValueError("Chapter paths differ from the pinned manifest")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        prepared = list(executor.map(lambda c: prepare(c, args.cache_dir, args.offline), chapters))
    # Complete source validation before changing any chapter.
    for result in prepared:
        c = result["chapter"]
        path = ROOT / c["path"]
        expected = front_matter(path, c) + result["text"] + "\n"
        if args.check:
            if path.read_text(encoding="utf-8") != expected:
                raise ValueError(f"Generated page is stale: {c['path']}")
        else:
            destination = args.preview_dir / path.name if args.preview_dir else path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(expected, encoding="utf-8")
    if args.collation_report:
        args.collation_report.parent.mkdir(parents=True, exist_ok=True)
        args.collation_report.write_text(json.dumps(collation(prepared), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{'Checked' if args.check else 'Prepared' if args.preview_dir else 'Wrote'} 33 chapters, {sum(r['paragraphs'] for r in prepared)} paragraphs; both witnesses verified.")


if __name__ == "__main__":
    main()
