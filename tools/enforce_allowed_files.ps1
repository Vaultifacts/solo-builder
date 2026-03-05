[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$allowedPath = Join-Path $repoRoot 'claude/allowed_files.txt'

if (!(Test-Path $allowedPath)) {
  Write-Error 'Missing claude/allowed_files.txt. Populate it before committing.'
  exit 1
}

$allowed = Get-Content -Path $allowedPath | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') }
if ($allowed.Count -eq 0) {
  Write-Error 'claude/allowed_files.txt is empty. Populate allowed paths before committing.'
  exit 1
}

$changed = @(git diff --cached --name-only 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'git diff --cached --name-only failed.' }
if ($changed.Count -eq 0) { exit 0 }

$violations = New-Object System.Collections.Generic.List[string]
foreach ($file in $changed) {
  $ok = $false
  foreach ($rule in $allowed) {
    if ($rule.Contains('*')) {
      if ($file -like $rule) { $ok = $true; break }
    } else {
      if ($file -eq $rule) { $ok = $true; break }
    }
  }
  if (-not $ok) { $violations.Add($file) | Out-Null }
}

if ($violations.Count -gt 0) {
  Write-Error "Changed files outside allowed scope: $($violations -join ', ')"
  exit 1
}

exit 0

