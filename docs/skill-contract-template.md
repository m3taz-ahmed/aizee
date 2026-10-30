# <skill-name> — Handoff Contract

> Optional `CONTRACT.md` beside a `SKILL.md` (directory skills only). Declares what the skill requires, produces, and must never do — so handoffs are explicit and the contract is lintable (`aizee skill lint`).
> Pattern adapted from Claude-Code-Game-Studios (MIT).

## Role in Pipeline
<One paragraph: where this skill sits, what it bridges, what upstream/downstream skills expect of it.>

## Inputs Required

### Files That Must Exist
| File | Required fields / sections | Read-only? |
|------|---------------------------|------------|
| <path/glob> | <fields the skill reads> | Yes / No |

### Preconditions
- <state that must hold before the skill runs — statuses, versions, approvals>

## Outputs Produced

### Files Written
| File | Guaranteed fields / sections | Notes |
|------|------------------------------|-------|
| <path/glob> | <what the skill guarantees to write> | |

### Output Guarantees
- <behavioral guarantees: naming, evidence, status transitions, verification result>

## Immutability Rules
- READS but does NOT modify: <paths>
- MODIFIES only: <paths — and through whom>

## Hard Constraints (Never Violate)
- <absolute rules — scope boundaries, forbidden writes, approval requirements>
