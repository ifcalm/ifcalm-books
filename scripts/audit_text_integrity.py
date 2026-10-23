#!/usr/bin/env python3
"""Read-only checks for transcription artifacts in the current classical corpus.

This detects mechanical damage, not textual accuracy. Edition differences,
quotation punctuation, and inherited lacunae require external witnesses.
Run: python3 scripts/audit_text_integrity.py --output /tmp/text-integrity.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private_use": re.compile(r"[\ue000-\uf8ff\U000f0000-\U000ffffd\U00100000-\U0010fffd]"),
    "replacement_character": re.compile("\ufffd"),
    "latin_text": re.compile(r"[A-Za-z][A-Za-z0-9@\u00c0-\u024f]*"),
    "source_markup": re.compile(r"\{\{|\}\}|\[\[|\]\]|</?ref\b|\b(?:alt|alr)="),
    "lacuna": re.compile("□"),
}


def audit(root: Path) -> dict:
    units = []
    findings = []
    bodies: dict[str, list[str]] = defaultdict(list)
    for path in sorted((root / "content/posts").rglob("*.md")):
        if path.name == "_index.md":
            continue
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(root))
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        if not match:
            findings.append({"path": relative, "line": 1, "kind": "missing_front_matter"})
            continue
        front_matter = match.group(1)
        body = text[match.end():]
        title = re.search(r"^title:\s*(.+)$", front_matter, re.M)
        weight = re.search(r"^weight:\s*(\d+)\s*$", front_matter, re.M)
        units.append({
            "path": relative,
            "title": title.group(1).strip('"\'') if title else None,
            "weight": int(weight.group(1)) if weight else None,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "body_characters": len(body),
        })
        if not body.strip():
            findings.append({"path": relative, "line": text.count("\n") + 1, "kind": "empty_body"})
        canonical = re.sub(r"\s+", "", body)
        if canonical:
            bodies[canonical].append(relative)
        in_code = False
        for number, line in enumerate(text.splitlines(), 1):
            if number <= text[:match.end()].count("\n"):
                continue
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            for kind, pattern in PATTERNS.items():
                for hit in pattern.finditer(line):
                    findings.append({
                        "path": relative, "line": number, "kind": kind,
                        "token": hit.group(),
                        "context": line[max(0, hit.start() - 24):hit.end() + 24],
                    })
    return {
        "unit_count": len(units),
        "units": units,
        "findings": findings,
        "duplicate_bodies": [paths for paths in bodies.values() if len(paths) > 1],
        "interpretation": "Candidates only; lacuna signs may be intentional and Latin text may be legitimate.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--snapshot", type=Path, help="Compare local hashes with a previous integrity JSON.")
    args = parser.parse_args()
    result = audit(args.root.resolve())
    if args.snapshot:
        previous = json.loads(args.snapshot.read_text(encoding="utf-8"))
        before = {u["path"]: u["sha256"] for u in previous["units"]}
        after = {u["path"]: u["sha256"] for u in result["units"]}
        result["changed_since_snapshot"] = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Checked {result['unit_count']} files; {len(result['findings'])} mechanical candidates. Saved {args.output}")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
