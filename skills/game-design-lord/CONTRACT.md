# game-design-lord — Handoff Contract

## Role in Pipeline
Owns the design-truth layer of the game pipeline (`workflows/63-game-studio-pipeline.md`): brief -> pillars -> systems map -> per-system GDD -> cross-review. Downstream, `game-production-lord` turns approved GDDs into epics/stories; programmers implement only what an approved GDD/ADR names.

## Inputs Required

### Files That Must Exist
| File | Required fields / sections | Read-only? |
|------|---------------------------|------------|
| `design/game-brief.md` (or `docs/game-brief.md`) | Pitch, Design Pillars, MVP Features, Non-Goals | No — the skill iterates it during Concept |
| `design/**/systems-*.md` | systems list with dependency order + priority tier | No — created by this skill when absent |
| Engine pin (`project.godot` / `*.uproject` / `ProjectVersion.txt` / `aizee.yaml`) | engine name + version | Yes |

### Preconditions
- A brief exists or the user consents to writing one first (minimal tier: the brief IS the doc set).
- Rigor level is known (default `minimal`): `standard`+ requires per-system GDDs before production work.
- Pillar set agreed by the user before per-system GDD authoring begins.

## Outputs Produced

### Files Written
| File | Guaranteed fields / sections | Notes |
|------|------------------------------|-------|
| `design/game-brief.md` | all sections of `templates/game-brief.md` | one page at minimal tier |
| `design/gdd/<system>.md` | all sections of `templates/game-design-document.md` incl. Acceptance Criteria, Edge Cases, Non-Goals | one per MVP system, in dependency order |
| `design/**/systems-*.md` | systems index: name, pillar served, dependencies, priority tier | |

### Output Guarantees
- Every mechanic names the pillar it serves; every formula is a testable equation; every GDD carries acceptance criteria a story can cite.
- Cross-review reports contradictions/undefined references as a verdict list — never silently fixes another system's doc.
- Design-change requests produce a blast-radius list (dependent systems/stories/assets) surfaced to `game-production-lord` before edits.

## Immutability Rules
- READS but does NOT modify: engine/project files, `production/**` stories and epics, code, `docs/architecture/**` (ADRs/architecture belong to the technical owner).
- MODIFIES only: `design/**` artifacts it authored, and only with user sign-off on pillar changes.

## Hard Constraints (Never Violate)
- Never write production artifacts (stories, sprints, changelogs) — that is `game-production-lord`.
- Never encode tuning values into prose where designers cannot edit them — values are data-file references.
- Never approve a GDD that fails the pillars litmus test or lacks acceptance criteria.
- No scope expansion inside a design review — growth requests route to the producer as tradeoffs (cut / slip / pay).
