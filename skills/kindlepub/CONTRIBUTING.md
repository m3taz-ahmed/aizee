# Contributing to KindlePub

Thanks for helping make self-publishing less painful. PRs welcome.

The bar:
- **Generic + secret-free.** No personal book/author names, no API keys, no machine paths.
  The scripts' CONFIG blocks ship placeholder defaults.
- **Valid skill.** Keep `SKILL.md` frontmatter valid (a `name` matching the folder and a
  trigger-rich `description`); the skill must stay loadable by any SKILL.md-aware agent.
- **Preserve the hard-won notes.** The ebooklib traps, the cover no-text rule, and the
  exact-page-count requirement exist because something broke once. Don't drop them; improve them.
- **Test what you touch.** If you change `build_epub.py`, re-run `validate_epub.py` on a sample
  and confirm a clean `epubcheck` pass before opening the PR.

Open an issue first for anything large (a new format, a different cover compositor, etc.).
