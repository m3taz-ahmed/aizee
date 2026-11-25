# kindle-book

A Claude skill that converts Markdown manuscripts into Amazon KDP-ready files: **EPUB3** for Kindle and **print-ready PDF** for paperback.

One command. Markdown in, two publishable files out.

## What it does

Drop a `.md` or `.txt` file into Claude (desktop app, Cowork mode) and say **"make it a Kindle book."** The skill:

1. Parses your manuscript (headings → chapters, frontmatter → metadata)
2. Builds a valid **EPUB3** via pandoc (table of contents, proper structure, clean CSS)
3. Builds a **print-ready PDF** via pandoc + XeLaTeX with correct KDP margins for your trim size
4. Outputs both files ready to upload to Amazon KDP

## Supported trim sizes

| Size | Use case |
|------|----------|
| 5×8" | Novellas, poetry, short books |
| 5.5×8.5" | Novels, memoirs |
| 6×9" | Nonfiction, guides (most popular) |
| 8.5×11" | Workbooks, textbooks |

Margins auto-calculate based on trim size and page count per KDP specs.

## Installation

1. Download `kindle-book.skill` from [Releases](https://github.com/nikmcfly/kindle-book-skill/releases)
2. Open Claude desktop app
3. Drag the `.skill` file into Claude, or place it in your skills directory

Or clone and use directly:

```bash
git clone https://github.com/nikmcfly/kindle-book-skill.git
```

## Prerequisites

The skill runs inside Claude's environment, which has these pre-installed:

- `pandoc` (Markdown → EPUB/PDF conversion)
- `xelatex` (PDF typesetting)
- `python3` (build script)

If running the build script standalone outside Claude, install these first.

## Usage

### Inside Claude (recommended)

Just tell Claude:
- "Make this a Kindle book"
- "Convert my manuscript to KDP format"
- "I want to publish this on Amazon"

Claude reads the skill instructions and handles everything.

### Standalone

```bash
python3 scripts/build_kindle.py \
  --input manuscript.md \
  --output ./output/ \
  --title "My Book" \
  --author "Author Name" \
  --trim 6x9
```

Optional flags:

```
--cover cover.jpg      # EPUB cover image
--publisher "Name"     # Publisher metadata
--trim 5x8             # Trim size (default: 6x9)
--font-size 12         # Body font size in pt
--epub-only            # Skip PDF generation
--pdf-only             # Skip EPUB generation
```

## Manuscript format

Write in Markdown. Each `#` heading becomes a chapter. Optionally add YAML frontmatter:

```yaml
---
title: "My Book Title"
author: "Author Name"
language: en-US
publisher: "Publisher Name"
rights: "© 2026 Author Name. All rights reserved."
description: "One-line book description."
trim_size: "6x9"
cover_image: "cover.jpg"
---
```

## File structure

```
kindle-book-skill/
├── SKILL.md                    # Claude skill definition
├── scripts/
│   └── build_kindle.py         # Main build script
├── assets/
│   ├── epub-styles.css         # EPUB typography
│   └── print-template.tex      # LaTeX template for print PDF
└── references/
    └── trim-sizes.md           # KDP margin specs
```

## Output

The script produces:

- `<title>_digital.epub` — upload to KDP → Kindle eBooks → Manuscript
- `<title>_print.pdf` — upload to KDP → Paperback → Manuscript interior

KDP requires a **separate cover file** for paperback. Use [KDP Cover Calculator](https://kdp.amazon.com/en_US/cover-calculator) for exact dimensions.

## License

MIT

## Complete KDP workflow

This skill generates the **book interior** (EPUB + PDF). For the **paperback cover**, use the companion skill:

👉 **[kindle-cover-skill](https://github.com/nikmcfly/kindle-cover-skill)** — generates a full-wrap cover PDF (front + spine + back) sized to your page count.
```
manuscript.md ──▶ kindle-book-skill  ──▶ book.epub + book.pdf
cover.jpg     ──▶ kindle-cover-skill ──▶ fullwrap_cover.pdf
```

Install both:
```bash
claude install nikmcfly/kindle-book-skill
claude install nikmcfly/kindle-cover-skill
```
