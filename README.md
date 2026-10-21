# ifcalm-books

中国古典文献数字化收录项目，使用 Hugo 构建，按经部、佛学、道家、子部整理书籍及篇卷。

<!-- catalog-summary:start -->
当前共收录 **30 个书目条目**、**388 个 Markdown 正文单元**。同一书的卷、篇或章节文件在下方合并为一个书目条目；异译本和不同版本分别列出。
<!-- catalog-summary:end -->

<!-- catalog:start -->
> 下方分类树由 [`scripts/update_readme_catalog.py`](scripts/update_readme_catalog.py) 根据 `content/posts` 更新。新增或调整收录后运行 `python3 scripts/update_readme_catalog.py`；GitHub Actions 会检查该区块是否与当前收录保持同步。

## 收录目录

### [经部](content/posts/confucius/)

- [易经](content/posts/confucius/yi-jing/)（69 个内容单元）
- [尚书](content/posts/confucius/shang-shu/)（58 个内容单元）
- [大学](content/posts/confucius/da-xue.md)（1 个内容单元）
- [论语](content/posts/confucius/lun-yu.md)（1 个内容单元）
- [中庸](content/posts/confucius/zhong-yong.md)（1 个内容单元）
- [孟子](content/posts/confucius/mengzi/)（7 个内容单元）

### [佛学](content/posts/buddha/)

- [佛说无量寿经](content/posts/buddha/fo-shuo-wu-liang-shou-jing/)（2 个内容单元）
- [十善业道经](content/posts/buddha/shi-shan.md)（1 个内容单元）
- [圆觉经](content/posts/buddha/da-fang-guang-yuan-jue-xiu-duo-luo-liao-yi-jing.md)（1 个内容单元）
- [大乘起信论](content/posts/buddha/da-cheng-qi-xin-lun.md)（1 个内容单元）
- [妙法莲华经](content/posts/buddha/miao-fa-lian-hua-jing/)（7 个内容单元）
- [楞严经](content/posts/buddha/lengyan/)（10 个内容单元）
- [四十二章经](content/posts/buddha/si-shi-er.md)（1 个内容单元）
- [金刚经](content/posts/buddha/jing-gang-jing.md)（1 个内容单元）
- [地藏菩萨本愿经](content/posts/buddha/di-zang-pu-sa-ben-yuan-jing/)（2 个内容单元）
- [心经](content/posts/buddha/xing-jing.md)（1 个内容单元）
- [过去现在因果经](content/posts/buddha/guo-qu-xian-zai-yin-guo-jing/)（4 个内容单元）
- [大悲经](content/posts/buddha/da-bei-jing/)（5 个内容单元）
- [百喻经](content/posts/buddha/bai-yu-jing/)（4 个内容单元）
- [法句经](content/posts/buddha/fa-ju-jing/)（2 个内容单元）

### [道家](content/posts/taoism/)

- [庄子](content/posts/taoism/zhuangzi/)（33 个内容单元）
- [列子](content/posts/taoism/liezi/)（8 个内容单元）
- [太上感应篇](content/posts/taoism/tai-shang.md)（1 个内容单元）
- [德道经 (帛书版)](content/posts/taoism/dedaojing-boshuban.md)（1 个内容单元）
- [道德经](content/posts/taoism/dao-de-jing.md)（1 个内容单元）

### [子部](content/posts/masters/)

- [墨子](content/posts/masters/mozi/)（53 个内容单元）
- [韩非子](content/posts/masters/hanfeizi/)（55 个内容单元）
- [吕氏春秋](content/posts/masters/lvshi-chunqiu/)（26 个内容单元）
- [淮南子](content/posts/masters/huainanzi/)（21 个内容单元）
- [盐铁论](content/posts/masters/yantielun/)（10 个内容单元）

<!-- catalog:end -->

## 目录约定

所有书籍统一采用“大类 → 书籍 → 篇卷”的结构，佛学不再设置部类、经藏、论藏或经典系子目录。

```text
content/posts/
├── confucius/              # 经部
│   ├── da-xue.md           # 单篇书籍
│   └── yi-jing/            # 多篇书籍
│       ├── _index.md       # 书目页
│       └── qian.md         # 各篇正文
├── buddha/                 # 佛学，直接放置书籍
├── taoism/                 # 道家，直接放置书籍
└── masters/                # 子部
```

- 单篇、单卷书籍使用独立 Markdown 文件；多篇、多卷书籍建立目录，正文直接放在书籍目录内。
- 使用 `weight` 控制书籍、篇卷的排列顺序，不再建立上经、下经或卷号范围子目录。
- 大类和多篇、多卷书籍保留 `_index.md`，用于定义中文标题、排序和简介；归档、标签等功能页也保留各自的目录页。
- 目录页保留必要元数据，简介使用 `summary`，正文只补充不重复的说明，不重复设置文章页的展示配置。
- 不使用 `aliases` 或 `canon_section` 字段。
- 收录统计包含草稿，正文单元不包含 `_index.md`；正文是否发布由各文件的 `draft` 控制。已有公开正文的大类、书籍目录页须设为 `draft: false`，确保可从博文页逐层访问；全部正文仍为草稿的书籍可保持目录页为草稿。

## 本地预览与维护

在项目根目录运行以下命令，需要本地安装 Hugo 和 Python 3。

```bash
# 启动本地预览
hugo server

# 包含草稿的本地预览
hugo server --buildDrafts

# 新增、移动或删除书籍后，同步收录清单
python3 scripts/update_readme_catalog.py

# 检查 README 收录清单是否与实际文件一致
python3 scripts/update_readme_catalog.py --check

# 构建站点
hugo
```

`content/` 存放内容，`scripts/` 存放采集、生成与校验工具，`static/` 和 `assets/` 存放静态资源及样式，`themes/paperMod/` 存放主题。构建生成的 `public/` 和 `resources/` 不纳入版本管理。
