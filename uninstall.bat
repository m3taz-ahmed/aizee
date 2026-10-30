@echo off
REM aiZee — GUI Uninstaller Launcher (Windows)
REM Launches the tkinter GUI uninstaller with selective keep/backup.
REM No terminal needed — just double-click this file.

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

REM Try GUI mode first, fall back to console if tkinter unavailable
%PYCMD% runtime\uninstaller_gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [aizee] GUI unavailable. Launching console uninstaller...
    echo.
    %PYCMD% -m aizee_cli uninstall
    pause
)
