"""Regenerate Scripts/*.exe entry-point launchers after interpreter relocation.

Uses pip's vendored distlib ScriptMaker so generated .exe files embed the
new interpreter path. Run with the relocated interpreter:

    E:\\runtimes\\python\\3.15\\python.exe regen_launchers.py
"""

from __future__ import annotations

import sys
import sysconfig
from importlib.metadata import distributions

from pip._vendor.distlib.scripts import ScriptMaker


def main() -> None:
    scripts_dir = sysconfig.get_path("scripts")
    maker = ScriptMaker(None, scripts_dir)
    maker.executable = sys.executable
    maker.clobber = True

    regenerated: list[str] = []
    errors: list[str] = []
    for dist in distributions():
        try:
            entry_points = dist.entry_points
        except Exception as exc:  # report and continue
            errors.append(f"{dist.name}: metadata read failed: {exc}")
            continue
        for ep in entry_points:
            if ep.group not in ("console_scripts", "gui_scripts"):
                continue
            try:
                spec = f"{ep.name} = {ep.value}"
                maker.make(spec, {"gui": ep.group == "gui_scripts"})
                regenerated.append(ep.name)
            except Exception as exc:  # collect all failures
                errors.append(f"{ep.name}: {exc}")

    print(f"[{sys.executable}]")
    print(f"  regenerated {len(regenerated)} launchers -> {scripts_dir}")
    for err in errors:
        print(f"  ERROR: {err}")


if __name__ == "__main__":
    main()
