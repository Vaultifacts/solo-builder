[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$statePath = Join-Path $repoRoot 'claude/STATE.json'
$ciPath = Join-Path $repoRoot 'claude/ci_context.json'

if (!(Test-Path $statePath)) { throw "Missing $statePath" }
Write-Host 'STATE:'
(Get-Content -Raw -Path $statePath | ConvertFrom-Json | ConvertTo-Json -Depth 8) | Write-Host

Write-Host ''
if (Test-Path $ciPath) {
  Write-Host 'CI CONTEXT:'
  (Get-Content -Raw -Path $ciPath | ConvertFrom-Json | ConvertTo-Json -Depth 8) | Write-Host
} else {
  Write-Host 'CI CONTEXT: none'
}

