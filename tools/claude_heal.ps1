[CmdletBinding()]
param(
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$claudeDir = Join-Path $repoRoot 'claude'
$statePath = Join-Path $claudeDir 'STATE.json'
$queuePath = Join-Path $claudeDir 'TASK_QUEUE.md'
$ciPath = Join-Path $claudeDir 'ci_context.json'
$logPath = Join-Path $claudeDir 'logs/latest.txt'

if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
  Write-Host 'GitHub CLI (gh) is not installed. Install/authenticate gh and rerun tools/claude_heal.ps1.'
  exit 0
}

$runListJson = gh run list --limit 30 --json databaseId,conclusion,status,workflowName,displayTitle,headBranch,createdAt 2>$null
if (-not $runListJson) { throw 'Unable to query workflow runs via gh.' }
$runs = $runListJson | ConvertFrom-Json
$failed = $runs | Where-Object { $_.conclusion -eq 'failure' } | Select-Object -First 1
if (-not $failed) {
  Write-Host 'No failed runs found.'
  exit 0
}

$runId = [string]$failed.databaseId

if ($DryRun) {
  Write-Host "[DRY-RUN] Would triage run $runId | workflow: $($failed.workflowName) | branch: $($failed.headBranch) | title: $($failed.displayTitle)"
  Write-Host "[DRY-RUN] Would download artifacts to claude/artifacts/$runId"
  Write-Host "[DRY-RUN] Would reset STATE.json to triage/RESEARCH with run_id=$runId"
  Write-Host "[DRY-RUN] No files modified."
  exit 0
}

$artifactDir = Join-Path $claudeDir ("artifacts/$runId")
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
gh run download $runId -D $artifactDir | Out-Null

[pscustomobject]@{
  run_id = $runId
  workflow = $failed.workflowName
  title = $failed.displayTitle
  branch = $failed.headBranch
  created_at = $failed.createdAt
  downloaded_at = [DateTime]::UtcNow.ToString('o')
} | ConvertTo-Json -Depth 6 | Set-Content -Path $ciPath -Encoding UTF8

try {
  $logText = gh run view $runId --log 2>$null
  if ($logText) {
    $logText | Set-Content -Path $logPath -Encoding UTF8
    & (Join-Path $PSScriptRoot 'redact_logs.ps1') -Path $logPath | Out-Null
  }
} catch {
  Write-Warning "Unable to fetch logs for run $runId."
}

$stamp = [DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm:ssZ')
Add-Content -Path $queuePath -Value "- [$stamp] Triage failed CI run $runId ($($failed.workflowName))."

$state = Get-Content -Raw -Path $statePath | ConvertFrom-Json
$state.phase = 'triage'
$state.next_role = 'RESEARCH'
$state.run_id = $runId
$state.attempt = 0
$state.updated_at = [DateTime]::UtcNow.ToString('o')
$state | ConvertTo-Json -Depth 8 | Set-Content -Path $statePath -Encoding UTF8

Write-Host "Prepared triage context for run $runId."

