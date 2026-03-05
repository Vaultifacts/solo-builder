[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

if ($env:CLAUDE_ALLOW_WHITESPACE -eq '1') {
  Write-Host 'Whitespace guard override enabled via CLAUDE_ALLOW_WHITESPACE=1.'
  exit 0
}

$files = @(git diff --cached --name-only 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'git diff --cached failed.' }
if ($files.Count -eq 0) { exit 0 }

$violations = New-Object System.Collections.Generic.List[string]
foreach ($f in $files) {
  $raw = git diff --cached -- $f 2>$null
  $ignore = git diff --cached -w -- $f 2>$null
  if (($raw | Out-String).Trim().Length -gt 0 -and ($ignore | Out-String).Trim().Length -eq 0) {
    $violations.Add($f) | Out-Null
  }
}

if ($violations.Count -gt 0) {
  Write-Error "Whitespace-only staged changes are blocked: $($violations -join ', ')"
  exit 1
}

exit 0

