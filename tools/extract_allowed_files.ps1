[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$handoff = Join-Path $repoRoot 'claude/HANDOFF_DEV.md'
$allowedPath = Join-Path $repoRoot 'claude/allowed_files.txt'

if (!(Test-Path $handoff)) {
  Write-Error 'Missing claude/HANDOFF_DEV.md'
  exit 1
}

$lines = Get-Content -Path $handoff
$inAllowed = $false
$paths = New-Object System.Collections.Generic.List[string]

# Supported section-start aliases (intentionally bounded; no free-form matching)
$startPattern = '^\s*(?:##\s*)?(?:Allowed\s+changes|Allowed\s+files(?:\s+to\s+modify)?)\s*:?\s*$'
# Section-end markers to avoid over-capturing bullets from unrelated sections
$endPattern = '^\s*(?:##\s+|Disallowed\s+changes|Implementation\s+plan|Acceptance\s+criteria|Verification\s+steps|Risks|Files\s+that\s+must\s+not\s+be\s+modified)\b'

foreach ($line in $lines) {
  if ($line -imatch $startPattern) { $inAllowed = $true; continue }
  if ($inAllowed -and $line -imatch $endPattern) { break }
  if ($inAllowed -and $line -match '^\s*-\s+(.+)$') {
    $candidate = $Matches[1].Trim()
    if ($candidate) { $paths.Add($candidate) | Out-Null }
  }
}

if ($paths.Count -eq 0) {
  Set-Content -Path $allowedPath -Value '' -Encoding UTF8
  Write-Host 'No paths found in HANDOFF_DEV.md Allowed changes section. Fill claude/allowed_files.txt manually.'
  exit 1
}

$paths | Set-Content -Path $allowedPath -Encoding UTF8
Write-Host "Wrote $allowedPath"
