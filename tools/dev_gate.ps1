[CmdletBinding()]
param(
  [ValidateSet('Manual', 'PreCommit')]
  [string]$Mode = 'Manual',
  [switch]$SnapshotOnFail
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$allowedPath = Join-Path $repoRoot 'claude/allowed_files.txt'

if (!(Test-Path $allowedPath)) {
  Write-Error 'Missing claude/allowed_files.txt. Run pwsh tools/extract_allowed_files.ps1 or fill manually.'
  exit 1
}
$allowed = Get-Content -Path $allowedPath | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') }
if ($allowed.Count -eq 0) {
  Write-Error 'claude/allowed_files.txt is empty. Dev gate refuses to proceed.'
  exit 1
}

$steps = @(
  'secret_scan.ps1',
  'whitespace_guard.ps1',
  'new_file_guard.ps1',
  'enforce_allowed_files.ps1',
  'no_dep_bump_guard.ps1',
  'precommit_gate.ps1',
  'context_window_warn.ps1'
)

foreach ($step in $steps) {
  $path = Join-Path $PSScriptRoot $step
  Write-Host "Running $step"
  & $path
  if ($LASTEXITCODE -ne 0) {
    if ($SnapshotOnFail) {
      try { & (Join-Path $PSScriptRoot 'claude_snapshot.ps1') -Label "dev-gate-fail-$Mode" | Out-Null } catch {}
    }
    exit $LASTEXITCODE
  }
}

exit 0

