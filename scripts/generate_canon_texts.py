#!/usr/bin/env python3
"""Run corpus generators from a shared collection manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "scripts" / "data" / "taozang_catalog.json"


def load_catalog(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def selected_collections(
    catalog: dict,
    collection_id: str | None,
    all_collected: bool,
    include_planned: bool,
) -> list[dict]:
    collections = catalog["collections"]
    if collection_id:
        matches = [item for item in collections if item["id"] == collection_id]
        if not matches:
            raise SystemExit(f"unknown collection id: {collection_id}")
        return matches
    if all_collected:
        return [item for item in collections if item.get("status") == "collected"]
    if include_planned:
        return collections
    return collections


def generator_paths(collections: list[dict]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for item in collections:
        generator = item.get("generator")
        if not generator:
            continue
        path = (ROOT / generator).resolve()
        if path not in seen:
            paths.append(path)
            seen.add(path)
    return paths


def print_collection_table(collections: list[dict]) -> None:
    for item in collections:
        generator = item.get("generator") or "-"
        print(f"{item['id']}\t{item['status']}\t{item['quality']}\t{generator}\t{item['target']}")


def run_generator(path: Path, retries: int) -> None:
    for attempt in range(1, retries + 2):
        try:
            subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)
            return
        except subprocess.CalledProcessError:
            if attempt > retries:
                raise
            wait_seconds = 2 * attempt
            print(
                f"Generator failed, retrying in {wait_seconds}s "
                f"({attempt}/{retries}): {path.relative_to(ROOT)}"
            )
            time.sleep(wait_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--collection", help="Run/list one collection id.")
    parser.add_argument("--all-collected", action="store_true", help="Select all collected entries.")
    parser.add_argument("--include-planned", action="store_true", help="Include planned entries when listing.")
    parser.add_argument("--list", action="store_true", help="List selected catalog entries.")
    parser.add_argument("--dry-run", action="store_true", help="Print generators without running them.")
    parser.add_argument("--retries", type=int, default=2, help="Retry a failed generator this many times.")
    args = parser.parse_args()

    catalog_path = args.catalog if args.catalog.is_absolute() else ROOT / args.catalog
    catalog = load_catalog(catalog_path)
    collections = selected_collections(
        catalog,
        args.collection,
        args.all_collected,
        args.include_planned,
    )

    if args.list:
        print_collection_table(collections)
        return

    paths = generator_paths(collections)
    if not paths:
        print("No generators found for selected collections.")
        return

    for path in paths:
        if not path.exists():
            raise SystemExit(f"generator not found: {path}")
        if args.dry_run:
            print(path.relative_to(ROOT))
            continue
        print(f"Running {path.relative_to(ROOT)}")
        run_generator(path, args.retries)


if __name__ == "__main__":
    main()
