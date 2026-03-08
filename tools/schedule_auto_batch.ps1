# schedule_auto_batch.ps1
# Registers (or updates) a Windows Task Scheduler job that runs auto_batch.py
# nightly at 02:00.
#
# Usage:
#   pwsh tools/schedule_auto_batch.ps1              # register/update the task
#   pwsh tools/schedule_auto_batch.ps1 -Remove      # remove the task
#   pwsh tools/schedule_auto_batch.ps1 -RunNow      # register + trigger immediately
#   pwsh tools/schedule_auto_batch.ps1 -WhatIf      # show config without registering
#
# The job:
#   - Runs as the current user (no password required for interactive sessions).
#   - Writes stdout+stderr to tools/auto_batch.log in the repo root.
#   - Pops a desktop MessageBox if auto_batch.py exits non-zero.
#   - Skips execution if another instance is already running (via a lock file).
#
[CmdletBinding(SupportsShouldProcess)]
param(
  [switch]$Remove,
  [switch]$RunNow,

  # How many autonomous batches to allow per nightly run (0 = unlimited).
  [int]$MaxTotal = 5,

  # Scheduled start time (24-hour HH:mm).
  [string]$StartTime = "02:00",

  # Task name in Task Scheduler.
  [string]$TaskName = "SoloBuilder_AutoBatch"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logFile  = Join-Path $repoRoot 'tools\auto_batch.log'
$lockFile = Join-Path $repoRoot 'tools\auto_batch.lock'
$python   = 'python'            # assumes python is on PATH (Python 3.13)
$script   = Join-Path $repoRoot 'tools\auto_batch.py'

# ---------------------------------------------------------------------------
# Remove mode
# ---------------------------------------------------------------------------
if ($Remove) {
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task '$TaskName' removed."
  } else {
    Write-Host "Task '$TaskName' not found -- nothing to remove."
  }
  exit 0
}

# ---------------------------------------------------------------------------
# Build the action script (inline PowerShell run via cmd.exe wrapper)
# ---------------------------------------------------------------------------
# We embed a small PS block that:
#   1. Checks for a lock file to prevent overlapping runs.
#   2. Runs auto_batch.py, tee-ing output to auto_batch.log.
#   3. Pops a MessageBox on failure.

$maxTotalArg = if ($MaxTotal -eq 0) { '--max-total 0' } else { "--max-total $MaxTotal" }

$innerScript = @"
`$lock = '$($lockFile -replace "'","''")'
`$log  = '$($logFile  -replace "'","''")'
`$py   = '$($python   -replace "'","''")'
`$scr  = '$($script   -replace "'","''")'

if (Test-Path `$lock) {
    `$pid2 = Get-Content `$lock -ErrorAction SilentlyContinue
    `$proc = Get-Process -Id `$pid2 -ErrorAction SilentlyContinue
    if (`$proc) {
        Write-Host "$(Get-Date -f 'o') auto_batch already running (PID `$pid2) -- skipping." >> `$log
        exit 0
    }
    Remove-Item `$lock -Force
}

`$PID | Set-Content `$lock

try {
    `$env:PYTHONIOENCODING = 'utf-8'
    `$ts = Get-Date -Format 'o'
    "=== auto_batch run started `$ts ===" | Add-Content `$log
    & `$py `$scr --auto-generate $maxTotalArg 2>&1 | Tee-Object -FilePath `$log -Append
    if (`$LASTEXITCODE -ne 0) {
        `$msg = "auto_batch FAILED (exit `$LASTEXITCODE) -- check `$log"
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(`$msg, 'SoloBuilder', 'OK', 'Error') | Out-Null
    }
} finally {
    Remove-Item `$lock -Force -ErrorAction SilentlyContinue
}
"@

# Encode as Base64 so Task Scheduler doesn't choke on quotes
$bytes   = [System.Text.Encoding]::Unicode.GetBytes($innerScript)
$encoded = [Convert]::ToBase64String($bytes)

$actionArgs = "-NoProfile -NonInteractive -EncodedCommand $encoded"

# ---------------------------------------------------------------------------
# WhatIf: just show what would be registered
# ---------------------------------------------------------------------------
if ($WhatIfPreference) {
  Write-Host "Task name : $TaskName"
  Write-Host "Trigger   : Daily at $StartTime"
  Write-Host "MaxTotal  : $MaxTotal"
  Write-Host "Log file  : $logFile"
  Write-Host "Lock file : $lockFile"
  Write-Host ""
  Write-Host "Inner script that would run:"
  Write-Host $innerScript
  exit 0
}

# ---------------------------------------------------------------------------
# Register the task
# ---------------------------------------------------------------------------
$action  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArgs
$trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$settings = New-ScheduledTaskSettingsSet `
  -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
  -MultipleInstances  IgnoreNew `
  -StartWhenAvailable

# Run as current user (BUILTIN\Users workaround not needed -- uses current login)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
  -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
  Set-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
  Write-Host "Task '$TaskName' updated."
} else {
  Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
  Write-Host "Task '$TaskName' registered -- runs daily at $StartTime."
}

Write-Host "Log file : $logFile"
Write-Host "Lock file: $lockFile (prevents overlapping runs)"

if ($RunNow) {
  Start-ScheduledTask -TaskName $TaskName
  Write-Host "Task triggered immediately."
}
