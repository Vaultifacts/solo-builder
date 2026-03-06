[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$verifyPath = Join-Path $repoRoot 'claude/VERIFY.json'
if (!(Test-Path $verifyPath)) {
  Write-Host 'No VERIFY.json found. Run pwsh tools/bootstrap_verify.ps1 first.'
  exit 0
}

$verify = Get-Content -Raw -Path $verifyPath | ConvertFrom-Json
if (-not $verify.commands -or $verify.commands.Count -eq 0) {
  Write-Host 'No verification commands configured. Run pwsh tools/bootstrap_verify.ps1 first.'
  exit 0
}

$pending = $verify.commands | Where-Object { $_.name -eq 'bootstrap-pending' -or $_.name -eq 'no-verification-detected' }
if ($pending.Count -gt 0) {
  Write-Host 'Verification not bootstrapped yet. Run pwsh tools/bootstrap_verify.ps1.'
  exit 0
}

$nameMatch = '^(npm-)?(lint|test|unit|typecheck)$'
$fast = $verify.commands | Where-Object {
  $n = [string]$_.name
  $timeout = if ($_.timeout_sec) { [int]$_.timeout_sec } else { 300 }
  $isFastName = ($n -match $nameMatch) -or ($n -match 'lint') -or ($n -match 'unit')
  $isAllowedTimeout = ($timeout -le 300)
  $isOptionalPythonUnit = (($n -match 'python') -or ($n -match 'unittest'))
  $isFastName -and $isAllowedTimeout -and (-not $isOptionalPythonUnit)
} | Select-Object -First 1

if ($fast.Count -eq 0) {
  Write-Host 'No fast subset available; skipping precommit verification.'
  exit 0
}

foreach ($cmd in $fast) {
  Write-Host "precommit_gate running: $($cmd.command)"
  cmd.exe /d /s /c $cmd.command
  if ($LASTEXITCODE -ne 0) {
    Write-Error "precommit_gate failed: $($cmd.name)"
    exit 1
  }
}

exit 0
