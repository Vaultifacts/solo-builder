[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

git config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
  Write-Error 'Failed to set core.hooksPath. Ensure git is available and repository is trusted.'
  exit 1
}

Write-Host 'Configured git hooks path to .githooks'
exit 0

