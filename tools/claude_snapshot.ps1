[CmdletBinding()]
param(
  [string]$Label = 'manual'
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$claudeDir = Join-Path $repoRoot 'claude'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$safeLabel = ($Label -replace '[^a-zA-Z0-9_-]', '-')
$target = Join-Path $claudeDir ("snapshots/$stamp-$safeLabel")
New-Item -ItemType Directory -Path $target -Force | Out-Null

function Save-Cmd {
  param([string]$Name, [string]$Cmd)
  $out = Join-Path $target "$Name.txt"
  try {
    (cmd.exe /d /s /c $Cmd 2>&1 | Out-String) | Set-Content -Path $out -Encoding UTF8
  } catch {
    "ERROR: $($_.Exception.Message)" | Set-Content -Path $out -Encoding UTF8
  }
}

Save-Cmd -Name 'git-status' -Cmd 'git status --short --branch'
Save-Cmd -Name 'git-diff' -Cmd 'git diff'
Save-Cmd -Name 'git-diff-stat' -Cmd 'git diff --stat'
Save-Cmd -Name 'git-log' -Cmd 'git log --oneline -n 10'
Save-Cmd -Name 'git-changed-files' -Cmd 'git diff --name-only'

foreach ($f in @(
  'claude/HANDOFF_RESEARCH.md',
  'claude/HANDOFF_ARCHITECT.md',
  'claude/HANDOFF_DEV.md',
  'claude/HANDOFF_AUDIT.md',
  'claude/STATE.json',
  'claude/verify_last.json',
  'claude/VERIFY.json'
)) {
  $src = Join-Path $repoRoot $f
  if (Test-Path $src) {
    Copy-Item -Path $src -Destination (Join-Path $target ([IO.Path]::GetFileName($src))) -Force
  }
}

$statePath = Join-Path $claudeDir 'STATE.json'
if (Test-Path $statePath) {
  $state = Get-Content -Raw -Path $statePath | ConvertFrom-Json
  $state.last_snapshot_path = $target
  $state.updated_at = [DateTime]::UtcNow.ToString('o')
  $state | ConvertTo-Json -Depth 8 | Set-Content -Path $statePath -Encoding UTF8
}

Write-Host $target

