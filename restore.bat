@echo off
REM aiZee — Brain Restore Launcher (Windows)
REM Modes:
REM   restore.bat              → auto-merge (smart, from checkpoint)
REM   restore.bat --from PATH  → full restore from specific backup
REM   restore.bat --list       → list available backups
REM   restore.bat --checkpoint → show current checkpoint

chcp 65001 >nul
cd /d "%~dp0"

REM --- Find Python (python -> py -> python3) ---
set "PYCMD="
for %%c in (python py python3) do (
    where %%c >nul 2>nul && (
        if not defined PYCMD set "PYCMD=%%c"
    )
)
if not defined PYCMD (
    echo [aizee] ERROR: Python not found on PATH.
    pause
    exit /b 1
)

if "%~1"=="" (
    REM Default: auto-merge mode
    %PYCMD% scripts\restore_brain.py --auto
) else (
    REM Pass arguments through
    %PYCMD% scripts\restore_brain.py %*
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [aizee] Restore exited with error code %ERRORLEVEL%
    pause
) else (
    echo.
    echo Restore complete. Press any key to close...
    pause >nul
)
