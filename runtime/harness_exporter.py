"""Harness exporter — install aiZee skills into agent harnesses.

Adapted from Tencent/BrowserSkill's `bsk install-skill --harness X` —
a fixed table of target directories per harness; copies a skill's
SKILL.md (and sibling files) into the harness's skills folder.

Supported harnesses:
    cursor      ~/.cursor/skills/<name>/
    claude      ~/.claude/skills/<name>/
    codex       ~/.codex/skills/<name>/
    opencode    ~/.config/opencode/skills/<name>/
    project     ./.agents/skills/<name>/    (per-repo, read natively by Amp et al.)
    devin       ./.devin/skills/<name>/     (per-repo, read natively by Devin)
    windsurf    ./.windsurf/skills/<name>/  (per-repo, read natively by Windsurf)
    path        arbitrary --dest directory

Skill packaging extras:
    emit_openai_binding() — write ``agents/openai.yaml`` into a skill dir
    (Stickman/OpenAI agent-manifest format, adopted from
    kaomei/stickman-video-director).
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SKILL_FILENAME = "SKILL.md"

# Harness name -> skills dir under the user's home.
# ``agents`` is the cross-agent shared standard (~/.agents/skills) read
# natively by many harnesses (Amp, Codex, Cursor, Cline, Zed, ...) per the
# agentskills.io install matrix — installing there covers every harness
# that honors the shared layout in one copy.
_HARNESS_DIRS: dict[str, str] = {
    "agents": ".agents/skills",
    "cursor": ".cursor/skills",
    "claude": ".claude/skills",
    "codex": ".codex/skills",
    "opencode": ".config/opencode/skills",
}


@dataclass
class InstallResult:
    """Outcome of a single skill install."""

    skill: str
    harness: str
    dest: str = ""
    files: list[str] = field(default_factory=list)
    ok: bool = False
    error: str = ""
    overwritten: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "harness": self.harness,
            "dest": self.dest,
            "files": self.files,
            "ok": self.ok,
            "error": self.error or None,
            "overwritten": self.overwritten,
        }


def harnesses() -> dict[str, str]:
    """Harness name -> resolved target directory."""
    home = Path.home()
    return {name: str(home / rel) for name, rel in _HARNESS_DIRS.items()}


def detect_installed(home: Path | None = None) -> dict[str, Any]:
    """Detect which harnesses are actually installed on this machine.

    A harness counts as installed when its config home exists (e.g.
    ``~/.cursor``), even if its ``skills/`` subdir has not been created yet
    — installing the skills dir into an existing harness home is exactly
    the desired behavior. The shared ``agents`` target is always reported:
    it is a creatable standard location, not tied to one vendor.
    """
    base = home or Path.home()
    detected: dict[str, str] = {}
    skipped: list[str] = []
    for name, rel in _HARNESS_DIRS.items():
        harness_home = base / rel.split("/")[0]
        if name == "agents" or harness_home.is_dir():
            detected[name] = str(base / rel)
        else:
            skipped.append(name)
    return {"detected": detected, "skipped": skipped}


def install_auto(
    skills_root: Path,
    name: str,
    force: bool = False,
    home: Path | None = None,
) -> dict[str, Any]:
    """Install one skill into every detected harness. Returns per-harness results."""
    scan = detect_installed(home)
    results = [
        install_skill(skills_root, name, harness, force=force, home=home).to_dict()
        for harness in sorted(scan["detected"])
    ]
    # ``results`` is never empty: the shared ``agents`` target is always
    # detected, so there is at least one install attempt to report on.
    return {
        "ok": all(r["ok"] for r in results),
        "skill": name,
        "installed": sum(1 for r in results if r["ok"]),
        "skipped_harnesses": scan["skipped"],
        "results": results,
    }


# Harness name -> project-relative skills dir (per-repo targets).
_PROJECT_DIRS = {
    "project": ".agents/skills",
    "devin": ".devin/skills",
    "windsurf": ".windsurf/skills",
}


def resolve_harness_dir(harness: str, dest: str = "", home: Path | None = None) -> Path:
    """Resolve target directory for a harness name or explicit path."""
    harness = harness.strip().lower()
    if harness in _PROJECT_DIRS:
        return Path.cwd() / _PROJECT_DIRS[harness]
    if harness == "path":
        if not dest:
            raise ValueError("harness 'path' requires --dest <dir>")
        return Path(dest).expanduser()
    if harness in _HARNESS_DIRS:
        return (home or Path.home()) / _HARNESS_DIRS[harness]
    raise ValueError(
        f"unknown harness '{harness}' — supported: "
        + ", ".join(sorted([*_HARNESS_DIRS, *_PROJECT_DIRS, "path"]))
    )


def _find_skill_dir(skills_root: Path, name: str) -> Path:
    """Locate a skill source dir: directory form or flat `<name>.md`."""
    candidate = skills_root / name
    if candidate.is_dir() and (candidate / SKILL_FILENAME).exists():
        return candidate
    flat = skills_root / f"{name}.md"
    if flat.exists():
        return flat
    raise FileNotFoundError(f"skill '{name}' not found under {skills_root}")


def install_skill(
    skills_root: Path,
    name: str,
    harness: str,
    dest: str = "",
    force: bool = False,
    home: Path | None = None,
) -> InstallResult:
    """Install one skill into a harness directory.

    Directory skills copy recursively; flat `<name>.md` skills copy the
    single file as `<dest>/<name>.md`. Returns an InstallResult; never
    raises for missing skills (FileNotFoundError -> result.error).
    """
    result = InstallResult(skill=name, harness=harness)
    try:
        src = _find_skill_dir(Path(skills_root), name)
        target_base = resolve_harness_dir(harness, dest, home=home)
        if src.is_dir():
            target = target_base / name
            if target.exists():
                if not force:
                    result.error = f"'{target}' exists — pass --force to overwrite"
                    result.dest = str(target)
                    return result
                shutil.rmtree(target)
                result.overwritten = True
            shutil.copytree(src, target)
            result.files = [
                str(p.relative_to(target))
                for p in sorted(target.rglob("*"))
                if p.is_file()
            ]
        else:
            target_base.mkdir(parents=True, exist_ok=True)
            target = target_base / src.name
            if target.exists() and not force:
                result.error = f"'{target}' exists — pass --force to overwrite"
                result.dest = str(target)
                return result
            result.overwritten = target.exists()
            shutil.copy2(src, target)
            result.files = [src.name]
        result.dest = str(target)
        result.ok = True
        return result
    except (FileNotFoundError, ValueError, OSError) as exc:
        result.error = str(exc)
        return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    p = argparse.ArgumentParser(
        prog="aizee-install-skill",
        description="Install aiZee skills into agent harnesses",
    )
    p.add_argument(
        "name", nargs="?", help="skill name (dir or flat .md under skills/)"
    )
    p.add_argument("--all", dest="all_skills", action="store_true",
                   help="install every skill under --skills-root")
    p.add_argument(
        "--harness",
        default="project",
        help="cursor|claude|codex|opencode|project|path",
    )
    p.add_argument("--dest", default="", help="target dir when --harness path")
    p.add_argument("--force", action="store_true", help="overwrite existing")
    p.add_argument("--skills-root", default="skills")
    p.add_argument("--list", action="store_true", help="list harnesses and exit")
    args = p.parse_args(argv)

    if args.list:
        print(json.dumps(harnesses(), indent=2))
        return 0

    r = install_skill(
        Path(args.skills_root), args.name, args.harness, args.dest, args.force
    )
    print(json.dumps(r.to_dict(), indent=2))
    return 0 if r.ok else 1


_OPENAI_MANIFEST = "agents/openai.yaml"


def openai_binding(name: str, description: str) -> dict[str, Any]:
    """Build the ``agents/openai.yaml`` manifest payload for one skill.

    Adopted from stickman-video-director's ``agents/openai.yaml``: an
    ``interface`` block naming the skill in the OpenAI agent surface and a
    ``default_prompt`` that invokes it via the ``$<skill>`` convention.
    """
    display = name.replace("-", " ").replace("_", " ").title()
    short = " ".join(description.split())[:140]
    return {
        "interface": {
            "display_name": display,
            "short_description": short,
            "default_prompt": f"Use ${name} to help with this task.",
        }
    }


def emit_openai_binding(
    skills_root: Path, name: str, *, force: bool = False
) -> InstallResult:
    """Write ``agents/openai.yaml`` inside a skill's directory.

    Only directory skills carry agent manifests; flat ``<name>.md`` skills
    have no sibling space and return an error result.
    """
    import yaml

    from runtime.rule_frontmatter import parse_frontmatter

    result = InstallResult(skill=name, harness="openai")
    try:
        src = _find_skill_dir(Path(skills_root), name)
        if not src.is_dir():
            result.error = f"skill '{name}' is flat — openai.yaml needs a skill directory"
            return result
        target = src / _OPENAI_MANIFEST
        if target.exists() and not force:
            result.error = f"'{target}' exists — pass --force to overwrite"
            result.dest = str(target)
            return result
        result.overwritten = target.exists()
        text = (src / SKILL_FILENAME).read_text(encoding="utf-8", errors="replace")
        meta, _body = parse_frontmatter(text)
        description = meta.description.strip()
        payload = openai_binding(name, description)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        result.dest = str(target)
        result.files = [str(target.relative_to(src))]
        result.ok = True
        return result
    except (FileNotFoundError, OSError) as exc:
        result.error = str(exc)
        return result


def build_discovery_index(skills_root: Path, *, kind: str = "skill") -> dict[str, Any]:
    """Content-addressed discovery index over a skills directory.

    Adopted from vercel-labs/agent-skills' immutable release + discovery
    index: every entry carries a sha256 of its source file, so the hash is
    the release identity — any edit changes it, and consumers can detect
    drift or pin a skill without a version field (skills-lock.json parity).
    Metadata comes from ``build_catalog_from_directory`` so the index and
    the catalog never disagree on names, triggers, or invoke class.
    """
    from runtime.service_catalog import build_catalog_from_directory

    root = Path(skills_root)
    catalog = build_catalog_from_directory(root, kind=kind)
    entries: dict[str, Any] = {}
    for desc in sorted(catalog.all(), key=lambda d: d.name):
        path = Path(desc.file_path)
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            digest = ""
        rel = (
            path.name
            if path.parent == root
            else f"{path.parent.name}/{path.name}"
        )
        entries[desc.name] = {
            "file": rel,
            "description": desc.description,
            "invoke": desc.invoke,
            "triggers": sorted(desc.triggers),
            "sha256": digest,
        }
    return {"kind": kind, "count": len(entries), "skills": entries}


if __name__ == "__main__":
    sys.exit(main())
