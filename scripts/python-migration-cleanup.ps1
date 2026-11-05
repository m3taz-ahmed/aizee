#requires -RunAsAdministrator
<#
.SYNOPSIS
    Final elevated cleanup for the Python consolidation to E:\runtimes\python.

.DESCRIPTION
    Run AFTER the migration has been verified (py -0p shows E: paths and all
    venvs/MCP servers work). This script is idempotent - safe to re-run.

    Steps:
      1. Stop python.exe processes still running from the old dirs (they are
         MCP/IDE helpers; the IDE respawns them from the updated config).
      2. Update HKLM PythonCore InstallPath values -> E: paths.
      3. Remove stale python entries from the MACHINE Path.
      4. Delete old install dirs; schedule stubborn files for boot deletion.
      5. Create directory junctions at the old locations -> E: targets, so any
         hardcoded reference (shebangs, stubs, scripts) keeps working.
      6. Print post-state for review.

.NOTES
    Run elevated:
      powershell -ExecutionPolicy Bypass -File "E:\server\.ai\scripts\python-migration-cleanup.ps1"
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'

$OldToNew = [ordered]@{
    'C:\Python315'                  = 'E:\runtimes\python\3.15'
    'C:\Program Files\Python314'    = 'E:\runtimes\python\3.14'
    'C:\Program Files\Python310'    = 'E:\runtimes\python\3.10'
}
$PendingDirs = @('D:\Python315.pending-delete')
$MachinePathEntriesToRemove = @(
    'C:\Python315', 'C:\Python315\', 'C:\Python315\Scripts', 'C:\Python315\Scripts\',
    'C:\Program Files\Python310', 'C:\Program Files\Python310\',
    'C:\Program Files\Python310\Scripts', 'C:\Program Files\Python310\Scripts\'
)

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host 'ERROR: run this script elevated (Run as Administrator).' -ForegroundColor Red
    exit 1
}

Write-Host '== 1/6 Stopping python processes running from old locations ==' -ForegroundColor Cyan
$oldRoots = @($OldToNew.Keys) + $PendingDirs
Get-Process python, pythonw -ErrorAction SilentlyContinue | ForEach-Object {
    $p = $_
    if ($p.Path -and ($oldRoots | Where-Object { $p.Path.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) })) {
        Write-Host ("  stopping PID {0} [{1}]" -f $p.Id, $p.Path)
        try { $p | Stop-Process -Force -ErrorAction Stop } catch { Write-Host "    could not stop: $_" -ForegroundColor Yellow }
    }
}

Write-Host '== 2/6 Updating HKLM PythonCore registrations ==' -ForegroundColor Cyan
foreach ($entry in $OldToNew.GetEnumerator()) {
    $ver = switch ($entry.Key) {
        'C:\Python315'               { '3.15' }
        'C:\Program Files\Python314' { '3.14' }
        'C:\Program Files\Python310' { '3.10' }
    }
    $key = "HKLM:\SOFTWARE\Python\PythonCore\$ver\InstallPath"
    if (Test-Path $key) {
        Set-ItemProperty -Path $key -Name '(default)' -Value "$($entry.Value)\"
        Set-ItemProperty -Path $key -Name 'ExecutablePath' -Value "$($entry.Value)\python.exe"
        Set-ItemProperty -Path $key -Name 'WindowedExecutablePath' -Value "$($entry.Value)\pythonw.exe"
        Write-Host "  $ver -> $($entry.Value)"
    }
}

Write-Host '== 3/6 Cleaning machine PATH ==' -ForegroundColor Cyan
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$kept = ($machinePath -split ';' | Where-Object {
        $_ -and ($MachinePathEntriesToRemove -notcontains $_.TrimEnd('\')) `
           -and ($MachinePathEntriesToRemove -notcontains $_)
    })
[Environment]::SetEnvironmentVariable('Path', ($kept -join ';'), 'Machine')
Write-Host '  removed old python entries from machine Path'

Write-Host '== 4/6 Deleting old install dirs ==' -ForegroundColor Cyan
$bootDeletions = New-Object System.Collections.ArrayList
foreach ($dir in @($OldToNew.Keys) + $PendingDirs) {
    if (-not (Test-Path $dir)) { Write-Host "  already gone: $dir"; continue }
    try {
        Remove-Item $dir -Recurse -Force -ErrorAction Stop
        Write-Host "  deleted: $dir"
    } catch {
        Write-Host "  partially locked: $dir - scheduling leftovers for boot-time deletion" -ForegroundColor Yellow
        Get-ChildItem $dir -Recurse -Force -ErrorAction SilentlyContinue |
            Sort-Object { $_.FullName.Length } -Descending |
            ForEach-Object { [void]$bootDeletions.Add($_.FullName) }
        [void]$bootDeletions.Add($dir)
    }
}
if ($bootDeletions.Count -gt 0) {
    $regKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
    $existing = (Get-ItemProperty -Path $regKey -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
    $ops = @(); if ($existing) { $ops += $existing }
    foreach ($f in $bootDeletions) { $ops += "\??\$f"; $ops += '' }
    Set-ItemProperty -Path $regKey -Name PendingFileRenameOperations -Value ([string[]]$ops)
    Write-Host "  $($bootDeletions.Count) paths scheduled for deletion at next boot" -ForegroundColor Yellow
}

Write-Host '== 5/6 Creating compatibility junctions ==' -ForegroundColor Cyan
foreach ($entry in $OldToNew.GetEnumerator()) {
    if (Test-Path $entry.Key) {
        $leftover = Get-ChildItem $entry.Key -Force -ErrorAction SilentlyContinue
        if ($leftover) { Write-Host "  skipped (not empty): $($entry.Key)" -ForegroundColor Yellow; continue }
        cmd /c rmdir "$($entry.Key)" | Out-Null
    }
    New-Item -ItemType Junction -Path $entry.Key -Target $entry.Value | Out-Null
    Write-Host "  junction: $($entry.Key) -> $($entry.Value)"
}

Write-Host '== 6/6 Post-state ==' -ForegroundColor Cyan
py -0p
Write-Host ''
Write-Host 'python resolves to:' -NoNewline
(Get-Command python -All -ErrorAction SilentlyContinue | Select-Object -First 3).Source -join "`n  "
Write-Host ''
Write-Host 'Done. If any leftovers were scheduled for boot deletion, reboot once.' -ForegroundColor Green
Write-Host 'Note: python.org uninstall entries for 3.10/3.14 may remain in Add/Remove Programs - harmless; the junctions serve the files.' -ForegroundColor DarkGray
