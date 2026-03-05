[CmdletBinding()]
param(
  [ValidateSet('Acquire', 'Release', 'Status')]
  [string]$Action = 'Status'
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$lockPath = Join-Path $repoRoot 'claude/TASK_ACTIVE.lock'

switch ($Action) {
  'Acquire' {
    if (Test-Path $lockPath) {
      Write-Error "Lock already held: $lockPath"
      exit 1
    }
    [pscustomobject]@{
      user = $env:USERNAME
      host = $env:COMPUTERNAME
      pid = $PID
      acquired_at = [DateTime]::UtcNow.ToString('o')
    } | ConvertTo-Json -Depth 5 | Set-Content -Path $lockPath -Encoding UTF8
    Write-Host 'Lock acquired.'
  }
  'Release' {
    if (Test-Path $lockPath) {
      Remove-Item -Force $lockPath
      Write-Host 'Lock released.'
    } else {
      Write-Host 'No lock present.'
    }
  }
  'Status' {
    if (Test-Path $lockPath) {
      Get-Content -Raw -Path $lockPath | Write-Host
      exit 1
    }
    Write-Host 'Lock free.'
  }
}

