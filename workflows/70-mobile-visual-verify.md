---
description: Mobile visual verification loop — scrcpy/adb capture + unslop methodology + governed tunnels
triggers: [mobile ui, visual verification, screenshot review, android ui test, verify app ui]
---

# Mobile Visual Verification Loop

Combines the three repo lessons: scrcpy's component reuse + ephemeral
deployment, unslop-anything's evidence-not-truth review methodology, and
tunnelto/cloudflared's governed local-backend exposure.

## Phase 0 — Setup

1. Confirm device: `adb devices` — exactly one target or pass `-s <serial>`.
2. Never install persistent agents on the device. scrcpy's server is pushed
   to `/data/local/tmp`, executed, and removed — copy that pattern for any
   helper artifact.
3. Pin external tool versions (`scrcpy --version`, `adb version`) in the
   evidence report. Do not pip/curl-install anything mid-task.

## Phase 1 — Capture matrix

Capture screenshots across the states that actually break mobile UI:

- light + dark theme
- smallest width / largest font (accessibility scaling)
- rotation (portrait + landscape) when the app allows it
- empty state, error state, offline state — not just the happy path

Commands (per state):

```
adb shell screencap -p /sdcard/shot.png
adb pull /sdcard/shot.png state/mobile-verify/<date>/<scope>/<state>.png
adb shell rm /sdcard/shot.png
```

For interaction sequences use `adb shell input tap/swipe/text` — never blind
coordinates without a prior screenshot: capture → locate → act → re-capture.

## Phase 2 — Backend exposure (only when needed)

If the app talks to a localhost backend:

```
aizee tunnel start --provider cloudflared --port <port> --ttl 1800
```

- Treat the printed URL as a bearer secret — never commit it, never echo it
  into shared logs.
- Verify the health endpoint through the tunnel BEFORE pointing the app at it.
- When done: `aizee tunnel stop <id>`. TTL auto-sweep is the backstop, not
  the plan.

## Phase 3 — Review (evidence, not truth)

Per unslop-anything's rule: static detector output is a LEAD, never a verdict.

1. Review each screenshot visually first — task completion blockers outrank
   aesthetic issues.
2. Order findings: (a) task blockers, (b) performance uncertainty,
   (c) generic/visual slop.
3. Record intentional exceptions in the project chart
   (`state/mobile-verify/chart.md`) so they are never re-reported.
4. Never change business logic, navigation structure, or visual identity
   without explicit user approval.

## Phase 4 — Fix + verify

After every fix batch, re-capture the SAME matrix states into
`state/mobile-verify/<date>/<scope>/after/` and diff against before/. A fix
is not done until its evidence exists.

## Anti-patterns

- No polling loops waiting for devices — use `adb wait-for-device`.
- No mixing control actions into telemetry capture streams.
- No persistent device modifications; ephemeral push-run-clean only.
