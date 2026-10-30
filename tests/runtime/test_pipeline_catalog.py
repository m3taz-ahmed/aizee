"""Tests for runtime/pipeline_catalog.py — artifact-aware pipeline detection."""

from __future__ import annotations

from pathlib import Path

from runtime.pipeline_catalog import (
    check_artifact,
    list_catalogs,
    pipeline_status,
)

_WORKFLOW = """[WORKFLOW] test-pipeline
[OBJ] test
[TRIGGER] test
[RULES]
1. [REQ] step
[CATALOG]
```yaml
label: Test Pipeline
paths:
  minimal:
    label: Minimal path
    steps:
      - id: brief
        name: Brief exists
        required: true
        artifact:
          glob: design/game-brief.md
      - id: manual
        name: Manual step
        required: false
        artifact:
          note: cannot auto-detect
phases:
  concept:
    label: Concept
    next_phase: build
    steps:
      - id: brief
        name: Brief exists
        required: true
        artifact:
          glob: design/game-brief.md
      - id: pillars
        name: Pillars documented
        required: true
        artifact:
          glob: design/**/*.md
          pattern: "pillars|Pillars"
  build:
    label: Build
    steps:
      - id: stories
        name: Stories written
        required: true
        artifact:
          glob: production/**/story-*.md
          min_count: 2
      - id: adrs
        name: ADR alternatives
        required: true
        artifact:
          any_of:
            - glob: docs/adr-*.md
            - glob: architecture/adr-*.md
```
"""


def _os_root(tmp_path: Path) -> Path:
    wf = tmp_path / "os" / "workflows"
    wf.mkdir(parents=True)
    (wf / "test-pipeline.md").write_text(_WORKFLOW, encoding="utf-8")
    return tmp_path / "os"


class TestListCatalogs:
    def test_finds_cataloged_workflow(self, tmp_path: Path):
        assert list_catalogs(_os_root(tmp_path)) == ["test-pipeline"]

    def test_ignores_plain_workflow(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "plain.md").write_text("[WORKFLOW] plain\n[RULES]\n")
        assert list_catalogs(os_root) == ["test-pipeline"]


class TestCheckArtifact:
    def test_glob_done(self, tmp_path: Path):
        (tmp_path / "design").mkdir()
        (tmp_path / "design/game-brief.md").write_text("brief")
        state, _ = check_artifact(tmp_path, {"glob": "design/game-brief.md"})
        assert state == "done"

    def test_glob_missing(self, tmp_path: Path):
        state, detail = check_artifact(tmp_path, {"glob": "design/game-brief.md"})
        assert state == "missing"
        assert "0/1" in detail

    def test_min_count(self, tmp_path: Path):
        stories = tmp_path / "production"
        stories.mkdir()
        (stories / "story-1.md").write_text("s")
        state, _ = check_artifact(
            tmp_path, {"glob": "production/**/story-*.md", "min_count": 2}
        )
        assert state == "missing"
        (stories / "story-2.md").write_text("s")
        state, _ = check_artifact(
            tmp_path, {"glob": "production/**/story-*.md", "min_count": 2}
        )
        assert state == "done"

    def test_pattern_match(self, tmp_path: Path):
        (tmp_path / "design").mkdir()
        (tmp_path / "design/doc.md").write_text("has Pillars section")
        state, _ = check_artifact(
            tmp_path, {"glob": "design/**/*.md", "pattern": "pillars|Pillars"}
        )
        assert state == "done"

    def test_pattern_no_match(self, tmp_path: Path):
        (tmp_path / "design").mkdir()
        (tmp_path / "design/doc.md").write_text("nothing relevant")
        state, _ = check_artifact(
            tmp_path, {"glob": "design/**/*.md", "pattern": "pillars"}
        )
        assert state == "missing"

    def test_any_of(self, tmp_path: Path):
        adr = tmp_path / "architecture"
        adr.mkdir()
        (adr / "adr-1.md").write_text("adr")
        state, _ = check_artifact(
            tmp_path,
            {"any_of": [{"glob": "docs/adr-*.md"}, {"glob": "architecture/adr-*.md"}]},
        )
        assert state == "done"

    def test_note_only_is_manual(self, tmp_path: Path):
        state, _ = check_artifact(tmp_path, {"note": "manual check"})
        assert state == "manual"

    def test_no_artifact_is_manual(self, tmp_path: Path):
        state, _ = check_artifact(tmp_path, None)
        assert state == "manual"


class TestPipelineStatus:
    def test_empty_project_starts_at_concept(self, tmp_path: Path):
        status = pipeline_status(_os_root(tmp_path), tmp_path, "test-pipeline")
        assert status is not None
        assert status.current_phase == "concept"
        assert status.next_step == "brief"
        assert not status.complete

    def test_progress_advances_phase(self, tmp_path: Path):
        (tmp_path / "design").mkdir()
        (tmp_path / "design/game-brief.md").write_text("brief\nPillars: x")
        status = pipeline_status(_os_root(tmp_path), tmp_path, "test-pipeline")
        assert status is not None
        # brief done + pillars pattern matched by same file
        assert status.phases[0].done
        assert status.current_phase == "build"

    def test_minimal_route(self, tmp_path: Path):
        status = pipeline_status(
            _os_root(tmp_path), tmp_path, "test-pipeline", path="minimal"
        )
        assert status is not None
        assert status.route == "minimal"
        assert status.phases[0].steps[1].status == "manual"

    def test_unknown_workflow_returns_none(self, tmp_path: Path):
        assert pipeline_status(_os_root(tmp_path), tmp_path, "nope") is None

    def test_no_catalog_returns_none(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "plain.md").write_text("[WORKFLOW] plain\n[RULES]\n")
        assert pipeline_status(os_root, tmp_path, "plain") is None

    def test_unreadable_workflow_returns_none(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "dirwf.md").mkdir()  # a directory, not a file
        assert pipeline_status(os_root, tmp_path, "dirwf") is None

    def test_to_dict_shape(self, tmp_path: Path):
        status = pipeline_status(_os_root(tmp_path), tmp_path, "test-pipeline")
        assert status is not None
        data = status.to_dict()
        assert data["workflow"] == "test-pipeline"
        assert data["phases"][0]["steps"][0]["id"] == "brief"


class TestCatalogBlockEdgeCases:
    def test_bad_yaml_block_skipped(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "mixed.md").write_text(
            "```yaml\n{{{{ invalid\n```\n```yaml\nphases:\n  p:\n    steps: []\n```\n"
        )
        assert "mixed" in list_catalogs(os_root)

    def test_yaml_block_without_catalog_keys_skipped(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "two.md").write_text(
            "```yaml\nname: unrelated\n```\n```yaml\nphases:\n  p:\n    steps: []\n```\n"
        )
        assert "two" in list_catalogs(os_root)


class TestCheckArtifactEdgeCases:
    def test_invalid_glob_pattern_is_missing(self, tmp_path: Path):
        state, detail = check_artifact(tmp_path, {"glob": "x**y"})
        assert state == "missing"
        assert "0/1" in detail

    def test_bad_regex_pattern(self, tmp_path: Path):
        (tmp_path / "design").mkdir()
        (tmp_path / "design/doc.md").write_text("x")
        state, detail = check_artifact(
            tmp_path, {"glob": "design/*.md", "pattern": "[unclosed"}
        )
        assert state == "missing"
        assert "bad pattern" in detail

    def test_any_of_nondict_and_glob_less_spec(self, tmp_path: Path):
        state, detail = check_artifact(
            tmp_path, {"any_of": ["nope", {"note": "cannot tell"}]}
        )
        assert state == "missing"
        assert "cannot tell" in detail


class TestRouteResolution:
    def test_paths_only_catalog_uses_first_path(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "paths-only.md").write_text(
            "```yaml\npaths:\n  minimal:\n    label: Min\n    steps: []\n```\n"
        )
        status = pipeline_status(os_root, tmp_path, "paths-only")
        assert status is not None
        assert status.route == "minimal"

    def test_steps_only_catalog_gives_empty_route(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "steps-only.md").write_text(
            "```yaml\nsteps: []\n```\n"
        )
        status = pipeline_status(os_root, tmp_path, "steps-only")
        assert status is not None
        assert status.route == ""
        assert status.phases == ()
        assert not status.complete

    def test_non_dict_step_skipped(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "stray.md").write_text(
            "```yaml\nphases:\n  p:\n    steps:\n      - just a string\n      - id: s\n"
            "        required: true\n        artifact:\n          glob: a.md\n```\n"
        )
        status = pipeline_status(os_root, tmp_path, "stray")
        assert status is not None
        assert len(status.phases[0].steps) == 1

    def test_optional_only_phase_is_current_without_next(self, tmp_path: Path):
        os_root = _os_root(tmp_path)
        (os_root / "workflows" / "opt.md").write_text(
            "```yaml\nphases:\n  prep:\n    steps:\n      - id: nice\n        required: false\n"
            "        artifact:\n          glob: z.md\n  work:\n    steps:\n"
            "      - id: w\n        required: true\n        artifact:\n          glob: a.md\n```\n"
        )
        status = pipeline_status(os_root, tmp_path, "opt")
        assert status is not None
        assert status.current_phase == "prep"
        assert status.next_step == ""

    def test_next_step_skips_done_required(self, tmp_path: Path):
        (tmp_path / "design").mkdir()
        (tmp_path / "design/game-brief.md").write_text("brief text only")
        status = pipeline_status(_os_root(tmp_path), tmp_path, "test-pipeline")
        assert status is not None
        assert status.current_phase == "concept"
        assert status.next_step == "pillars"
