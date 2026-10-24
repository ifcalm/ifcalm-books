#!/usr/bin/env python3
"""扫描 content 中的扩展区生僻字，从花园明朝裁出子集，生成 static/fonts/HanaMin{A,B,C}-subset.woff2。

用法：python3 scripts/build_rare_font.py <含 HanaMinA/B/C.otf 的目录>
依赖：pip install fonttools brotli
字体来源：https://github.com/cjkvi/HanaMinAFDKO/releases
"""
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "fonts"


def is_rare(o):
    return 0x3400 <= o <= 0x4DBF or 0x20000 <= o <= 0x2EBEF


def used_chars():
    chars = set()
    for p in (ROOT / "content").rglob("*.md"):
        chars.update(ord(c) for c in p.read_text(encoding="utf8") if is_rare(ord(c)))
    return chars


def main(src):
    src = Path(src)
    remaining = used_chars()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in "ABC":
        path = src / f"HanaMin{name}.otf"
        cmap = set(TTFont(path, lazy=True).getBestCmap())
        cps = sorted(remaining & cmap)
        remaining -= set(cps)
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = []
        opts.name_IDs = ["*"]
        opts.notdef_outline = False
        font = subset.load_font(str(path), opts)
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=cps)
        sub.subset(font)
        out = OUT / f"HanaMin{name}-subset.woff2"
        subset.save_font(font, str(out), opts)
        print(f"{name}: {len(cps)} 字 -> {out.name} ({out.stat().st_size} B)")
    if remaining:
        print("未覆盖：", "".join(chr(c) for c in sorted(remaining)))


if __name__ == "__main__":
    main(sys.argv[1])
