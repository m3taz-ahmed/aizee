@echo off
REM aiZee — Brain Backup Launcher (Windows)
REM Backs up learned data (memory/state/brain/graphify-out/.env) to a timestamped folder.

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

%PYCMD% scripts\backup_brain.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [aizee] Backup exited with error code %ERRORLEVEL%
    pause
) else (
    echo.
    echo Backup complete. Press any key to close...
    pause >nul
)
