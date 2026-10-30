[WORKFLOW] 64-game-feature-teams
[OBJ] Cross-domain team recipes for one game feature — adapted from CCGS /team-* orchestration. Composes persona + lord sets so a feature ships coherent, not per-silo.
[TRIGGER] game feature team | team combat | team ui | team narrative | team release | فريق تطوير لعبة
[RULES]
1. [REQ] Compose per feature, not per task: a feature team names one owner (drives decisions) + contributors (consulted, no binding cross-domain calls) + the conflict-escalation owner.
2. [REQ] Team recipes — combat/systems feature: owner `game-design-lord`; code `game-architect` + engine specialist; economy `game-economy-lord` (if costs/rewards); QA `game-qa-lord`; producer `game-production-lord` for scope.
3. [REQ] Team recipes — UI/HUD feature: owner design (ux-designer or `game-design-lord`); code `game-architect`/`frontend-ui-expert`; narrative `game-narrative-lord` (tone of copy); accessibility + localization checks mandatory; QA `game-qa-lord` for OBSERVED evidence.
4. [REQ] Team recipes — narrative/quest feature: owner `game-narrative-lord` (canon); design `game-design-lord` (verb + rejoin points); level `game-level-design-lord` (staging); QA `game-qa-lord`.
5. [REQ] Team recipes — level/world feature: owner `game-level-design-lord`; design `game-design-lord` (pillar fit); narrative `game-narrative-lord` (environmental story); performance review before art pass.
6. [REQ] Team recipes — audio feature: owner sound direction (surface to user — no dedicated lord yet); design + level consulted; QA verifies audio evidence on target device.
7. [REQ] Team recipes — release feature: owner `game-production-lord`; QA `game-qa-lord` (certification evidence); all leads consulted on changelog entries; security review for online components.
8. [REQ] Team recipes — polish/performance feature: owner `game-architect`; performance-analyst rules apply (profile worst-case scene on target device); design consulted on juice/feel tradeoffs.
9. [REQ] Escalation: same-tier disagreement escalates to the shared owner (design disputes -> `game-design-lord`; technical -> `game-architect`; schedule -> `game-production-lord`); user is the final call.
10. [PROHIBIT] Team members editing outside their domain without explicit delegation; two owners on one feature; consultation treated as approval — the owner decides, consultants advise.
