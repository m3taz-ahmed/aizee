# aiZee vendoring note — novelist-longform

Media-light vendoring: this skill's raster/print media is excluded from git
(`.gitignore` media-light block) and ships as a release asset instead.

## What was excluded (1.1 MiB, 9 files)

workbench/phase screenshots referenced by the docs (cosmetic — the workflow itself is text/code) — all remain fully functional on the
maintainer's source tree.

## Restoring full functionality

```bash
aizee skill media-fetch novelist-longform
```

Downloads `aizee-media-novelist-longform.tar.gz` from the matching GitHub release,
verifies sha256 against the committed `skills/media-packs.json` manifest, and
extracts in place. `aizee deps check` reports this pack as `skill-media-novelist-longform`.

## Manual fallback

If no release asset is reachable, the media can be re-fetched from upstream:
`https://github.com/PenglongHuang/chinese-novelist-skill` (see `LICENSE.upstream` / vendoring license in this directory).

## Effect while media is missing

The skill's text, code, templates and fonts are all present — but any step that
reads the missing images/prints degrades. Disclose the missing media honestly
(best-effort, never an equivalence claim), or fetch the pack first.
