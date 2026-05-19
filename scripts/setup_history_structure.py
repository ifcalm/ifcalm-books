#!/usr/bin/env python3
"""Create the 二十四史 directory skeleton under content/posts/history/."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "content" / "posts" / "history"

HISTORIES: list[dict] = [
    {"slug": "shi-ji", "title": "史记", "volumes": 130, "author": "司马迁", "dynasty": "西汉",
     "summary": "史记一百三十卷，汉司马迁撰。本纪十二、表十、书八、世家三十、列传七十。"},
    {"slug": "han-shu", "title": "汉书", "volumes": 100, "author": "班固", "dynasty": "东汉",
     "summary": "汉书一百卷，汉班固撰。纪十二、表八、志十、列传七十。"},
    {"slug": "hou-han-shu", "title": "后汉书", "volumes": 120, "author": "范晔", "dynasty": "南朝宋",
     "summary": "后汉书一百二十卷，南朝宋范晔撰。纪十、列传八十、志三十。"},
    {"slug": "san-guo-zhi", "title": "三国志", "volumes": 65, "author": "陈寿", "dynasty": "西晋",
     "summary": "三国志六十五卷，晋陈寿撰。魏书三十、蜀书十五、吴书二十。"},
    {"slug": "jin-shu", "title": "晋书", "volumes": 130, "author": "房玄龄等", "dynasty": "唐",
     "summary": "晋书一百三十卷，唐房玄龄等奉敕撰。帝纪十、志二十、列传七十、载记三十。"},
    {"slug": "song-shu", "title": "宋书", "volumes": 100, "author": "沈约", "dynasty": "南朝梁",
     "summary": "宋书一百卷，南朝梁沈约撰。本纪十、志三十、列传六十。"},
    {"slug": "nan-qi-shu", "title": "南齐书", "volumes": 59, "author": "萧子显", "dynasty": "南朝梁",
     "summary": "南齐书五十九卷，南朝梁萧子显撰。本纪八、志十一、列传四十。"},
    {"slug": "liang-shu", "title": "梁书", "volumes": 56, "author": "姚思廉", "dynasty": "唐",
     "summary": "梁书五十六卷，唐姚思廉撰。本纪六、列传五十。"},
    {"slug": "chen-shu", "title": "陈书", "volumes": 36, "author": "姚思廉", "dynasty": "唐",
     "summary": "陈书三十六卷，唐姚思廉撰。本纪六、列传三十。"},
    {"slug": "wei-shu", "title": "魏书", "volumes": 114, "author": "魏收", "dynasty": "北齐",
     "summary": "魏书一百一十四卷，北齐魏收撰。帝纪十二、列传九十二、志十。"},
    {"slug": "bei-qi-shu", "title": "北齐书", "volumes": 50, "author": "李百药", "dynasty": "唐",
     "summary": "北齐书五十卷，唐李百药撰。本纪八、列传四十二。"},
    {"slug": "zhou-shu", "title": "周书", "volumes": 50, "author": "令狐德棻等", "dynasty": "唐",
     "summary": "周书五十卷，唐令狐德棻等撰。本纪八、列传四十二。"},
    {"slug": "sui-shu", "title": "隋书", "volumes": 85, "author": "魏徵等", "dynasty": "唐",
     "summary": "隋书八十五卷，唐魏徵等撰。帝纪五、志三十、列传五十。"},
    {"slug": "nan-shi", "title": "南史", "volumes": 80, "author": "李延寿", "dynasty": "唐",
     "summary": "南史八十卷，唐李延寿撰。本纪十、列传七十。"},
    {"slug": "bei-shi", "title": "北史", "volumes": 100, "author": "李延寿", "dynasty": "唐",
     "summary": "北史一百卷，唐李延寿撰。本纪十二、列传八十八。"},
    {"slug": "jiu-tang-shu", "title": "旧唐书", "volumes": 200, "author": "刘昫等", "dynasty": "后晋",
     "summary": "旧唐书二百卷，后晋刘昫等撰。本纪二十、志三十、列传一百五十。"},
    {"slug": "xin-tang-shu", "title": "新唐书", "volumes": 225, "author": "欧阳修、宋祁", "dynasty": "北宋",
     "summary": "新唐书二百二十五卷，宋欧阳修、宋祁等撰。本纪十、志五十、表十五、列传一百五十。"},
    {"slug": "jiu-wu-dai-shi", "title": "旧五代史", "volumes": 150, "author": "薛居正等", "dynasty": "北宋",
     "summary": "旧五代史一百五十卷，宋薛居正等撰。梁书二十四、唐书五十、晋书二十四、汉书十一、周书二十二、列传七。"},
    {"slug": "xin-wu-dai-shi", "title": "新五代史", "volumes": 74, "author": "欧阳修", "dynasty": "北宋",
     "summary": "新五代史七十四卷，宋欧阳修撰。本纪十二、列传四十五、考三、世家十、附录三。"},
    {"slug": "song-shi", "title": "宋史", "volumes": 496, "author": "脱脱等", "dynasty": "元",
     "summary": "宋史四百九十六卷，元脱脱等撰。本纪四十七、志一百六十二、表三十二、列传二百五十五。"},
    {"slug": "liao-shi", "title": "辽史", "volumes": 116, "author": "脱脱等", "dynasty": "元",
     "summary": "辽史一百一十六卷，元脱脱等撰。本纪三十、志三十二、表八、列传四十五、国语解一。"},
    {"slug": "jin-shi", "title": "金史", "volumes": 135, "author": "脱脱等", "dynasty": "元",
     "summary": "金史一百三十五卷，元脱脱等撰。本纪十九、志三十九、表四、列传七十三。"},
    {"slug": "yuan-shi", "title": "元史", "volumes": 210, "author": "宋濂等", "dynasty": "明",
     "summary": "元史二百一十卷，明宋濂等撰。本纪四十七、志五十八、表八、列传九十七。"},
    {"slug": "ming-shi", "title": "明史", "volumes": 332, "author": "张廷玉等", "dynasty": "清",
     "summary": "明史三百三十二卷，清张廷玉等撰。本纪二十四、志七十五、表十三、列传二百二十。"},
]


def volume_groups(total: int, chunk: int = 30) -> list[tuple[int, int]]:
    groups: list[tuple[int, int]] = []
    for start in range(1, total + 1, chunk):
        end = min(start + chunk - 1, total)
        groups.append((start, end))
    return groups


def write_frontmatter(path: Path, title: str, summary: str, weight: int,
                      tags: list[str] | None = None,
                      categories: list[str] | None = None) -> None:
    tags = tags or []
    categories = categories or ["史部"]
    lines = [
        "---",
        f'title: "{title}"',
        "date: 2026-05-19",
        f"weight: {weight}",
        f"tags: {tags}",
        f"categories: {categories}",
        "draft: false",
        f'summary: "{summary}"',
        "showToc: false",
        "tocOpen: false",
        "ShowShareButtons: false",
        "---",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)

    # Top-level _index.md
    write_frontmatter(
        BASE / "_index.md",
        title="二十四史",
        summary="二十四史，中国古代各朝撰写的二十四部史书的总称。",
        weight=5,
        tags=["二十四史", "史部"],
        categories=["史部"],
    )

    for i, h in enumerate(HISTORIES):
        slug = h["slug"]
        hist_dir = BASE / slug
        hist_dir.mkdir(parents=True, exist_ok=True)

        # History-level _index.md
        write_frontmatter(
            hist_dir / "_index.md",
            title=h["title"],
            summary=h["summary"],
            weight=10 * (i + 1),
            tags=[h["title"], h["dynasty"]],
        )

        groups = volume_groups(h["volumes"])
        for gidx, (start, end) in enumerate(groups):
            group_name = f"{start:03d}-{end:03d}"
            group_dir = hist_dir / group_name
            group_dir.mkdir(parents=True, exist_ok=True)

            write_frontmatter(
                group_dir / "_index.md",
                title=f"{h['title']} 卷{start}–{end}",
                summary=f"{h['title']}卷{start}至卷{end}。",
                weight=gidx + 1,
                tags=[h["title"]],
            )

    print(f"Created structure under {BASE.relative_to(ROOT)}")
    print(f"  {len(HISTORIES)} histories")
    total_groups = sum(len(volume_groups(h["volumes"])) for h in HISTORIES)
    print(f"  {total_groups} volume-group subdirectories")


if __name__ == "__main__":
    main()
