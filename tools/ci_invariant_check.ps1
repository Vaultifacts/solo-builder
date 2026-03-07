[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$verifyPath = Join-Path $repoRoot 'claude/VERIFY.json'
$consistencyCheck = Join-Path $PSScriptRoot 'check_next_action_consistency.ps1'

if (!(Test-Path $verifyPath)) { throw "Missing $verifyPath" }
if (!(Test-Path $consistencyCheck)) { throw "Missing $consistencyCheck" }

function Invoke-CommandWithTimeout {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [int]$TimeoutSec = 300
  )

  $stdoutFile = [IO.Path]::GetTempFileName()
  $stderrFile = [IO.Path]::GetTempFileName()
  try {
    $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/d', '/s', '/c', $Command -NoNewWindow -PassThru -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
    $timedOut = -not $proc.WaitForExit($TimeoutSec * 1000)
    if ($timedOut) {
      try { $proc.Kill() } catch {}
    }
    return [pscustomobject]@{
      exit_code = if ($timedOut) { 124 } else { $proc.ExitCode }
      timed_out = $timedOut
      stdout = if (Test-Path $stdoutFile) { Get-Content -Raw -Path $stdoutFile } else { '' }
      stderr = if (Test-Path $stderrFile) { Get-Content -Raw -Path $stderrFile } else { '' }
    }
  } finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $stdoutFile, $stderrFile
  }
}

# Required invariant: rendered contract must match machine state.
& $consistencyCheck
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$verify = Get-Content -Raw -Path $verifyPath | ConvertFrom-Json
$results = New-Object System.Collections.Generic.List[object]
$requiredFailures = 0

foreach ($cmd in $verify.commands) {
  $timeoutSec = if ($cmd.timeout_sec) { [int]$cmd.timeout_sec } else { 300 }
  Write-Host "Running: $($cmd.name)"
  $run = Invoke-CommandWithTimeout -Command $cmd.command -TimeoutSec $timeoutSec
  $passed = (-not $run.timed_out) -and ($run.exit_code -eq 0)
  $required = [bool]$cmd.required
  if ($required -and (-not $passed)) { $requiredFailures++ }

  $results.Add([pscustomobject]@{
    name = $cmd.name
    command = $cmd.command
    required = $required
    timeout_sec = $timeoutSec
    passed = $passed
    exit_code = $run.exit_code
    timed_out = $run.timed_out
    stdout = $run.stdout
    stderr = $run.stderr
  }) | Out-Null
}

if ($requiredFailures -gt 0) {
  Write-Error "$requiredFailures required verification command(s) failed."
  exit 1
}

Write-Host "ci_invariant_check: PASS"
exit 0
