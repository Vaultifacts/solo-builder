[CmdletBinding()]
param(
  [string]$Image = 'repo-audit-ci'
)
$ErrorActionPreference = 'Stop'

if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host 'Docker is not installed or not on PATH.'
  exit 0
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Write-Host "Building $Image from Dockerfile.ci"
docker build -f (Join-Path $repoRoot 'Dockerfile.ci') -t $Image $repoRoot
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "Running audit in container $Image"
docker run --rm -v "${repoRoot}:/repo" -w /repo $Image pwsh tools/audit_check.ps1
exit $LASTEXITCODE

