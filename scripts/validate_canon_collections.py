#!/usr/bin/env python3
"""Validate generated canon collections against a shared manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "scripts" / "data" / "taozang_catalog.json"
DEFAULT_FORBIDDEN = re.compile(
    r"\{\{|\}\}|\[\[|\]\]|Category:|__NOEDITSECTION__|<onlyinclude|</onlyinclude>|aliases:"
)


@dataclass
class ValidationResult:
    id: str
    title: str
    status: str
    ok: bool
    content_files: int | None = None
    expected_content_files: int | None = None
    section_headings: int | None = None
    expected_section_headings: int | None = None
    missing_chars: int | None = None
    expected_missing_chars: int | None = None
    private_use_chars: int | None = None
    expected_private_use_chars: int | None = None
    issues: list[str] | None = None


def load_catalog(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(path for path in target.rglob("*.md") if path.name != "_index.md")


def count_headings(files: list[Path]) -> int:
    total = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        total += len(re.findall(r"^###\s+.+$", text, flags=re.M))
    return total


def count_missing_chars(files: list[Path]) -> int:
    return sum(path.read_text(encoding="utf-8").count("□") for path in files)


def count_private_use_chars(files: list[Path]) -> int:
    return sum(
        1
        for path in files
        for char in path.read_text(encoding="utf-8")
        if "\ue000" <= char <= "\uf8ff"
    )


def find_forbidden(files: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if DEFAULT_FORBIDDEN.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{number}")
                break
    return hits


def validate_collection(item: dict) -> ValidationResult:
    issues: list[str] = []
    target = ROOT / item["target"]
    expected = item.get("expected", {})

    if item.get("status") != "collected":
        return ValidationResult(
            id=item["id"],
            title=item["title"],
            status=item["status"],
            ok=True,
            issues=[],
        )

    if not target.exists():
        return ValidationResult(
            id=item["id"],
            title=item["title"],
            status=item["status"],
            ok=False,
            issues=[f"target missing: {item['target']}"],
        )

    if target.is_dir() and not (target / "_index.md").exists():
        issues.append("directory target is missing _index.md")

    files = markdown_files(target)
    content_files = len(files)
    expected_content_files = expected.get("content_files")
    if expected_content_files is not None and content_files != expected_content_files:
        issues.append(f"content files {content_files} != expected {expected_content_files}")

    section_headings = count_headings(files)
    expected_section_headings = expected.get("section_headings")
    if expected_section_headings is not None and section_headings != expected_section_headings:
        issues.append(f"section headings {section_headings} != expected {expected_section_headings}")

    missing_chars = count_missing_chars(files)
    expected_missing_chars = expected.get("missing_chars")
    if expected_missing_chars is not None and missing_chars != expected_missing_chars:
        issues.append(f"missing chars {missing_chars} != expected {expected_missing_chars}")

    private_use_chars = count_private_use_chars(files)
    expected_private_use_chars = expected.get("private_use_chars", 0)
    if private_use_chars != expected_private_use_chars:
        issues.append(
            f"private-use chars {private_use_chars} != expected {expected_private_use_chars}"
        )

    forbidden = find_forbidden(files)
    if forbidden:
        issues.append("forbidden source artifacts in " + ", ".join(forbidden[:8]))

    return ValidationResult(
        id=item["id"],
        title=item["title"],
        status=item["status"],
        ok=not issues,
        content_files=content_files,
        expected_content_files=expected_content_files,
        section_headings=section_headings,
        expected_section_headings=expected_section_headings,
        missing_chars=missing_chars,
        expected_missing_chars=expected_missing_chars,
        private_use_chars=private_use_chars,
        expected_private_use_chars=expected_private_use_chars,
        issues=issues,
    )


def selected_collections(catalog: dict, collection_id: str | None, include_planned: bool) -> list[dict]:
    collections = catalog["collections"]
    if collection_id:
        matches = [item for item in collections if item["id"] == collection_id]
        if not matches:
            raise SystemExit(f"unknown collection id: {collection_id}")
        return matches
    if include_planned:
        return collections
    return [item for item in collections if item.get("status") == "collected"]


def print_text(results: list[ValidationResult]) -> None:
    for result in results:
        marker = "ok" if result.ok else "fail"
        print(f"{marker}\t{result.id}\t{result.title}")
        if result.content_files is not None:
            print(
                f"  files {result.content_files}/{result.expected_content_files}; "
                f"headings {result.section_headings}/{result.expected_section_headings}; "
                f"missing {result.missing_chars}/{result.expected_missing_chars}; "
                f"pua {result.private_use_chars}/{result.expected_private_use_chars}"
            )
        for issue in result.issues or []:
            print(f"  - {issue}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--collection", help="Validate one collection id.")
    parser.add_argument("--include-planned", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args()

    catalog_path = args.catalog if args.catalog.is_absolute() else ROOT / args.catalog
    catalog = load_catalog(catalog_path)
    results = [
        validate_collection(item)
        for item in selected_collections(catalog, args.collection, args.include_planned)
    ]

    if args.json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        print_text(results)

    if not all(result.ok for result in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
