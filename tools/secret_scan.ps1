[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

if ($env:CLAUDE_ALLOW_SECRETS -eq '1') {
  Write-Host 'Secret scan override enabled via CLAUDE_ALLOW_SECRETS=1.'
  exit 0
}

$patterns = @(
  'ghp_[A-Za-z0-9_]{10,}',
  'github_pat_[A-Za-z0-9_]{10,}',
  'sk-[A-Za-z0-9_-]{10,}',
  'xox[baprs]-[A-Za-z0-9-]{10,}',
  '(?i)Authorization\s*:\s*Bearer\s+\S+'
)

$stagedFiles = @(git diff --cached --name-only 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'git diff --cached failed. Is git configured for this repo?' }
if ($stagedFiles.Count -eq 0) { exit 0 }

$hits = New-Object System.Collections.Generic.List[string]
foreach ($file in $stagedFiles) {
  if (!(Test-Path $file)) { continue }
  $text = Get-Content -Raw -Path $file -ErrorAction SilentlyContinue
  foreach ($p in $patterns) {
    if ($text -match $p) {
      $hits.Add("$file matched pattern $p") | Out-Null
    }
  }
}

if ($hits.Count -gt 0) {
  Write-Error "Secret scan failed. Review potential secrets:`n$($hits -join \"`n\")"
  exit 1
}

exit 0

