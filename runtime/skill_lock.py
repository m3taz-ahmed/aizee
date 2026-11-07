"""Skill lock file (vercel-labs/skills `skills-lock.json` adoption).

Installed skills are pinned by content hash so installs are reproducible
and drift is detectable:

- ``folder_hash(path)`` — sha256 over the skill's files (names + bytes),
  our equivalent of the GitHub ``skillFolderHash`` tree SHA.
- ``SkillLock`` — reads/writes ``skills-lock.json`` (v1) at the repo root.
- ``check`` — recomputes hashes and reports changed/missing/extra skills.
- ``record``/``remove`` — keep the lock in sync with ``skill link``/pack.

Format::

    {"version": 1,
     "skills": {"<name>": {"path": "skills/<name>",
                          "hash": "<sha256[:16]>",
                          "source": "local|pack:<dir>",
                          "installed": "<iso8601>"}}}
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOCK_VERSION = 1
LOCK_FILENAME = "skills-lock.json"
_SKIP_NAMES = {"index.json", ".ds_store", "thumbs.db"}


def folder_hash(path: Path) -> str:
    """Content hash over every file under ``path`` (sorted by name)."""
    h = hashlib.sha256()
    if path.is_file():
        files = [path]
        base = path.parent
    else:
        files = sorted(p for p in path.rglob("*") if p.is_file() and p.name.lower() not in _SKIP_NAMES)
        base = path
    for f in files:
        h.update(str(f.relative_to(base)).replace("\\", "/").encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:16]


@dataclass
class LockEntry:
    name: str
    path: str
    hash: str
    source: str = "local"
    installed: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "hash": self.hash,
            "source": self.source,
            "installed": self.installed,
        }


@dataclass
class LockReport:
    ok: bool
    changed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    locked: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "locked": self.locked,
            "changed": self.changed,
            "missing": self.missing,
            "extra": self.extra,
        }


class SkillLock:
    """Repo-root ``skills-lock.json`` management."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / LOCK_FILENAME

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": LOCK_VERSION, "skills": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": LOCK_VERSION, "skills": {}}
        if not isinstance(data, dict) or data.get("version") != LOCK_VERSION:
            return {"version": LOCK_VERSION, "skills": {}}
        if not isinstance(data.get("skills"), dict):
            data["skills"] = {}
        return data

    def entries(self) -> dict[str, LockEntry]:
        return {
            name: LockEntry(
                name=name,
                path=str(e.get("path", "")),
                hash=str(e.get("hash", "")),
                source=str(e.get("source", "local")),
                installed=str(e.get("installed", "")),
            )
            for name, e in self._read()["skills"].items()
            if isinstance(e, dict)
        }

    def _write(self, skills: dict[str, dict[str, Any]]) -> None:
        self.path.write_text(
            json.dumps({"version": LOCK_VERSION, "skills": skills}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def record(self, name: str, path: Path, *, source: str = "local") -> LockEntry:
        """Add/update a lock entry for an installed skill dir."""
        data = self._read()
        rel = str(path.relative_to(self.root)).replace("\\", "/") if path.is_relative_to(self.root) else str(path)
        entry = LockEntry(
            name=name,
            path=rel,
            hash=folder_hash(path),
            source=source,
            installed=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        data["skills"][name] = entry.to_dict()
        self._write(data["skills"])
        return entry

    def remove(self, name: str) -> bool:
        data = self._read()
        if name not in data["skills"]:
            return False
        del data["skills"][name]
        self._write(data["skills"])
        return True

    def record_all_local(self, skills_dir: Path | None = None) -> int:
        """Rebuild the lock from every local skill on disk (flat + dir).

        Entries whose recorded path no longer exists are pruned, so
        renames/deletes don't leave ghost locks.
        """
        skills_dir = skills_dir or self.root / "skills"
        data = self._read()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for name in list(data["skills"]):
            rec_path = data["skills"][name].get("path", "")
            if rec_path and not (self.root / rec_path).exists():
                del data["skills"][name]
        if skills_dir.is_dir():
            for p in sorted(skills_dir.glob("*.md")):
                if p.name in ("README.md", "index.json"):
                    continue
                data["skills"][p.stem] = LockEntry(
                    name=p.stem,
                    path=str(p.relative_to(self.root)).replace("\\", "/"),
                    hash=folder_hash(p),
                    source="local",
                    installed=now,
                ).to_dict()
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir() and (d / "SKILL.md").exists():
                    data["skills"][d.name] = LockEntry(
                        name=d.name,
                        path=str(d.relative_to(self.root)).replace("\\", "/"),
                        hash=folder_hash(d),
                        source="local",
                        installed=now,
                    ).to_dict()
        self._write(data["skills"])
        return len(data["skills"])

    def check(self) -> LockReport:
        """Recompute hashes; report changed/missing/extra skills."""
        entries = self.entries()
        report = LockReport(ok=True, locked=len(entries))
        disk_paths: set[str] = set()
        for name, e in entries.items():
            p = self.root / e.path
            if not p.exists():
                report.missing.append(name)
                continue
            disk_paths.add(e.path)
            if folder_hash(p) != e.hash:
                report.changed.append(name)
        skills_dir = self.root / "skills"
        if skills_dir.is_dir():
            for p in sorted(skills_dir.glob("*.md")):
                if p.name in ("README.md", "index.json"):
                    continue
                rel = str(p.relative_to(self.root)).replace("\\", "/")
                if rel not in disk_paths:
                    report.extra.append(p.stem)
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir() and (d / "SKILL.md").exists():
                    rel = str(d.relative_to(self.root)).replace("\\", "/")
                    if rel not in disk_paths:
                        report.extra.append(d.name)
        report.ok = not (report.changed or report.missing)
        return report
