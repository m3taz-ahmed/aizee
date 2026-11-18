"""Machine profile — one-shot hardware/environment fingerprint.

Adopted from ApkStart's preflight concept (``src/core/preflight.js``): probe
the machine once, then let declarative ``drivers/*.json`` patches adapt
config to what was found (see :mod:`runtime.drivers`).

Cheap and dependency-free: ``psutil`` when present, platform fallbacks
otherwise. GPU detection is presence-of-``nvidia-smi`` only — no driver
calls, no subprocess.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MachineProfile:
    """Immutable snapshot of the facts driver patches may match on."""

    platform: str  # sys.platform: win32 | linux | darwin | ...
    ram_gb: float
    cpu_count: int
    gpu: str  # "nvidia" | "none"
    python: str  # "3.14.10"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ram_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:  # pragma: no cover - psutil is a declared dependency
        pass
    if sys.platform == "win32":  # pragma: no cover - platform specific
        import ctypes

        class _MemStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemStatus()
        status.dwLength = ctypes.sizeof(_MemStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(float(status.ullTotalPhys) / (1024**3), 1)
        return 0.0
    try:  # pragma: no cover - POSIX fallback, unreachable on Windows CI
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        return round(pages * page_size / (1024**3), 1)
    except (ValueError, OSError, AttributeError):  # pragma: no cover - POSIX-only
        return 0.0


def _gpu() -> str:
    return "nvidia" if shutil.which("nvidia-smi") else "none"


def norm_platform(plat: str) -> str:
    """Normalize ``sys.platform`` to the matchable driver vocabulary."""
    if plat.startswith("linux"):
        return "linux"
    if plat in ("win32", "cygwin"):
        return "win32"
    return plat


def detect() -> MachineProfile:
    """Probe the machine once. Never raises — unknowns degrade to 0/"none"."""
    return MachineProfile(
        platform=norm_platform(sys.platform),
        ram_gb=_ram_gb(),
        cpu_count=os.cpu_count() or 1,
        gpu=_gpu(),
        python=platform.python_version(),
    )
