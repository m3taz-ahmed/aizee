@echo off
REM NVENC ffmpeg shim — routes x264/x265/AV1 encodes to the NVIDIA GPU.
REM Put this directory earlier on PATH than the real ffmpeg.
REM Bypass per call: set AIZEE_FFMPEG_NVENC=0
python "%~dp0ffmpeg_nvenc_shim.py" %*
