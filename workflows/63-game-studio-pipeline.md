[WORKFLOW] 63-game-studio-pipeline
[OBJ] Full-lifecycle game pipeline — concept to release — adapted from Claude-Code-Game-Studios (MIT) studio model. Minimal-path-first: evidence over documents; phase gates advisory.
[TRIGGER] game pipeline | game project | build a game | gdd | vertical slice | لعبة جديدة | تطوير لعبة | ستوديو العاب
[RULES]
1. [REQ] Detect stage first: existing artifacts (engine choice, brief, GDDs, stories, code) determine entry point — never restart a pipeline that already has evidence on disk. `aizee pipeline status` reads the catalog below.
2. [REQ] Rigour default is MINIMAL: one-page brief + stories + build loop. Escalate to standard/full only when the project grows or the user asks — extra docs buy traceability, not a better game (measured: standard tier produced 30 pre-code docs and ranked last in blind review).
3. [REQ] Minimal path: engine setup -> `templates/game-brief.md` (one page: pitch, MVP features, build order) -> stories in build order -> dev-story loop -> story-done with OBSERVED evidence.
4. [REQ] Standard/full path phases: Concept (brief, pillars, art bible, systems map) -> Systems Design (per-system GDD via `game-design-lord`, cross-review, consistency check) -> Technical Setup (architecture doc, >=3 foundation ADRs, control manifest, test harness) -> Pre-Production (epics, stories, sprint plan, QA plan) -> Production (dev-story loop, reviews, evidence) -> Polish -> Release (certification checklist, changelog, patch notes via `game-production-lord`).
5. [REQ] Phase gates are ADVISORY verdicts (gate-check pattern): required artifacts listed, gaps surfaced, user decides proceed/defer — gates never hard-block.
6. [REQ] Story contract: acceptance criteria + test-evidence plan + dependencies + out-of-scope + risk. Implementer sets `In Progress` only; closing is the closer's job alone. `rules/run-and-observe.md` applies to every visual story at every rigor level.
7. [REQ] Persona routing: design docs -> `game-design-lord`; levels -> `game-level-design-lord`; economy -> `game-economy-lord`; fiction -> `game-narrative-lord`; QA/evidence -> `game-qa-lord`; planning/release -> `game-production-lord`; code -> `game-architect` + engine tech-stack (`tech-stack/godot-4.md|unity-6.md|unreal-5.md` after `[VER-01]`).
8. [REQ] Engine pinned before implementation: read lockfile/project file for exact version, load matching tech-stack file, query Context7 for engine APIs before writing engine code.
9. [REQ] Team features: cross-domain work routes through `workflows/64-game-feature-teams.md` (combat/UI/narrative/audio/level/release/QA team recipes).
10. [PROHIBIT] GDD-writing before pillar agreement at standard+; story implementation without `Ready` status; skipping the OBSERVED evidence step at any rigor level; milestone claims without linked artifacts.
[CATALOG]
```yaml
label: Game Studio Pipeline
paths:
  minimal:
    label: Minimal path
    steps:
      - id: engine-setup
        name: Engine configured
        required: true
        artifact:
          any_of:
            - glob: project.godot
            - glob: "**/*.uproject"
            - glob: ProjectSettings/ProjectVersion.txt
            - glob: aizee.yaml
              pattern: "engine:"
      - id: game-brief
        name: One-page game brief
        required: true
        artifact:
          any_of:
            - glob: design/game-brief.md
            - glob: docs/game-brief.md
      - id: stories
        name: Stories in build order
        required: true
        artifact:
          any_of:
            - glob: production/**/story-*.md
            - glob: stories/*.md
            - glob: .task/**/*.md
              note: story tracking may live in task system
      - id: build-loop
        name: Implement + close stories
        required: true
        repeatable: true
        artifact:
          glob: production/qa/evidence/**
          note: OBSERVED runs retained per story
phases:
  concept:
    label: Concept
    next_phase: systems-design
    steps:
      - id: brief
        name: Game brief
        required: true
        artifact:
          any_of:
            - glob: design/game-brief.md
            - glob: docs/game-brief.md
      - id: pillars
        name: Design pillars
        required: true
        artifact:
          glob: design/**/*.md
          pattern: "pillars|Pillars"
      - id: systems-map
        name: Systems index
        required: false
        artifact:
          glob: design/**/systems-*.md
  systems-design:
    label: Systems Design
    next_phase: technical-setup
    steps:
      - id: system-gdds
        name: Per-system GDDs
        required: true
        repeatable: true
        artifact:
          glob: design/gdd/*.md
          min_count: 1
  technical-setup:
    label: Technical Setup
    next_phase: pre-production
    steps:
      - id: architecture
        name: Architecture doc
        required: true
        artifact:
          any_of:
            - glob: docs/architecture*.md
            - glob: docs/architecture/*.md
      - id: adrs
        name: Foundation ADRs
        required: true
        artifact:
          glob: docs/**/adr-*.md
          min_count: 3
  pre-production:
    label: Pre-Production
    next_phase: production
    steps:
      - id: epics
        name: Epics + stories
        required: true
        artifact:
          any_of:
            - glob: production/epics/**/*.md
            - glob: stories/*.md
      - id: test-setup
        name: Test harness
        required: true
        artifact:
          any_of:
            - glob: tests/**
            - glob: "**/test_*.gd"
            - glob: "**/*Test*.cs"
  production:
    label: Production
    next_phase: release
    steps:
      - id: implement
        name: Dev-story loop
        required: true
        repeatable: true
        artifact:
          glob: production/qa/evidence/**
          note: run-and-observe evidence per visual story
  release:
    label: Release
    steps:
      - id: release-checklist
        name: Release + certification checklist
        required: true
        artifact:
          any_of:
            - glob: production/**/release-checklist*.md
            - glob: docs/**/release*.md
      - id: changelog
        name: Changelog / patch notes
        required: true
        artifact:
          any_of:
            - glob: CHANGELOG.md
            - glob: production/**/patch-notes*.md
```
