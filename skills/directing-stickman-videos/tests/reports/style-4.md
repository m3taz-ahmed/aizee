# Style 4 — Cozy Storytelling / 治愈故事风

Date: 2026-10-14. This is a targeted extension of the existing director skill, not a new package or architecture redesign. Separate prior-art discovery is not applicable: the design comes from the owner's supplied visual references, Flow trials and explicit feedback. No upstream author branding, skill renaming or install-layout migration is introduced.

## User-approved direction

- Full-color cartoon story environments with an expressive minimalist white-filled character; the owner rejected “hand-drawn” naming and chose 治愈故事风.
- Each new ten-second segment normally enters a different story location. The accepted revised story used office → metro platform → outdoor cafe, with internal wide views, close-ups and lateral movement.
- Character, important prop, direction and narrator provide continuity; different tables/backgrounds after planned scene changes are not errors. Single-location requests and approved callbacks remain supported.

## Observed samples and evidence scope

Omni 1.1 Flash, 16:9, 720p, independent approximately ten-second clips. Browser action-keyframe checks showed the new locations, office departure/foreground doorway, station walk/train/columns, cafe phone placement, sip, drawing insert and foliage pullback. The owner accepted the visual direction and selected two sample files for publication.

This is sample-specific user visual acceptance, not blind review or frame-by-frame certification. Requested wipes did not always land on the last frame; actual assembly needs an appropriate cut point or the planned time jump. Pen handoff/ending state had unresolved details in the cafe trial. No separate listening-based Style 4 voice/BGM match has been certified. The revised cartoon-only runtime wording is a design adaptation of those samples, not a claim that every future prompt or topic has been provider-tested.

## Published examples

Both are owner-supplied ten-second samples, 1280×720 at 24 FPS with an audio track. They are not labeled as complete thirty-second films. GIF previews keep the full sample duration and loop inline; original MP4s are retained without requiring users to open them from the README.

| Example | Source selection | Repository MP4 | SHA-256 |
|---|---|---|---|
| Metro commute | 4-2.mp4 | assets/readme/style-4-cozy-station.mp4 | 19154a055298116262bf31cf15586ba1a62e1d293dc02749030007e9b53e3329 |
| Outdoor coffee break | 4-1.mp4 | assets/readme/style-4-cozy-cafe.mp4 | 94df6c6085dc7f99de5d4b4668cff261e70b070a10f3624b5c5d484012d765fb |

The content mapping was checked from actual video frames, not file-manager thumbnail caches. Only the default Chinese homepage and Chinese README are updated; other language pages wait for the owner's explicit multilingual-sync request.

## Regression checks

`tests/verify-cozy-storytelling.py` tests semantic plan fixtures: different-location success, explicit single-location exception, prop uniqueness, screen-down face, irreversible departure, two-arm/two-leg count, voice profile identity, static-design versus initial-state scope, and scene-local effects. Eight bad mutations must be rejected. These fixtures test the contract, not model behavior. Routing and media-file checks supplement existing README, classic-character and shared-voice regressions.

## Publication boundaries

All GitHub mutations target kaomei/stickman-video-director, with kaomei author/committer identity and no co-author trailers. Publish through a feature branch and PR, not a direct main push. No automatic Flow spending, video downloading or local installed-skill replacement is part of this repository update. Media are owner-authorized public examples, not remote private project exports.
