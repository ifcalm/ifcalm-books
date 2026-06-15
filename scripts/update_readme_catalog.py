#!/usr/bin/env python3
"""Update the managed catalog sections in README.md from content/posts."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = REPO_ROOT / "content" / "posts"
README_PATH = REPO_ROOT / "README.md"
SUMMARY_START = "<!-- catalog-summary:start -->"
SUMMARY_END = "<!-- catalog-summary:end -->"
CATALOG_START = "<!-- catalog:start -->"
CATALOG_END = "<!-- catalog:end -->"

RANGE_DIR_RE = re.compile(r"^\d{3}-\d{3}$")
FORCE_WORK_DIRS = {
    Path("confucius/yi-jing"),
}
FORCE_CATEGORY_DIRS = {
    Path("taoism/cultivation"),
    Path("taoism/ethics"),
    Path("taoism/ritual"),
}
SPECIAL_WORKS = {
    Path("taoism/classics"): [
        ("庄子", CONTENT_ROOT / "butterfly"),
    ],
}
SKIPPED_TOP_LEVEL = {"butterfly"}


@dataclass
class CatalogNode:
    title: str
    path: Path
    is_category: bool
    weight: int = 10_000
    documents: set[Path] = field(default_factory=set)
    children: list["CatalogNode"] = field(default_factory=list)

    @property
    def content_count(self) -> int:
        return len(self.documents)


def parse_front_matter_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None

    with path.open(encoding="utf-8-sig") as handle:
        in_front_matter = False
        for line_number, line in enumerate(handle):
            stripped = line.strip()
            if line_number == 0 and stripped == "---":
                in_front_matter = True
                continue
            if in_front_matter and stripped == "---":
                break
            if not in_front_matter or not stripped.startswith(f"{key}:"):
                continue

            value = stripped.split(":", 1)[1].strip()
            if not value:
                return None
            if value[0] in {'"', "'"}:
                try:
                    return str(ast.literal_eval(value))
                except (SyntaxError, ValueError):
                    pass
            return value
    return None


def title_for_file(path: Path) -> str:
    return parse_front_matter_value(path, "title") or path.stem


def weight_for_file(path: Path) -> int:
    raw_weight = parse_front_matter_value(path, "weight")
    if raw_weight is None:
        return 10_000
    try:
        return int(raw_weight)
    except ValueError:
        return 10_000


def direct_documents(path: Path) -> list[Path]:
    return sorted(
        file
        for file in path.glob("*.md")
        if file.name != "_index.md"
    )


def descendant_documents(path: Path) -> set[Path]:
    return {
        file
        for file in path.rglob("*.md")
        if file.name != "_index.md"
    }


def child_directories(path: Path) -> list[Path]:
    return sorted(child for child in path.iterdir() if child.is_dir())


def title_for_directory(path: Path) -> str:
    index_title = parse_front_matter_value(path / "_index.md", "title")
    if index_title:
        return index_title

    titles = [title_for_file(file) for file in direct_documents(path)]
    if len(titles) == 1:
        return titles[0]
    if titles:
        prefixes = {
            re.split(r"[-—：:]", title, maxsplit=1)[0].strip()
            for title in titles
        }
        if len(prefixes) == 1:
            return prefixes.pop()
    return path.name


def weight_for_directory(path: Path) -> int:
    index_weight = weight_for_file(path / "_index.md")
    if index_weight != 10_000:
        return index_weight
    weights = [weight_for_file(file) for file in direct_documents(path)]
    return min(weights, default=10_000)


def is_work_directory(path: Path) -> bool:
    relative = path.relative_to(CONTENT_ROOT)
    if relative in FORCE_CATEGORY_DIRS:
        return False
    if relative in FORCE_WORK_DIRS:
        return True

    children = child_directories(path)
    documents = direct_documents(path)
    if not children:
        return bool(documents)
    if documents:
        return False
    return all(RANGE_DIR_RE.fullmatch(child.name) for child in children)


def make_work(path: Path, title: str | None = None) -> CatalogNode:
    return CatalogNode(
        title=title or title_for_directory(path),
        path=path,
        is_category=False,
        weight=weight_for_directory(path),
        documents=descendant_documents(path),
    )


def make_file_work(path: Path) -> CatalogNode:
    return CatalogNode(
        title=title_for_file(path),
        path=path,
        is_category=False,
        weight=weight_for_file(path),
        documents={path},
    )


def build_category(path: Path) -> CatalogNode:
    node = CatalogNode(
        title=title_for_directory(path),
        path=path,
        is_category=True,
        weight=weight_for_directory(path),
    )

    for document in direct_documents(path):
        node.children.append(make_file_work(document))

    for child in child_directories(path):
        if is_work_directory(child):
            node.children.append(make_work(child))
        else:
            node.children.append(build_category(child))

    relative = path.relative_to(CONTENT_ROOT)
    for title, special_path in SPECIAL_WORKS.get(relative, []):
        node.children.append(make_work(special_path, title))

    node.children.sort(key=lambda child: (child.weight, child.title, child.path.as_posix()))
    node.documents = set().union(*(child.documents for child in node.children))
    return node


def relative_link(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).as_posix()
    return f"{relative}/" if path.is_dir() else relative


def render_children(node: CatalogNode, depth: int = 0) -> list[str]:
    if not node.children:
        return [f"{'  ' * depth}- 暂无收录"]

    lines: list[str] = []
    for child in node.children:
        indent = "  " * depth
        link = relative_link(child.path)
        if child.is_category:
            lines.append(f"{indent}- **[{child.title}]({link})**")
            lines.extend(render_children(child, depth + 1))
        else:
            lines.append(
                f"{indent}- [{child.title}]({link})"
                f"（{child.content_count} 个内容单元）"
            )
    return lines


def walk_nodes(node: CatalogNode):
    yield node
    for child in node.children:
        yield from walk_nodes(child)


def validate_catalog(top_level: list[CatalogNode]) -> tuple[int, int]:
    all_documents = descendant_documents(CONTENT_ROOT)
    work_nodes = [
        node
        for top_node in top_level
        for node in walk_nodes(top_node)
        if not node.is_category
    ]

    ownership: dict[Path, list[str]] = {}
    for node in work_nodes:
        for document in node.documents:
            ownership.setdefault(document, []).append(node.title)

    missing = sorted(all_documents - ownership.keys())
    duplicated = {
        path: titles
        for path, titles in ownership.items()
        if len(titles) > 1
    }
    unexpected = sorted(ownership.keys() - all_documents)

    if missing or duplicated or unexpected:
        if missing:
            print("Uncataloged documents:", file=sys.stderr)
            for path in missing:
                print(f"  {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        if duplicated:
            print("Documents assigned more than once:", file=sys.stderr)
            for path, titles in sorted(duplicated.items()):
                print(
                    f"  {path.relative_to(REPO_ROOT)}: {', '.join(titles)}",
                    file=sys.stderr,
                )
        if unexpected:
            print("Catalog references missing documents:", file=sys.stderr)
            for path in unexpected:
                print(f"  {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        raise SystemExit(1)

    return len(work_nodes), len(all_documents)


def build_catalog() -> tuple[list[CatalogNode], int, int]:
    top_level = [
        build_category(path)
        for path in child_directories(CONTENT_ROOT)
        if path.name not in SKIPPED_TOP_LEVEL and (path / "_index.md").exists()
    ]
    top_level.sort(key=lambda node: (node.weight, node.title, node.path.as_posix()))
    work_count, document_count = validate_catalog(top_level)
    return top_level, work_count, document_count


def render_summary(work_count: int, document_count: int) -> str:
    return "\n".join(
        [
            SUMMARY_START,
        (
            f"当前共收录 **{work_count} 个书目条目**、"
            f"**{document_count} 个 Markdown 正文单元**。"
            "同一书的卷、篇或章节文件在下方合并为一个书目条目；"
            "异译本和不同版本分别列出。"
        ),
            SUMMARY_END,
        ]
    )


def render_catalog(top_level: list[CatalogNode]) -> str:
    lines = [
        CATALOG_START,
        (
            "> 下方分类树由 "
            "[`scripts/update_readme_catalog.py`](scripts/update_readme_catalog.py) "
            "根据 `content/posts` 更新。新增或调整收录后运行 "
            "`python3 scripts/update_readme_catalog.py`；"
            "GitHub Actions 会检查该区块是否与当前收录保持同步。"
        ),
        "",
        "## 收录目录",
        "",
    ]

    for top_node in top_level:
        lines.append(f"### [{top_node.title}]({relative_link(top_node.path)})")
        lines.append("")
        lines.extend(render_children(top_node))
        lines.append("")

    lines.append(CATALOG_END)
    return "\n".join(lines).rstrip()


def replace_managed_block(
    content: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = content.find(start_marker)
    end = content.find(end_marker)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"Missing managed README block: {start_marker}")
    end += len(end_marker)
    return content[:start] + replacement + content[end:]


def update_readme(
    current: str,
    summary: str,
    catalog: str,
) -> str:
    if SUMMARY_START not in current:
        summary_pattern = re.compile(
            r"^当前共收录 \*\*\d+ 个书目条目\*\*、"
            r"\*\*\d+ 个 Markdown 正文单元\*\*。.*$",
            re.MULTILINE,
        )
        current, replacements = summary_pattern.subn(summary, current, count=1)
        if replacements != 1:
            raise ValueError("Could not locate the README catalog summary.")
    else:
        current = replace_managed_block(
            current,
            SUMMARY_START,
            SUMMARY_END,
            summary,
        )

    if CATALOG_START not in current:
        heading = "\n## 收录目录\n"
        catalog_start = current.find(heading)
        if catalog_start == -1:
            raise ValueError("Could not locate the README catalog heading.")
        current = current[:catalog_start].rstrip() + "\n\n" + catalog + "\n"
    else:
        current = replace_managed_block(
            current,
            CATALOG_START,
            CATALOG_END,
            catalog,
        )

    return current.rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if README.md is not up to date",
    )
    args = parser.parse_args()

    if not README_PATH.exists():
        print("README.md does not exist; create it before updating the catalog.", file=sys.stderr)
        raise SystemExit(1)

    top_level, work_count, document_count = build_catalog()
    current = README_PATH.read_text(encoding="utf-8")
    updated = update_readme(
        current,
        render_summary(work_count, document_count),
        render_catalog(top_level),
    )
    if args.check:
        if current != updated:
            print("README.md catalog sections are out of date.", file=sys.stderr)
            raise SystemExit(1)
        print("README.md catalog sections are up to date.")
        return

    README_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated catalog sections in {README_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
