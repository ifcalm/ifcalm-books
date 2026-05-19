# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Build the Hugo site (output to public/)
hugo

# Serve locally with live reload
hugo server -D

# Build with drafts included
hugo -D

# Run all content generation scripts (orchestrated via catalog)
python3 scripts/generate_canon_texts.py --all-collected

# Generate a single collection by id
python3 scripts/generate_canon_texts.py --collection <id>

# List all collections in the catalog
python3 scripts/generate_canon_texts.py --list --include-planned

# Dry-run (print which generators would run)
python3 scripts/generate_canon_texts.py --dry-run --all-collected

# Validate generated content against catalog expectations
python3 scripts/validate_canon_collections.py

# Validate a single collection
python3 scripts/validate_canon_collections.py --collection <id>

# Validate with JSON output
python3 scripts/validate_canon_collections.py --json

# 二十四史 generation
python3 scripts/generate_history.py --history shi-ji     # Single history
python3 scripts/generate_history.py --all                 # All 24 histories
python3 scripts/generate_history.py --list                # List available histories
python3 scripts/generate_history.py --discover han-shu    # Discover volume pages via API
```

## Architecture

This is a **Hugo static site** (PaperMod theme) hosting classical Chinese philosophical/religious texts — "诸子百家" — deployed at `https://books.ifcalm.org/`. Language is `zh-cn`.

### Content structure

Four top-level categories under `content/posts/`:
- `butterfly/` — Zhuangzi chapters (庄子, 33 chapters as individual pages)
- `taoism/` — Daoist canon organized by sub-category: `classics/`, `alchemy/`, `cultivation/`, `ethics/`, `ritual/`, `shangqing/`, `immortals/`
- `buddha/` — Buddhist canon organized by tripitaka: `jingzang/` (经藏/sutras), `luzang/` (律藏/vinaya), `lunzang/` (论藏/abhidharma). Jingzang subdivided into `ahan/`, `bore/`, `fahua/`, `huayan/`, `niepan/`, `baoji/`, `daji/`, `jingji/`
- `confucius/` — Confucian texts (经部 classics)
- `history/` — 二十四史 (史部), 24 official dynastic histories, ~3200 volumes. Each history in its own subdirectory with 30-volume grouping.

Each directory has an `_index.md` with frontmatter (title, weight for ordering, summary). Individual texts are markdown files with `###`-level section headings (Hugo renders h3 as the primary section delimiter given the page title is h1 and category heading is h2).

### Content generation pipeline

`scripts/data/taozang_catalog.json` is the **authoritative manifest** — it defines every collection with an id, status (`collected`/`planned`), generator script path, target content path, and expected metrics (`content_files`, `section_headings`, `missing_chars` count).

**Orchestrator**: `scripts/generate_canon_texts.py` reads the catalog, selects collections by status/id, and runs the corresponding generator scripts. Use `--all-collected` to run all completed collections.

**Validator**: `scripts/validate_canon_collections.py` checks that generated content matches catalog expectations — file counts, heading counts, missing-character counts, private-use unicode characters, and forbidden source artifacts (wiki markup, `<onlyinclude>` tags, etc.).

**Generators** come in two families:
- **Wikisource-based** (Daoist texts): Fetch raw/rendered wikitext from `zh.wikisource.org`, strip templates and wiki markup, convert `== headings ==` to `###` markdown.
- **CBETA API-based** (Buddhist texts): Fetch from `cbdata.dila.edu.tw/stable/juans`, parse HTML into structured markdown with `###` juan (卷) headings. The CBETA parsers share a common base class in `generate_bore_from_cbdata.py` (`CbetaJuanParser`, `fetch_text`, `chinese_number` utilities).

### Hugo theme notes

PaperMod theme lives in `themes/paperMod/`. `hugo.toml` configures profile mode for the home page, simple nav menu, Chinese date format, and `ShowToc: true` by default. Custom layouts/partials can be placed in `layouts/` to override theme defaults.
