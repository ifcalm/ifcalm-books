#!/usr/bin/env python3
"""Generate a focused batch of high-frequency classical works.

Collected works:

* 百家姓 and 千字文 under 蒙学.
* 高僧传 from CBETA/CBData T2059 under 佛学/史传.
* 说文解字 under 小学.
* 世说新语 under 笔记.

For the non-Buddhist texts, Chinese Wikisource raw pages are used as the
repeatable text source. For 高僧传, CBData's stable juan endpoint is used so the
script can validate Taisho number, category, and juan count before rendering.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from wikitext_cleaner import remove_balanced

from generate_bore_from_cbdata import CbetaJuanParser, chinese_number, fetch_text


ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "posts"
USER_AGENT = "ifcalm-books text collector; contact: https://books.ifcalm.org/"
WIKISOURCE_RAW = "https://zh.wikisource.org/w/index.php"
CBETA_API = "https://cbdata.dila.edu.tw/stable/juans?work={work}&juan={juan}&work_info=1&toc=1"
DATE = "2026-06-23"
DRAFT = True
FETCH_DELAY = 0.05


@dataclass(frozen=True)
class SimpleText:
    key: str
    title: str
    tag: str
    target: str
    slug: str
    wiki_title: str
    root_title: str
    root_summary: str
    root_weight: int
    work_summary: str
    work_weight: int
    mode: str
    expected_markers: tuple[str, ...]


@dataclass(frozen=True)
class WikiUnit:
    title: str
    traditional_title: str
    slug: str
    wiki_title: str


BAIJIA_XING = SimpleText(
    key="baijia-xing",
    title="百家姓",
    tag="百家姓",
    target="mengxue/baijia-xing",
    slug="baijia-xing",
    wiki_title="百家姓",
    root_title="蒙学",
    root_summary="童蒙识字与韵文经典。",
    root_weight=8,
    work_summary="百家姓，传统姓氏识字蒙书。",
    work_weight=10,
    mode="poem",
    expected_markers=("趙錢孫李", "司徒司空"),
)

QIAN_ZI_WEN = SimpleText(
    key="qian-zi-wen",
    title="千字文",
    tag="千字文",
    target="mengxue/qian-zi-wen",
    slug="qian-zi-wen",
    wiki_title="千字文",
    root_title="蒙学",
    root_summary="童蒙识字与韵文经典。",
    root_weight=8,
    work_summary="千字文，南朝梁周兴嗣撰，传统识字韵文。",
    work_weight=20,
    mode="poem",
    expected_markers=("天地玄黃", "焉哉乎也"),
)


SHI_SHUO_UNITS = (
    WikiUnit("序", "序", "000-xu", "世說新語/序"),
    WikiUnit("德行", "德行", "001-de-xing", "世說新語/德行"),
    WikiUnit("言语", "言語", "002-yan-yu", "世說新語/言語"),
    WikiUnit("政事", "政事", "003-zheng-shi", "世說新語/政事"),
    WikiUnit("文学", "文學", "004-wen-xue", "世說新語/文學"),
    WikiUnit("方正", "方正", "005-fang-zheng", "世說新語/方正"),
    WikiUnit("雅量", "雅量", "006-ya-liang", "世說新語/雅量"),
    WikiUnit("识鉴", "識鑒", "007-shi-jian", "世說新語/識鑒"),
    WikiUnit("赏誉", "賞譽", "008-shang-yu", "世說新語/賞譽"),
    WikiUnit("品藻", "品藻", "009-pin-zao", "世說新語/品藻"),
    WikiUnit("规箴", "規箴", "010-gui-zhen", "世說新語/規箴"),
    WikiUnit("捷悟", "捷悟", "011-jie-wu", "世說新語/捷悟"),
    WikiUnit("夙惠", "夙惠", "012-su-hui", "世說新語/夙惠"),
    WikiUnit("豪爽", "豪爽", "013-hao-shuang", "世說新語/豪爽"),
    WikiUnit("容止", "容止", "014-rong-zhi", "世說新語/容止"),
    WikiUnit("自新", "自新", "015-zi-xin", "世說新語/自新"),
    WikiUnit("企羡", "企羡", "016-qi-xian", "世說新語/企羡"),
    WikiUnit("伤逝", "傷逝", "017-shang-shi", "世說新語/傷逝"),
    WikiUnit("栖逸", "棲逸", "018-qi-yi", "世說新語/棲逸"),
    WikiUnit("贤媛", "賢媛", "019-xian-yuan", "世說新語/賢媛"),
    WikiUnit("术解", "術解", "020-shu-jie", "世說新語/術解"),
    WikiUnit("巧艺", "巧蓺", "021-qiao-yi", "世說新語/巧蓺"),
    WikiUnit("宠礼", "寵禮", "022-chong-li", "世說新語/寵禮"),
    WikiUnit("任诞", "任誕", "023-ren-dan", "世說新語/任誕"),
    WikiUnit("简傲", "簡傲", "024-jian-ao", "世說新語/簡傲"),
    WikiUnit("排调", "排調", "025-pai-diao", "世說新語/排調"),
    WikiUnit("轻诋", "輕詆", "026-qing-di", "世說新語/輕詆"),
    WikiUnit("假谲", "假譎", "027-jia-jue", "世說新語/假譎"),
    WikiUnit("黜免", "黜免", "028-chu-mian", "世說新語/黜免"),
    WikiUnit("俭啬", "儉嗇", "029-jian-se", "世說新語/儉嗇"),
    WikiUnit("汰侈", "汰侈", "030-tai-chi", "世說新語/汰侈"),
    WikiUnit("忿狷", "忿狷", "031-fen-juan", "世說新語/忿狷"),
    WikiUnit("谗险", "讒險", "032-chan-xian", "世說新語/讒險"),
    WikiUnit("尤悔", "尤悔", "033-you-hui", "世說新語/尤悔"),
    WikiUnit("纰漏", "紕漏", "034-pi-lou", "世說新語/紕漏"),
    WikiUnit("惑溺", "惑溺", "035-huo-ni", "世說新語/惑溺"),
    WikiUnit("仇隙", "仇隟", "036-chou-xi", "世說新語/仇隟"),
)


FORBIDDEN_BODY_PATTERNS = [
    (re.compile(r"#REDIRECT|#重定向", re.I), "redirect"),
    (re.compile(r"\{\{|\}\}"), "raw template braces"),
    (re.compile(r"\[\[|\]\]"), "raw wiki link"),
    (re.compile(r"<[^>]+>"), "raw HTML tag"),
    (re.compile(r"Category:|分類:|分类:", re.I), "category line"),
    (re.compile(r"Textquality|Wikisource|維基文庫|CBETA|CBReader|大正藏"), "source boilerplate"),
    (re.compile(r"File:|thumb|px\|"), "image artifact"),
    (re.compile(r"__NOEDITSECTION__|__TOC__"), "MediaWiki marker"),
    (re.compile(r"�"), "replacement character"),
    (re.compile(r"[\ue000-\uf8ff]"), "private-use character"),
]


def dump_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(title: str, summary: str, tag: str, weight: int) -> str:
    return "\n".join(
        [
            "---",
            f"title: {dump_string(title)}",
            f"date: {DATE}",
            f"weight: {weight}",
            f"tags: {json.dumps([tag], ensure_ascii=False)}",
            f"draft: {'true' if DRAFT else 'false'}",
            f"summary: {dump_string(summary)}",
            "showToc: false",
            "tocOpen: false",
            "ShowShareButtons: false",
            "---",
            "",
        ]
    )


def write_page(path: Path, title: str, summary: str, tag: str, weight: int, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(front_matter(title, summary, tag, weight) + body.rstrip() + "\n", encoding="utf-8")


def fetch_wikisource_raw(title: str, follow_redirects: int = 5) -> str:
    current = title
    for _ in range(follow_redirects + 1):
        query = urllib.parse.urlencode({"title": current, "action": "raw"})
        request = urllib.request.Request(
            f"{WIKISOURCE_RAW}?{query}",
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
        redirect = re.search(r"^#(?:重定向|redirect)\s*\[\[([^]]+)\]\]", raw, flags=re.I)
        if not redirect:
            return raw
        current = redirect.group(1)
    raise ValueError(f"Too many redirects for {title}")


def strip_template(text: str, name: str) -> str:
    while "{{" + name in text:
        text = remove_balanced(text, "{{" + name, "}}")
    return text


def replace_language_variant(match: re.Match[str]) -> str:
    inner = match.group(1)
    if ":" not in inner or ";" not in inner:
        return inner
    variants: dict[str, str] = {}
    for part in inner.split(";"):
        if ":" in part:
            key, value = part.split(":", 1)
            variants[key.strip()] = value.strip()
    return variants.get("zh-hant") or variants.get("zh") or next(iter(variants.values()), "")


def clean_common_wikitext(raw: str) -> str:
    text = raw
    for name in (
        "header",
        "header2",
        "Novel",
        "Novel-f",
        "Textquality",
        "PD-old",
        "南北朝作品",
        "東漢作品",
        "梁朝作品",
    ):
        text = strip_template(text, name)

    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"-\{([^{}]+)\}-", replace_language_variant, text)
    text = re.sub(r"\{\{另\|([^{}|]+)\|[^{}]+\}\}", r"\1", text)
    for template in ("ProperNoun", "+", "yw", "*", "center"):
        pattern = re.compile(r"\{\{" + re.escape(template) + r"\|([^{}]+)\}\}")
        while True:
            updated = pattern.sub(r"\1", text)
            if updated == text:
                break
            text = updated
    text = re.sub(r"\[\[(?:File|文件|Image|圖像|图像):[^\]]+\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"</?(?:onlyinclude|poem|div|span|center|small|big|br)\b[^>]*>", "", text, flags=re.I)
    text = re.sub(r"<templatestyles\b[^>]*>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"'''?", "", text)
    text = remove_balanced(text, "{{", "}}")
    text = text.replace("{{", "").replace("}}", "")
    text = text.replace("\ufeff", "")
    return html.unescape(text)


def split_long_paragraph(text: str, target: int = 1200) -> list[str]:
    if len(text) <= target:
        return [text]
    pieces = re.split(r"([。！？；])", text)
    chunks: list[str] = []
    current = ""
    for index in range(0, len(pieces), 2):
        sentence = pieces[index]
        if index + 1 < len(pieces):
            sentence += pieces[index + 1]
        if current and len(current) + len(sentence) > target:
            chunks.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def extract_poem(raw: str) -> str:
    match = re.search(r"<poem>(.*?)</poem>", raw, flags=re.S | re.I)
    text = clean_common_wikitext(match.group(1) if match else raw)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line.replace("\u3000", " ")).strip()
        if line:
            lines.append(line)
    return "  \n".join(lines)


def clean_prose_body(raw: str) -> str:
    if "<onlyinclude>" in raw and "</onlyinclude>" in raw:
        raw = raw.split("<onlyinclude>", 1)[1].split("</onlyinclude>", 1)[0]
    text = clean_common_wikitext(raw)
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^#+", "", line).strip()
        line = re.sub(r"^:+", "", line).strip()
        line = re.sub(r"\s+", "", line)
        if not line:
            continue
        heading = re.fullmatch(r"={1,6}\s*(.+?)\s*={1,6}", line)
        if heading:
            lines.append(f"### {heading.group(1)}")
            continue
        lines.extend(split_long_paragraph(line))
    return "\n\n".join(lines).strip()


def write_simple_text(config: SimpleText) -> None:
    root = CONTENT_ROOT / config.target.split("/", 1)[0]
    write_page(root / "_index.md", config.root_title, config.root_summary, config.root_title, config.root_weight, config.root_summary)

    out_dir = CONTENT_ROOT / config.target
    if out_dir.exists():
        shutil.rmtree(out_dir)
    raw = fetch_wikisource_raw(config.wiki_title)
    body = extract_poem(raw) if config.mode == "poem" else clean_prose_body(raw)
    for marker in config.expected_markers:
        if marker not in body:
            raise RuntimeError(f"{config.title}: missing marker {marker}")
    write_page(
        out_dir / f"{config.slug}.md",
        config.title,
        config.work_summary,
        config.tag,
        1,
        body,
    )
    write_page(
        out_dir / "_index.md",
        config.title,
        config.work_summary,
        config.tag,
        config.work_weight,
        f"收录《{config.title}》。",
    )


def write_biji_index() -> None:
    write_page(
        CONTENT_ROOT / "biji" / "_index.md",
        "笔记",
        "笔记、清谈、杂录与轶事类经典。",
        "笔记",
        7,
        "收录笔记、清谈、杂录与轶事类经典。",
    )


def generate_shi_shuo() -> None:
    write_biji_index()
    out_dir = CONTENT_ROOT / "biji" / "shi-shuo-xin-yu"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    write_page(
        out_dir / "_index.md",
        "世说新语",
        "世说新语，南朝宋刘义庆撰，记魏晋人物言行轶事。",
        "世说新语",
        10,
        "收录《世说新语》序及三十六篇。",
    )
    for index, unit in enumerate(SHI_SHUO_UNITS, start=1):
        raw = fetch_wikisource_raw(unit.wiki_title)
        body = clean_prose_body(raw)
        if len(body) < 80:
            raise RuntimeError(f"世说新语-{unit.title}: body too short")
        write_page(
            out_dir / f"shi-shuo-xin-yu-{unit.slug}.md",
            f"世说新语-{unit.title}",
            f"世说新语：{unit.title}",
            "世说新语",
            index,
            body,
        )
        time.sleep(FETCH_DELAY)


def clean_shuowen_cell(cell: str) -> str:
    cell = cell.strip().lstrip("|").strip()
    if "|" in cell and re.search(r"\b(?:style|rowspan|colspan|class)\s*=", cell.split("|", 1)[0]):
        cell = cell.rsplit("|", 1)[-1]
    cell = re.sub(r"\s+", "", cell)
    return cell.strip()


def parse_shuowen_row(row: str) -> str | None:
    row = re.sub(r"\[\[(?:File|文件|Image|圖像|图像):[^\]]+\]\]", "", row, flags=re.I)
    row = clean_common_wikitext(row)
    cells: list[str] = []
    for line in row.splitlines():
        line = line.strip()
        if not line or line.startswith(("{|", "|}", "!", "class=")):
            continue
        if line.startswith("|"):
            for part in line.split("||"):
                cell = clean_shuowen_cell(part)
                if cell:
                    cells.append(cell)
    cells = [cell for cell in cells if cell and not re.fullmatch(r"[-|]+", cell)]
    if not cells:
        return None

    definition_index = None
    for index, cell in enumerate(cells):
        if "。" in cell or "也" in cell:
            definition_index = index
            break
    if definition_index is None or definition_index == 0:
        return None

    head = cells[0]
    definition = cells[definition_index]
    if len(head) > 8:
        return definition
    return f"{head}：{definition}"


def parse_shuowen_volume(raw: str, volume: int) -> str:
    if volume == 15:
        return clean_prose_body(raw)

    cleaned = re.sub(r"\{\{header2.*?\}\}", "", raw, flags=re.S)
    parts = re.split(r"^==\s*(.+?)\s*==\s*$", cleaned, flags=re.M)
    output: list[str] = []
    for index in range(1, len(parts), 2):
        section_title = parts[index].strip()
        section_body = parts[index + 1]
        output.append(f"### {section_title}")
        if "{|" in section_body:
            for row in section_body.split("|-"):
                parsed = parse_shuowen_row(row)
                if parsed:
                    output.append(parsed)
        else:
            section_text = clean_common_wikitext(section_body)
            section_text = re.sub(r"（\s*）", "", section_text)
            for line in section_text.splitlines():
                line = re.sub(r"\s+", "", line).strip()
                if line:
                    output.append(line)
        output.append("")
    return "\n\n".join(line for line in output if line.strip()).strip()


def write_xiaoxue_index() -> None:
    write_page(
        CONTENT_ROOT / "xiaoxue" / "_index.md",
        "小学",
        "文字、训诂、音韵等小学文献。",
        "小学",
        8,
        "收录文字、训诂、音韵等小学文献。",
    )


def generate_shuowen() -> None:
    write_xiaoxue_index()
    out_dir = CONTENT_ROOT / "xiaoxue" / "shuo-wen-jie-zi"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    write_page(
        out_dir / "_index.md",
        "说文解字",
        "说文解字十五卷，东汉许慎撰。",
        "说文解字",
        10,
        "收录《说文解字》十五卷。",
    )
    for volume in range(1, 16):
        title = f"說文解字/{volume:02d}"
        raw = fetch_wikisource_raw(title)
        body = parse_shuowen_volume(raw, volume)
        if len(body) < 200:
            raise RuntimeError(f"说文解字 卷{volume}: body too short")
        write_page(
            out_dir / f"shuo-wen-jie-zi-{volume:03d}.md",
            f"说文解字 卷第{chinese_number(volume)}",
            f"说文解字卷第{chinese_number(volume)}",
            "说文解字",
            volume,
            body,
        )
        time.sleep(FETCH_DELAY)


def write_buddha_shizhuan_index() -> None:
    write_page(
        CONTENT_ROOT / "buddha" / "shizhuan" / "_index.md",
        "史传部",
        "佛教史传、僧传与传灯文献。",
        "佛学",
        35,
        "收录佛教史传、僧传与传灯文献。",
    )


def fetch_gaoseng_blocks(juan: int) -> list[tuple[str, str | None, str]]:
    raw = fetch_text(CBETA_API.format(work="T2059", juan=juan))
    data = json.loads(raw)
    work_info = data.get("work_info") or {}
    if work_info.get("work") != "T2059":
        raise RuntimeError(f"高僧传 卷{juan}: unexpected work {work_info.get('work')}")
    if work_info.get("category") != "史傳部類":
        raise RuntimeError(f"高僧传 卷{juan}: unexpected category {work_info.get('category')}")
    if int(work_info.get("juan") or 0) != 14:
        raise RuntimeError(f"高僧传 卷{juan}: unexpected juan count {work_info.get('juan')}")
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"高僧传 卷{juan}: empty CBData result")
    parser = CbetaJuanParser()
    parser.feed(html.unescape(results[0]))
    blocks = []
    for block_type, level, text in parser.blocks:
        normalized = re.sub(r"\s+", "", text)
        if block_type == "paragraph" and re.fullmatch(r"高僧傳(?:序錄)?卷第[零一二三四五六七八九十]+", normalized):
            continue
        if block_type == "byline" and normalized in {"梁會稽嘉祥寺沙門釋慧皎撰", "梁慧皎撰"}:
            continue
        blocks.append((block_type, level, text))
    if not blocks:
        raise RuntimeError(f"高僧传 卷{juan}: no cleaned blocks")
    return blocks


def render_cbeta_markdown(blocks: list[tuple[str, str | None, str]]) -> str:
    lines: list[str] = []
    for block_type, level, text in blocks:
        if block_type == "head":
            try:
                heading_level = max(2, min(6, int(level or 2) + 1))
            except ValueError:
                heading_level = 3
            lines.append("#" * heading_level + " " + text)
        elif block_type == "verse":
            lines.append("  \n".join(text.splitlines()))
        else:
            lines.extend(split_long_paragraph(text))
        lines.append("")
    return "\n".join(lines).strip()


def generate_gaoseng(workers: int) -> None:
    write_buddha_shizhuan_index()
    out_dir = CONTENT_ROOT / "buddha" / "shizhuan" / "gao-seng-zhuan"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    write_page(
        out_dir / "_index.md",
        "高僧传",
        "高僧传十四卷，梁慧皎撰。",
        "高僧传",
        10,
        "收录《高僧传》十四卷。",
    )

    def write_juan(juan: int) -> Path:
        body = render_cbeta_markdown(fetch_gaoseng_blocks(juan))
        path = out_dir / f"gao-seng-zhuan-{juan:03d}.md"
        write_page(
            path,
            f"高僧传 卷第{chinese_number(juan)}",
            f"高僧传卷第{chinese_number(juan)}",
            "高僧传",
            juan,
            body,
        )
        return path

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(write_juan, juan): juan for juan in range(1, 15)}
        for completed, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            juan = future_map[future]
            path = future.result()
            print(f"[{completed:02d}/14] 高僧传 卷{juan:03d} -> {path}")


def parse_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    front: dict[str, str] = {}
    for line in text[4:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            front[key.strip()] = value.strip()
    return front, text[end + 5 :]


def markdown_files(path: Path) -> list[Path]:
    return sorted(file for file in path.rglob("*.md") if file.name != "_index.md")


def validate_page(path: Path, expected_tag: str) -> list[str]:
    problems: list[str] = []
    rel = path.relative_to(ROOT)
    front, body = parse_front_matter(path)
    if not front:
        return [f"{rel}: missing front matter"]
    if front.get("tags") != json.dumps([expected_tag], ensure_ascii=False):
        problems.append(f"{rel}: unexpected tags {front.get('tags')}")
    if front.get("draft") != "true":
        problems.append(f"{rel}: expected draft true")
    if "categories" in front:
        problems.append(f"{rel}: categories should not be present")
    if front.get("showToc") != "false":
        problems.append(f"{rel}: expected showToc false")
    if len(body.strip()) < 80:
        problems.append(f"{rel}: body too short")
    for pattern, label in FORBIDDEN_BODY_PATTERNS:
        if pattern.search(body):
            problems.append(f"{rel}: residual {label}")
            break
    for line_no, line in enumerate(body.splitlines(), start=1):
        if len(line) > 3000:
            problems.append(f"{rel}: line {line_no} too long ({len(line)} chars)")
            break
    return problems


def collection_specs() -> list[tuple[str, Path, int, str]]:
    return [
        ("百家姓", CONTENT_ROOT / "mengxue" / "baijia-xing", 1, "百家姓"),
        ("千字文", CONTENT_ROOT / "mengxue" / "qian-zi-wen", 1, "千字文"),
        ("世说新语", CONTENT_ROOT / "biji" / "shi-shuo-xin-yu", 37, "世说新语"),
        ("说文解字", CONTENT_ROOT / "xiaoxue" / "shuo-wen-jie-zi", 15, "说文解字"),
        ("高僧传", CONTENT_ROOT / "buddha" / "shizhuan" / "gao-seng-zhuan", 14, "高僧传"),
    ]


def check_all(source_check: bool, workers: int) -> int:
    problems: list[str] = []
    for title, path, expected_count, tag in collection_specs():
        if not (path / "_index.md").exists():
            problems.append(f"{title}: missing _index.md")
        files = markdown_files(path)
        if len(files) != expected_count:
            problems.append(f"{title}: expected {expected_count} files, got {len(files)}")
        for index, file in enumerate(files, start=1):
            problems.extend(validate_page(file, tag))
            front, _body = parse_front_matter(file)
            if front.get("weight") != str(index):
                problems.append(f"{file.relative_to(ROOT)}: expected weight {index}")

    shuowen_files = markdown_files(CONTENT_ROOT / "xiaoxue" / "shuo-wen-jie-zi")
    radical_count = sum(
        len(re.findall(r"^###\s+.+部$", file.read_text(encoding="utf-8"), flags=re.M))
        for file in shuowen_files[:14]
    )
    if radical_count != 540:
        problems.append(f"说文解字: expected 540 radicals in volumes 1-14, got {radical_count}")

    if source_check:
        # Regenerate into memory by comparing a fresh cleaned body for every content file.
        fresh_checks = {
            CONTENT_ROOT / BAIJIA_XING.target / f"{BAIJIA_XING.slug}.md": extract_poem(fetch_wikisource_raw(BAIJIA_XING.wiki_title)),
            CONTENT_ROOT / QIAN_ZI_WEN.target / f"{QIAN_ZI_WEN.slug}.md": extract_poem(fetch_wikisource_raw(QIAN_ZI_WEN.wiki_title)),
        }
        for unit in SHI_SHUO_UNITS:
            fresh_checks[
                CONTENT_ROOT / "biji" / "shi-shuo-xin-yu" / f"shi-shuo-xin-yu-{unit.slug}.md"
            ] = clean_prose_body(fetch_wikisource_raw(unit.wiki_title))
            time.sleep(FETCH_DELAY)
        for volume in range(1, 16):
            fresh_checks[
                CONTENT_ROOT / "xiaoxue" / "shuo-wen-jie-zi" / f"shuo-wen-jie-zi-{volume:03d}.md"
            ] = parse_shuowen_volume(fetch_wikisource_raw(f"說文解字/{volume:02d}"), volume)
            time.sleep(FETCH_DELAY)

        def fresh_gaoseng(juan: int) -> tuple[Path, str]:
            return (
                CONTENT_ROOT / "buddha" / "shizhuan" / "gao-seng-zhuan" / f"gao-seng-zhuan-{juan:03d}.md",
                render_cbeta_markdown(fetch_gaoseng_blocks(juan)),
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for path, body in executor.map(fresh_gaoseng, range(1, 15)):
                fresh_checks[path] = body

        for path, fresh_body in fresh_checks.items():
            _front, body = parse_front_matter(path)
            if body.strip() != fresh_body.strip():
                problems.append(f"{path.relative_to(ROOT)}: differs from cleaned source")

    if problems:
        print("CHECK FAILED")
        for problem in problems[:120]:
            print(f"  - {problem}")
        if len(problems) > 120:
            print(f"  ... and {len(problems) - 120} more")
        return 1
    print("CHECK OK: high-frequency classics batch")
    return 0


def generate_all(workers: int) -> None:
    write_simple_text(BAIJIA_XING)
    write_simple_text(QIAN_ZI_WEN)
    generate_shi_shuo()
    generate_shuowen()
    generate_gaoseng(workers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--source-check", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    if args.check or args.source_check:
        return check_all(source_check=args.source_check, workers=args.workers)
    generate_all(workers=args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
