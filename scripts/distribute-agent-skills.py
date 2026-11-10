"""Distribute .ai/skills into agent-scanned dirs via junctions/hardlinks.

- dir-skills  -> <target>/<name>   NTFS junction -> skills/<name>
- flat skills -> <target>/<name>.md NTFS hardlink -> skills/<name>.md

Targets: .agents/skills (agentskills.io standard), .devin/skills (Devin),
.claude/skills (Claude Code). All machine-local -> gitignored.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(r"E:\server\.ai")
SRC = ROOT / "skills"
TARGETS = [ROOT / ".agents" / "skills", ROOT / ".devin" / "skills", ROOT / ".claude" / "skills"]


def junction(link: Path, target: Path) -> str:
    if link.exists() or link.is_junction():
        return "exists"
    os.system(f'cmd /c mklink /J "{link}" "{target}" >nul 2>&1')
    return "junction" if link.exists() else "FAIL"


def hardlink(link: Path, target: Path) -> str:
    if link.exists():
        return "exists"
    try:
        os.link(target, link)
        return "hardlink"
    except OSError as exc:
        return f"FAIL:{exc}"


def main() -> int:
    dirs = sorted(d for d in SRC.iterdir() if d.is_dir() and (d / "SKILL.md").is_file())
    flats = sorted(p for p in SRC.glob("*.md") if p.stem not in {"README", "EVAL"})
    print(f"src: {len(dirs)} dir-skills + {len(flats)} flat = {len(dirs) + len(flats)}")
    stats = {"junction": 0, "hardlink": 0, "exists": 0, "FAIL": 0}
    for t in TARGETS:
        t.mkdir(parents=True, exist_ok=True)
        for d in dirs:
            r = junction(t / d.name, d)
            stats[r.split(":")[0]] = stats.get(r.split(":")[0], 0) + 1
            if r.startswith("FAIL"):
                print("FAIL", t, d.name, r)
        for f in flats:
            r = hardlink(t / f.name, f)
            stats[r.split(":")[0]] = stats.get(r.split(":")[0], 0) + 1
            if r.startswith("FAIL"):
                print("FAIL", t, f.name, r)
        n = sum(1 for _ in t.iterdir())
        print(f"{t}: {n} entries")
    print(stats)
    return 0 if stats["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
