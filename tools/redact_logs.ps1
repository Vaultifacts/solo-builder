[CmdletBinding()]
param(
  [string]$Path = 'claude/logs/latest.txt'
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$full = if ([IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path $repoRoot $Path }
if (!(Test-Path $full)) { exit 0 }

$text = Get-Content -Raw -Path $full
$text = [regex]::Replace($text, 'ghp_[A-Za-z0-9_]+', 'ghp_[REDACTED]')
$text = [regex]::Replace($text, 'github_pat_[A-Za-z0-9_]+', 'github_pat_[REDACTED]')
$text = [regex]::Replace($text, 'sk-[A-Za-z0-9_-]+', 'sk-[REDACTED]')
$text = [regex]::Replace($text, 'xox[baprs]-[A-Za-z0-9-]+', 'xox[REDACTED]')
$text = [regex]::Replace($text, '(?im)^\s*Authorization\s*:\s*Bearer\s+[^\r\n]+', 'Authorization: Bearer [REDACTED]')
$text | Set-Content -Path $full -Encoding UTF8

Write-Host "Redacted: $full"

