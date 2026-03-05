[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

if ($env:CLAUDE_ALLOW_DEP_BUMP -eq '1') {
  Write-Host 'Dependency bump guard override enabled via CLAUDE_ALLOW_DEP_BUMP=1.'
  exit 0
}

$lockFiles = @(
  'package-lock.json',
  'yarn.lock',
  'pnpm-lock.yaml',
  'bun.lockb',
  'poetry.lock',
  'Pipfile.lock'
)

$changed = @(git diff --cached --name-only 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'git diff --cached --name-only failed.' }

$hits = New-Object System.Collections.Generic.List[string]
foreach ($f in $changed) {
  if ($lockFiles -contains $f) { $hits.Add($f) | Out-Null }
}

if ($hits.Count -gt 0) {
  Write-Error "Lockfile changes are blocked: $($hits -join ', '). Set CLAUDE_ALLOW_DEP_BUMP=1 to override."
  exit 1
}

exit 0

