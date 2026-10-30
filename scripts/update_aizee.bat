@echo off
REM === aiZee Sync Script: .ai -> aizee ===
REM Mirrors the working directory (.ai) into the deployment folder (aizee).
REM Usage: scripts\update_aizee.bat
REM
REM [DIR-01] .ai is the ONLY working directory. aizee is READ-ONLY except via this script.
REM
REM robocopy /MIR = exact mirror: new files copied, changed files updated,
REM files retired from .ai are DELETED from aizee (stale-path cleanup).
REM Exclusion lists below keep runtime state, secrets, and regenerable output out.

setlocal enabledelayedexpansion

REM Derive paths relative to this script's location (portable across machines).
REM Source = parent of scripts/ dir (the .ai working directory).
REM Target = sibling "aizee" deployment folder (override via AIZEE_DEPLOY env if needed).
set "SOURCE=%~dp0.."
if defined AIZEE_DEPLOY (set "TARGET=%AIZEE_DEPLOY%") else (set "TARGET=%~dp0..\..\aizee")

echo === aiZee Sync: %SOURCE% -^> %TARGET% ===

if not exist "%TARGET%" (
    echo ERROR: Target directory %TARGET% does not exist.
    pause
    exit /b 1
)

REM Self-mirror guard: if this copy lives inside the deployment folder,
REM SOURCE resolves to the target itself and /MIR would be a no-op.
for %%I in ("%SOURCE%") do set "SRCNORM=%%~fI"
for %%I in ("%TARGET%") do set "TGTNORM=%%~fI"
if /I "%SRCNORM%"=="%TGTNORM%" (
    echo This script syncs the .ai working directory into the aizee deployment folder.
    echo You are running the DEPLOYMENT copy - run it from .ai\scripts\ instead.
    pause
    exit /b 1
)

REM Safety: /MIR deletes extra files in TARGET. Refuse to run unless TARGET
REM looks like an aiZee deployment (has the package markers).
if not exist "%TARGET%\pyproject.toml" (
    echo ERROR: %TARGET% has no pyproject.toml - refusing to mirror into a non-aiZee dir.
    pause
    exit /b 1
)
if not exist "%TARGET%\config.py" (
    echo ERROR: %TARGET% has no config.py - refusing to mirror into a non-aiZee dir.
    pause
    exit /b 1
)

REM --- Mirror pass: everything except the excluded dirs/files below. ---
REM Excluded dirs: VCS internals, runtime/learned state, regenerable output.
REM Excluded files: secrets, generated configs, local overrides, scratch notes.

robocopy "%SOURCE%" "%TARGET%" /MIR /R:2 /W:2 /NFL /NDL /NP /NJH ^
    /XD .git .ai temp state brain backups graphify-out htmlcov .mypy_cache .pytest_cache .ruff_cache __pycache__ node_modules .venv venv abstracts .idea .claude .devin ^
    /XF .env .coverage *.pyc *.pyo *.log .aizee-version settings.json settings.local.json mcp_config.local.json config.local.json notes-*.md implementation_plan.md DEEP_AUDIT_PROMPT.md GRAPH_REPORT.md
set "RC1=%ERRORLEVEL%"

REM --- .claude pass: configs/skills, minus machine-generated settings.json ---
robocopy "%SOURCE%\.claude" "%TARGET%\.claude" /MIR /R:2 /W:2 /NFL /NDL /NP /NJH ^
    /XD __pycache__ ^
    /XF settings.json settings.local.json *.pyc *.pyo
set "RC2=%ERRORLEVEL%"

REM --- .devin pass: skills/config, minus local override files ---
robocopy "%SOURCE%\.devin" "%TARGET%\.devin" /MIR /R:2 /W:2 /NFL /NDL /NP /NJH ^
    /XD __pycache__ ^
    /XF mcp_config.local.json config.local.json *.pyc *.pyo
set "RC3=%ERRORLEVEL%"

REM robocopy success = exit code < 8 (0 nothing, 1 copied, 2+ extras/mismatches).
if %RC1% GEQ 8 ( echo ERROR: main mirror failed ^(robocopy %RC1%^) & pause & exit /b %RC1% )
if %RC2% GEQ 8 ( echo ERROR: .claude mirror failed ^(robocopy %RC2%^) & pause & exit /b %RC2% )
if %RC3% GEQ 8 ( echo ERROR: .devin mirror failed ^(robocopy %RC3%^) & pause & exit /b %RC3% )

echo.
echo === Sync Complete ===
echo Verify with: cd %TARGET% ^&^& python eval\harness.py
echo.
pause
endlocal
exit /b 0
