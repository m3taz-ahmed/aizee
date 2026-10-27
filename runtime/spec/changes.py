"""OpenSpec-style change folders: proposal -> design -> tasks -> archive.

Adopted from Fission-AI/OpenSpec: each change lives in
``specs/changes/<name>/{proposal.md, design.md, tasks.md, specs/}`` while it
is being worked, then ``archive`` moves it to
``specs/changes/archive/YYYY-MM-DD-<name>`` once the implementation lands.

Delta requirements inside ``specs/`` use ADDED/MODIFIED/REMOVED sections —
the same delta semantics as :class:`~runtime.spec.models.SpecDelta`.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

PROPOSAL_TEMPLATE = """# Proposal: {title}

## Why

<!-- What problem does this change solve? Why now? -->

## What changes

<!-- High-level description of the change. -->

## Impact

- Specs affected: <!-- list spec ids -->
- Code affected: <!-- list modules -->
- Breaking: no

"""

DESIGN_TEMPLATE = """# Design: {title}

## Context

<!-- Background and constraints. -->

## Decisions

<!-- Key technical decisions and alternatives considered. -->

## Risks

<!-- Known risks and mitigations. -->

"""

TASKS_TEMPLATE = """# Tasks: {title}

- [ ] Task 1 — describe
- [ ] Task 2 — describe
- [ ] Verify — run tests + quality gates

"""


@dataclass(frozen=True)
class ChangeInfo:
    name: str
    path: str
    has_proposal: bool
    has_design: bool
    has_tasks: bool
    tasks_done: int
    tasks_total: int
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "has_proposal": self.has_proposal,
            "has_design": self.has_design,
            "has_tasks": self.has_tasks,
            "tasks": {"done": self.tasks_done, "total": self.tasks_total},
            "archived": self.archived,
        }


class ChangesMixin:
    """Mixin on SpecEngine adding OpenSpec-style change-folder workflow."""

    specs_dir: Path  # provided by SpecEngine

    # -- layout --------------------------------------------------------------

    @property
    def changes_dir(self) -> Path:
        return self.specs_dir / "changes"

    @property
    def archive_dir(self) -> Path:
        return self.changes_dir / "archive"

    # -- operations ----------------------------------------------------------

    def propose(self, name: str, title: str = "") -> Path:
        """Create ``changes/<name>/`` with proposal/design/tasks skeletons."""
        if not _NAME_RE.match(name):
            raise ValueError(f"invalid change name {name!r}: use lowercase-slug")
        change_dir = self.changes_dir / name
        if change_dir.exists():
            raise FileExistsError(f"change {name!r} already exists at {change_dir}")
        (change_dir / "specs").mkdir(parents=True)
        title = title or name.replace("-", " ").title()
        (change_dir / "proposal.md").write_text(PROPOSAL_TEMPLATE.format(title=title), encoding="utf-8")
        (change_dir / "design.md").write_text(DESIGN_TEMPLATE.format(title=title), encoding="utf-8")
        (change_dir / "tasks.md").write_text(TASKS_TEMPLATE.format(title=title), encoding="utf-8")
        return change_dir

    def list_changes(self) -> list[ChangeInfo]:
        """List active (non-archived) changes with completion status."""
        return self._scan(self.changes_dir, archived=False)

    def list_archived(self) -> list[ChangeInfo]:
        """List archived changes."""
        return self._scan(self.archive_dir, archived=True)

    def change_status(self, name: str) -> ChangeInfo | None:
        change_dir = self.changes_dir / name
        if not change_dir.is_dir():
            return None
        return self._describe(change_dir, name, archived=False)

    def archive(self, name: str) -> Path:
        """Move a change to ``changes/archive/YYYY-MM-DD-<name>``."""
        change_dir = self.changes_dir / name
        if not change_dir.is_dir():
            raise FileNotFoundError(f"change {name!r} not found in {self.changes_dir}")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        target = self.archive_dir / f"{stamp}-{name}"
        counter = 1
        while target.exists():
            target = self.archive_dir / f"{stamp}-{name}-{counter}"
            counter += 1
        shutil.move(str(change_dir), str(target))
        return target

    # -- internals -----------------------------------------------------------

    def _scan(self, base: Path, archived: bool) -> list[ChangeInfo]:
        if not base.is_dir():
            return []
        infos = []
        for entry in sorted(base.iterdir()):
            if entry.is_dir() and entry.name != "archive":
                infos.append(self._describe(entry, entry.name, archived))
        return infos

    def _describe(self, change_dir: Path, name: str, archived: bool) -> ChangeInfo:
        tasks_file = change_dir / "tasks.md"
        done = total = 0
        if tasks_file.exists():
            for line in tasks_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("- ["):
                    total += 1
                    if stripped.startswith("- [x]") or stripped.startswith("- [X]"):
                        done += 1
        return ChangeInfo(
            name=name,
            path=str(change_dir),
            has_proposal=(change_dir / "proposal.md").exists(),
            has_design=(change_dir / "design.md").exists(),
            has_tasks=tasks_file.exists(),
            tasks_done=done,
            tasks_total=total,
            archived=archived,
        )
