# Economy Model — <game title>

> Graph before tuning. Every resource names sources, sinks, and converters.

## Resources
| Resource | Type | Sources (verbs) | Sinks (choices) | Converters |
|----------|------|-----------------|-----------------|------------|
| <name> | soft / hard / item / energy | <how earned> | <how spent> | <conversion path> |

## Flow Targets
- Earn rate (new / regular / veteran): <units per session>
- Burn rate per segment: <units per session>
- Max intended stockpile: <N days of burn>

## Progression Curve
- Target curve: linear / exponential / S-curve
- Time-to-milestone: <session count per unlock tier>
- Max session grind: <minutes>

## Loot / Drop Tables
| Table | Entries (prob sums to 1.0) | Pity rule | Duplicate path |
|-------|----------------------------|-----------|----------------|

## Inflation Watch
- Signals: <hoarding threshold, price drift, dead sinks>
- Corrective levers: <new sink, earn-rate change, seasonal reset>

## Live Tuning Notes
- Data files: <paths>   Versioned: yes/no   Rollback plan: <one line>
