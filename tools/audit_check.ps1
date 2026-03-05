[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$claudeDir = Join-Path $repoRoot 'claude'
$verifyPath = Join-Path $claudeDir 'VERIFY.json'
$resultPath = Join-Path $claudeDir 'verify_last.json'
$statePath = Join-Path $claudeDir 'STATE.json'

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
    if ($timedOut) { try { $proc.Kill() } catch {} }
    [pscustomobject]@{
      exit_code = if ($timedOut) { 124 } else { $proc.ExitCode }
      timed_out = $timedOut
      stdout = if (Test-Path $stdoutFile) { Get-Content -Raw -Path $stdoutFile } else { '' }
      stderr = if (Test-Path $stderrFile) { Get-Content -Raw -Path $stderrFile } else { '' }
    }
  } finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $stdoutFile, $stderrFile
  }
}

if (!(Test-Path $verifyPath)) { throw "Missing $verifyPath" }
if (!(Test-Path $statePath)) { throw "Missing $statePath" }

$verify = Get-Content -Raw -Path $verifyPath | ConvertFrom-Json
$results = New-Object System.Collections.Generic.List[object]
$requiredFailures = 0

foreach ($cmd in $verify.commands) {
  $timeoutSec = if ($cmd.timeout_sec) { [int]$cmd.timeout_sec } else { 300 }
  Write-Host "Running: $($cmd.name)"
  $run = Invoke-CommandWithTimeout -Command $cmd.command -TimeoutSec $timeoutSec
  $passed = (-not $run.timed_out) -and ($run.exit_code -eq 0)
  if (($cmd.required -eq $true) -and (-not $passed)) { $requiredFailures++ }
  $results.Add([pscustomobject]@{
    name = $cmd.name
    command = $cmd.command
    required = [bool]$cmd.required
    timeout_sec = $timeoutSec
    passed = $passed
    exit_code = $run.exit_code
    timed_out = $run.timed_out
    stdout = $run.stdout
    stderr = $run.stderr
  }) | Out-Null
}

$passedAll = ($requiredFailures -eq 0)
$message = if ($passedAll) { 'All required verification commands passed.' } else { "$requiredFailures required command(s) failed." }

[pscustomobject]@{
  generated_at = [DateTime]::UtcNow.ToString('o')
  passed = $passedAll
  message = $message
  results = $results
} | ConvertTo-Json -Depth 12 | Set-Content -Path $resultPath -Encoding UTF8

$state = Get-Content -Raw -Path $statePath | ConvertFrom-Json
if ($passedAll) {
  $state.last_verify_pass = $true
  $state.phase = 'done'
} else {
  $state.last_verify_pass = $false
  $state.attempt = [int]$state.attempt + 1
  $state.phase = 'verify'
  $state.next_role = 'ARCHITECT'
}
$state.updated_at = [DateTime]::UtcNow.ToString('o')
$state | ConvertTo-Json -Depth 8 | Set-Content -Path $statePath -Encoding UTF8

if (-not $passedAll) {
  try { & (Join-Path $PSScriptRoot 'claude_snapshot.ps1') -Label 'verify-fail' | Out-Null } catch {}
  Write-Error $message
  exit 1
}

Write-Host $message
exit 0

