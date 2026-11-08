#!/usr/bin/env python3
"""NVENC ffmpeg shim — route software x264/x265/AV1 encodes to the NVIDIA GPU.

Put this directory (``scripts/gpu-bin``) earlier on PATH than the real
ffmpeg: every ``ffmpeg -c:v libx264 …`` call then lands here, gets its
encoder arguments rewritten to ``*_nvenc``, and is forwarded to the real
ffmpeg binary (located by scanning PATH while skipping this directory).

Graceful by default: when the real ffmpeg has no ``*_nvenc`` encoders (no
NVIDIA GPU, or a slim ffmpeg build), args pass through untouched — the CPU
path works exactly as if the shim were absent. ``AIZEE_FFMPEG_NVENC=0``
forces passthrough; ``=1`` forces translation (lets the real ffmpeg error
if it lacks encoders); unset = auto-detect per invocation.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ENCODER_MAP = {
    "libx264": "h264_nvenc",
    "libx265": "hevc_nvenc",
    "libsvtav1": "av1_nvenc",
    "librav1e": "av1_nvenc",
    "libaom-av1": "av1_nvenc",
}
NVENC_PRESETS = {f"p{i}" for i in range(1, 8)}
NVENC_TUNES = {"hq", "ll", "ull", "lossless"}
DISABLE_ENV = "AIZEE_FFMPEG_NVENC"


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _real_ffmpeg() -> str | None:
    """First ffmpeg on PATH that is not this shim's own directory."""
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        try:
            if Path(entry).resolve() == _script_dir():
                continue
        except OSError:
            continue
        for name in ("ffmpeg.exe", "ffmpeg"):
            cand = Path(entry) / name
            if cand.is_file():
                return str(cand)
    return None


def _map_preset(value: str) -> str:
    if value in NVENC_PRESETS:
        return value
    if value in {"slow", "slower", "veryslow", "placebo"}:
        return "p6"
    if value == "medium":
        return "p4"
    return "p3"  # ultrafast..fast and unknown → quick default


def _rewrite_pair(argv: list[str], i: int, out: list[str]) -> int:
    """Handle one flag that consumes a value; return consumed argv count."""
    a, nxt = argv[i], argv[i + 1]
    if a == "-crf":
        out.extend(["-cq", nxt])
    elif a == "-preset":
        out.extend([a, _map_preset(nxt)])
    elif a == "-tune":
        if nxt in NVENC_TUNES:
            out.extend([a, nxt])
    elif a in ("-x264-params", "-x265-params"):
        pass
    else:
        out.extend([a, nxt])
    return 2


def _translate(argv: list[str]) -> list[str]:
    out: list[str] = []
    encoder = ""
    have_bitrate = any(a in ("-b:v", "-maxrate") for a in argv)
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-c:v", "-codec:v", "-vcodec") and i + 1 < len(argv):
            mapped = ENCODER_MAP.get(argv[i + 1], argv[i + 1])
            if mapped != argv[i + 1]:
                encoder = mapped
            out.extend([a, mapped])
            i += 2
            continue
        if i + 1 < len(argv) and a in ("-crf", "-preset", "-tune", "-x264-params", "-x265-params", "-profile:v"):
            if a == "-profile:v" and encoder != "av1_nvenc":
                out.extend([a, argv[i + 1]])
            elif a != "-profile:v":
                i += _rewrite_pair(argv, i, out) - 2
            i += 2
            continue
        out.append(a)
        i += 1
    if encoder and not have_bitrate:
        out += ["-b:v", "0"]
    return out


def _nvenc_available(real: str) -> bool:
    """True when the real ffmpeg reports NVIDIA encoders — else CPU passthrough."""
    try:
        proc = subprocess.run(
            [real, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "nvenc" in proc.stdout


def main() -> int:
    real = _real_ffmpeg()
    if not real:
        sys.stderr.write("nvenc-shim: real ffmpeg not found on PATH\n")
        return 127
    argv = sys.argv[1:]
    forced = os.environ.get(DISABLE_ENV, "")
    if forced == "0" or (forced != "1" and not _nvenc_available(real)):
        return subprocess.call([real, *argv])
    return subprocess.call([real, *_translate(argv)])


if __name__ == "__main__":
    raise SystemExit(main())
