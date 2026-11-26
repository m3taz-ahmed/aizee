#!/usr/bin/env python3
# Sync agent config files across tools — thin pointers to AGENTS.md canonical.
# Adapters must NOT embed the full AGENTS.md body: that inflates every harness's
# always-on context (~20 KB x N adapters per session). Emit a pointer instead;
# every modern harness reads AGENTS.md natively or follows the instruction to.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"

POINTER = """\
[FILE] aizee pointer
[OBJ] Keep this thin — the full OS rules load once from `AGENTS.md`, not from duplicated copies.

[RULES]
1. [REQ] Read `AGENTS.md` at the aiZee root (the directory containing `aizee_cli.py`) — it is the single canonical ruleset for this project. Apply it fully.
2. [REQ] Working dir = the aiZee root only; a sibling `aizee/` deployment mirror is READ-ONLY (sync via `scripts/update_aizee.bat`).
3. [PROHIBIT] `git add .` / `git add -A`; no commit, push, or destructive git without explicit user approval.
4. [REQ] Windows default shell is PowerShell — never bash syntax (`&&`, `2>nul`, `cat`, `ls`).
5. [REQ] Cold start is lean: read `Memory.md` (hot file) and pick the persona semantically from the Persona Menu in `AGENTS.md` — no detection CLI call, no bulk file loading.
"""


def require_agents() -> None:
    if not AGENTS.exists():
        print("AGENTS.md missing")
        sys.exit(1)


def cursor_mdc(description: str, globs: list[str]) -> str:
    globs_s = "[" + ", ".join(f'"{g}"' for g in globs) + "]"
    return (
        f"---\ndescription: {description}\nglobs: {globs_s}\nalwaysApply: true\n---\n\n"
        f"{POINTER}"
    )


def markdown_adapter() -> str:
    return f"# aiZee\n\n{POINTER}"


def aider_conf() -> str:
    # `read:` makes aider load the canonical files itself — no embedded body.
    # Pointer kept as YAML comments so the file stays parseable.
    commented = "\n".join("# " + line if line else "#" for line in POINTER.splitlines())
    return (
        "read:\n  - AGENTS.md\n  - Memory.md\n"
        "model: claude-sonnet-4-6\nauto-commits: false\ndirty-commits: false\n\n"
        f"{commented}\n"
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"  wrote {path.relative_to(ROOT)} ({len(content.encode('utf-8'))} B)")


def main() -> None:
    require_agents()
    write(ROOT / ".cursor" / "rules" / "aizee.mdc",
          cursor_mdc("aiZee pointer — canonical ruleset lives in AGENTS.md", []))
    write(ROOT / ".claude" / "CLAUDE.md", markdown_adapter())
    write(ROOT / ".clinerules" / "aizee.md", markdown_adapter())
    write(ROOT / ".windsurfrules", markdown_adapter())
    write(ROOT / ".aider.conf.yml", aider_conf())
    write(ROOT / ".github" / "copilot-instructions.md", markdown_adapter())
    print("Synced agent configs — pointers to AGENTS.md")


if __name__ == "__main__":
    main()
