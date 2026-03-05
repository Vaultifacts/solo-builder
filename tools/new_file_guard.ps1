[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

if ($env:CLAUDE_ALLOW_NEW_FILES -eq '1') {
  Write-Host 'New-file guard override enabled via CLAUDE_ALLOW_NEW_FILES=1.'
  exit 0
}

$status = @(git diff --cached --name-status 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'git diff --cached --name-status failed.' }

$added = New-Object System.Collections.Generic.List[string]
foreach ($line in $status) {
  if ($line -match '^A\s+(.+)$') {
    $added.Add($Matches[1]) | Out-Null
  }
}

if ($added.Count -gt 0) {
  Write-Error "New staged files are blocked: $($added -join ', '). Set CLAUDE_ALLOW_NEW_FILES=1 to override."
  exit 1
}

exit 0

