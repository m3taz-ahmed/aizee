# aiZee vendoring note — oneirloom-craft-construction

Media-light vendoring: this skill's raster/print media is excluded from git
(`.gitignore` media-light block) and ships as a release asset instead.

## What was excluded (7.2 MiB, 4 files)

the few-shot reference/result images the recipes inspect — all remain fully functional on the
maintainer's source tree.

## Restoring full functionality

```bash
aizee skill media-fetch oneirloom-craft-construction
```

Downloads `aizee-media-oneirloom-craft-construction.tar.gz` from the matching GitHub release,
verifies sha256 against the committed `skills/media-packs.json` manifest, and
extracts in place. `aizee deps check` reports this pack as `skill-media-oneirloom-craft-construction`.

## Manual fallback

If no release asset is reachable, the media can be re-fetched from upstream:
`https://github.com/PigeonAI-Yang/oneirloom` (see `LICENSE.upstream` / vendoring license in this directory).

## Effect while media is missing

The skill's text, code, templates and fonts are all present — but any step that
reads the missing images/prints degrades. Disclose the missing media honestly
(best-effort, never an equivalence claim), or fetch the pack first.
