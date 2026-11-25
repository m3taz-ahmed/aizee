# 📚 KindlePub

**An end-to-end Amazon KDP self-publishing pipeline, packaged as a portable [Agent Skill](https://agentskills.io).**

Take a finished manuscript all the way onto Amazon — an `epubcheck`-clean Kindle EPUB, a cover
whose art you generate with **Gemini Nano Banana** and assemble in **KDP Cover Creator** (which
auto-sizes the spine — no custom PDFs), drafted KDP metadata, and a field-by-field walk through
KDP's Details → Content → Pricing → Publish flow for the ebook, paperback, and hardcover.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Agent Skill](https://img.shields.io/badge/Agent_Skills-SKILL.md-7c3aed)
![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

---

## Why

Shipping a book to KDP is a maze of format gotchas: an EPUB that silently fails `epubcheck`, a
cover rejected because the spine is off, garbled AI text smeared across the art. KindlePub encodes
the hard-won fixes so your agent gets it right the first time — and because it's a standard
`SKILL.md`, it **travels with you** across Claude Code, Codex, Cursor, Gemini CLI, and the Claude
app instead of being trapped in one tool.

Build everything to the edge; the human enters credentials, operates native file pickers, and
presses Publish. The skill never types your passwords.

## What it does

| Phase | Output |
|------:|--------|
| 1 | Lock the manuscript, export a clean DOCX (no copy/paste loss) |
| 2 | Reflowable Kindle **EPUB**, `epubcheck`-clean (encodes 3 ebooklib traps that waste hours) |
| 3 | **Cover** — generate art with Gemini **Nano Banana**, assemble in **KDP Cover Creator** (it adds the title and auto-sizes the spine; reuse the front for the ebook) |
| 4 | **Print** — upload the manuscript DOCX; KDP paginates it and Cover Creator sizes the spine (no custom PDF) |
| 5 | Drafted KDP **metadata** (description, BISAC categories, keywords, AI-content answers, pricing) |
| 6 | Field-by-field **KDP walkthrough** (DRM, KDP Select, pre-order, the hardcover print-cost trap) |
| 7 | A saved **publication record** so the next format and next book go faster |

## Install

**Any coding agent (via the [openskills](https://github.com/numman-ali/openskills) loader):**
```bash
git clone https://github.com/jessl2juice/kindlepub
npx openskills install ./kindlepub      # installs into Claude Code, Codex, Cursor, Gemini CLI…
```

**Claude app / Cowork:** download `kindlepub.skill` from
[Releases](https://github.com/jessl2juice/kindlepub/releases) and click **Save skill**.

**Manual (any SKILL.md-aware tool):** copy this folder to `.claude/skills/kindlepub/`.

## Requirements

Python 3, plus pip deps for the EPUB build:
```bash
pip install mammoth ebooklib beautifulsoup4 lxml epubcheck
```
`epubcheck` also needs **Java** on your PATH. (The cover and spine are done in KDP Cover Creator —
no extra image/PDF libraries needed.)

## Usage

Just talk to your agent — *"I finished my manuscript, help me put it on Amazon"* — and the skill
drives the pipeline, handing you each irreversible click. The two scripts build and validate the
Kindle EPUB; the cover is generated in Nano Banana and assembled in KDP Cover Creator (in the
browser).

```bash
python3 scripts/build_epub.py            # -> book.epub  (edit the CONFIG block first)
python3 scripts/validate_epub.py book.epub
# Cover: generate art with Nano Banana (see references/), then build it in KDP Cover Creator.
```

## What's inside

```
kindlepub/
├── SKILL.md                              # the skill: when to trigger + the 7-phase procedure
├── scripts/
│   ├── build_epub.py                     # DOCX -> epubcheck-clean reflowable EPUB
│   └── validate_epub.py                  # epubcheck wrapper (the same check KDP runs)
└── references/
    ├── kdp-walkthrough.md                # field-by-field KDP script + Cover Creator steps
    ├── metadata-template.md              # the metadata you fill in
    └── nanobanana-cover-prompts.md       # cover-art prompt recipes + the no-text rule
```

## Why it's better than winging it

- **The EPUB actually validates.** The build script encodes three `ebooklib` traps (the
  encoding-declaration empty-body bug, `add_link` CSS attachment, and the `set_cover` / OPF-096
  page-list crash) that silently produce broken-but-"valid"-looking books.
- **The cover looks human.** AI models always sneak garbled text onto pennants, clothing, spines,
  and screens — so the Nano Banana prompts forbid text on those surfaces and KDP Cover Creator
  lays the real title in afterward.
- **The spine fits with zero math.** KDP paginates your manuscript and Cover Creator auto-sizes the
  spine to that page count — no guessed spine, no custom cover PDF, no rejected upload.

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The bar: keep it generic and secret-free,
keep the `SKILL.md` frontmatter valid, and preserve the hard-won notes (they exist because
something broke once).

## License

[MIT](LICENSE) — use it, fork it, ship your book.

## Acknowledgements

Built on the open **[Agent Skills](https://agentskills.io)** standard (`SKILL.md`), originated by
Anthropic and now read by ~40 agent tools. Part of the **Open Skills** idea: the way you work
should be yours and portable, not rented back to you by whichever AI app you happened to use.
