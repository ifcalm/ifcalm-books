#!/usr/bin/env python3
import argparse
import concurrent.futures
import html
import json
import re
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path


API_URL = "https://cbdata.dila.edu.tw/stable/juans?work=T0220&juan={juan}&work_info=1&toc=1"
OUT_ROOT = Path(__file__).resolve().parents[1] / "content/posts/buddha/jingzang/bore/da-bore"


class CbetaJuanParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self.current = None
        self.capture_depth = 0
        self.skip_stack = []
        self.div_stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        parent_skip = bool(self.skip_stack and self.skip_stack[-1])
        starts_inline_note = (not parent_skip) and "inline-note" in classes
        if starts_inline_note:
            self._append_note_boundary()
        skip = parent_skip
        skip = skip or tag == "a" or "lb" in classes or "lineInfo" in classes or "noteAnchor" in classes
        skip = skip or "inline-note" in classes
        self.skip_stack.append(skip)
        if skip:
            return

        if tag == "div":
            div_kind = None
            if "lg" in classes:
                div_kind = "lg"
            elif "lg-row" in classes:
                div_kind = "lg-row"
            self.div_stack.append(div_kind)

            if div_kind == "lg":
                if self.current is not None:
                    self._finish_block()
                self.current = {"type": "verse", "level": None, "parts": []}
            elif div_kind == "lg-row" and self.current is not None and self.current["type"] == "verse":
                if self.current["parts"]:
                    self.current["parts"].append("\n")

        if tag == "p":
            if self.current is not None:
                self._finish_block()
            block_type = "paragraph"
            level = None
            if "head" in classes:
                block_type = "head"
                level = attrs.get("data-head-level")
            elif "byline" in classes:
                block_type = "byline"
            self.current = {"type": block_type, "level": level, "parts": []}

        if tag == "span" and ({"t", "pc"} & classes):
            self.capture_depth += 1

    def handle_endtag(self, tag):
        skip = self.skip_stack.pop() if self.skip_stack else False
        if skip:
            return
        if tag == "span" and self.capture_depth:
            self.capture_depth -= 1
        if tag == "div":
            div_kind = self.div_stack.pop() if self.div_stack else None
            if div_kind == "lg" and self.current is not None and self.current["type"] == "verse":
                self._finish_block()
        if tag == "p" and self.current is not None:
            self._finish_block()

    def handle_data(self, data):
        if self.skip_stack and self.skip_stack[-1]:
            return
        if self.capture_depth and self.current is not None:
            self.current["parts"].append(data)

    def _finish_block(self):
        text = "".join(self.current["parts"])
        if self.current["type"] == "verse":
            lines = [re.sub(r"\s+", "", line) for line in text.splitlines()]
            text = "\n".join(line for line in lines if line)
        else:
            text = re.sub(r"\s+", "", text)
            text = re.sub(r"。{2,}", "。", text)
        if text:
            self.blocks.append((self.current["type"], self.current["level"], text))
        self.current = None

    def _append_note_boundary(self):
        if self.current is None:
            return
        text = "".join(self.current["parts"]).rstrip()
        if not text:
            return
        if text[-1] not in "。！？；：，、（）《》「」『』“”‘’()[]{}…":
            self.current["parts"].append("。")


def chinese_number(num):
    digits = "零一二三四五六七八九"

    def below_100(n):
        if n < 10:
            return digits[n]
        ten, one = divmod(n, 10)
        if ten == 1:
            return "十" + (digits[one] if one else "")
        return digits[ten] + "十" + (digits[one] if one else "")

    if num < 100:
        return below_100(num)
    hundred, rest = divmod(num, 100)
    if rest == 0:
        return digits[hundred] + "百"
    if rest < 10:
        return digits[hundred] + "百零" + digits[rest]
    return digits[hundred] + "百" + below_100(rest)


def range_dir(juan):
    start = ((juan - 1) // 30) * 30 + 1
    end = start + 29
    return start, end, f"{start:03d}-{end:03d}"


def fetch_text(url, retries=3):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return subprocess.check_output(
                ["curl", "-sL", "--max-time", "45", "-A", "ifcalm-books-import/1.0", url],
                stderr=subprocess.STDOUT,
            ).decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            time.sleep(attempt * 1.5)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def fetch_blocks(juan):
    raw = fetch_text(API_URL.format(juan=juan))
    data = json.loads(raw)
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"卷{juan} API 返回为空")
    parser = CbetaJuanParser()
    parser.feed(html.unescape(results[0]))
    blocks = parser.blocks
    if not blocks:
        raise RuntimeError(f"卷{juan} 未解析到正文段落")
    return drop_title_and_translator(blocks)


def normalize_title(text):
    return re.sub(r"\s+", "", text)


def drop_title_and_translator(blocks):
    cleaned = []
    for block in blocks:
        text = normalize_title(block[2])
        if re.fullmatch(r"大般若波羅蜜多經卷第[零一二三四五六七八九十百]+", text):
            continue
        if text == "三藏法師玄奘奉詔譯":
            continue
        cleaned.append(block)
    return cleaned


def front_matter(juan):
    cn = chinese_number(juan)
    return [
        "---",
        f'title: "大般若波罗蜜多经 卷第{cn}"',
        "date: 2026-05-02",
        'tags: ["大般若经"]',
        'categories: ["佛学"]',
        "draft: false",
        f'summary: "大般若波罗蜜多经卷第{cn}"',
        "showToc: false",
        "tocOpen: false",
        "ShowShareButtons: false",
        f"weight: {juan}",
        "---",
        "",
    ]


def render_markdown(juan, blocks):
    lines = front_matter(juan)
    for block_type, level, text in blocks:
        if block_type == "head":
            try:
                heading_level = max(2, min(6, int(level or 2)))
            except ValueError:
                heading_level = 2
            lines.append("#" * heading_level + " " + text)
        elif block_type == "verse":
            lines.append("  \n".join(text.splitlines()))
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_range_indexes():
    for start in range(1, 601, 30):
        end = start + 29
        dirname = f"{start:03d}-{end:03d}"
        path = OUT_ROOT / dirname
        path.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            [
                "---",
                f'title: "大般若经 卷第{chinese_number(start)}至卷第{chinese_number(end)}"',
                "date: 2026-05-02",
                'tags: ["大般若经"]',
                'categories: ["佛学"]',
                "draft: false",
                f'summary: "大般若经卷第{chinese_number(start)}至卷第{chinese_number(end)}"',
                "showToc: false",
                "tocOpen: false",
                "ShowShareButtons: false",
                f"weight: {start}",
                "---",
                "",
            ]
        )
        (path / "_index.md").write_text(content, encoding="utf-8")


def write_juan(juan):
    blocks = fetch_blocks(juan)
    _, _, dirname = range_dir(juan)
    path = OUT_ROOT / dirname / f"bore-{juan:03d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(juan, blocks), encoding="utf-8")
    return juan, len(blocks), path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=600)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    if args.start < 1 or args.end > 600 or args.start > args.end:
        raise SystemExit("卷号范围必须在 1..600 内")

    write_range_indexes()
    juans = list(range(args.start, args.end + 1))
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(write_juan, juan): juan for juan in juans}
        for future in concurrent.futures.as_completed(future_map):
            juan, block_count, path = future.result()
            completed += 1
            print(f"[{completed:03d}/{len(juans):03d}] 卷{juan:03d}: {block_count} blocks -> {path}")


if __name__ == "__main__":
    main()
