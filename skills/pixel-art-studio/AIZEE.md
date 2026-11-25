# aiZee vendoring note — pixel-art-studio

Media-light vendoring: this skill's raster/print media is excluded from git
(`.gitignore` media-light block) and ships as a release asset instead.

## What was excluded (1.1 MiB, 79 files)

the animated example sprites/sheets referenced by the docs — all remain fully functional on the
maintainer's source tree.

## Restoring full functionality

```bash
aizee skill media-fetch pixel-art-studio
```

Downloads `aizee-media-pixel-art-studio.tar.gz` from the matching GitHub release,
verifies sha256 against the committed `skills/media-packs.json` manifest, and
extracts in place. `aizee deps check` reports this pack as `skill-media-pixel-art-studio`.

## Manual fallback

If no release asset is reachable, the media can be re-fetched from upstream:
`https://github.com/Gamezxz/pixel-art-studio` (see `LICENSE.upstream` / vendoring license in this directory).

## Effect while media is missing

The skill's text, code, templates and fonts are all present — but any step that
reads the missing images/prints degrades. Disclose the missing media honestly
(best-effort, never an equivalence claim), or fetch the pack first.
