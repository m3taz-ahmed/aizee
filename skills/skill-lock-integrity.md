---
name: skill-lock-integrity
category: checklist
description: Installed-skill integrity via skills-lock.json folder hashes. Use when installing, updating, or auditing skills — verify drift before trusting a skill's content.
triggers:
  - skill install
  - skill update
  - skills-lock
  - skill integrity
  - skill drift
personas:
  - dev
  - sec
---
[SKILL] skill-lock-integrity
[OBJ] Installed skills are pinned by content hash — any change, deletion, or unlocked skill is visible drift.
[RULES]
1. [REQ] After installing or updating skills, run `aizee skill lock-update` to re-pin `skills-lock.json`.
2. [REQ] Before trusting the skill library (release, deploy, security review), run `aizee skill lock-check` — changed/missing/unlocked skills must be explained, not ignored.
3. [REQ] A changed hash without a corresponding edit is tamper evidence — investigate before use.
4. [CMD] Commit `skills-lock.json` alongside skill changes so installs stay reproducible.
5. [PROHIBIT] Never hand-edit `skills-lock.json` hashes — always regenerate via lock-update.
