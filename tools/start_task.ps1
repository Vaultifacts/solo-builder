[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^TASK-\d{3}$')]
  [string]$TaskId,

  [string]$Goal = '<define task goal>',

  [switch]$NoPull,
  [switch]$NoCommit,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskQueuePath = Join-Path $repoRoot 'claude/TASK_QUEUE.md'
$taskActivePath = Join-Path $repoRoot 'claude/TASK_ACTIVE.md'
$journalPath = Join-Path $repoRoot 'claude/JOURNAL.md'
$statePath = Join-Path $repoRoot 'claude/STATE.json'
$orchestratePath = Join-Path $PSScriptRoot 'claude_orchestrate.ps1'
$preflightPath = Join-Path $PSScriptRoot 'workflow_preflight.ps1'

function Invoke-Git {
  param([Parameter(Mandatory = $true)][string[]]$Args)
  & git @Args
  if ($LASTEXITCODE -ne 0) {
    throw "git command failed: git $($Args -join ' ')"
  }
}

function Get-CurrentBranch {
  $branch = (& git branch --show-current).Trim()
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
    throw 'Unable to determine current branch.'
  }
  return $branch
}

function Get-DirtyPaths {
  $lines = @(& git status --porcelain)
  if ($LASTEXITCODE -ne 0) { throw 'git status --porcelain failed.' }
  $paths = New-Object System.Collections.Generic.List[string]
  foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line.Length -lt 4) { continue }
    $path = $line.Substring(3).Trim()
    if ($path -match ' -> ') { $path = ($path -split ' -> ')[1].Trim() }
    if ($path -and ($paths -notcontains $path)) { $paths.Add($path) | Out-Null }
  }
  return @($paths)
}

function Test-BranchExists {
  param([Parameter(Mandatory = $true)][string]$Branch)
  & git show-ref --verify --quiet "refs/heads/$Branch"
  return ($LASTEXITCODE -eq 0)
}

if (!(Test-Path $preflightPath)) { throw "Missing $preflightPath" }
if (!(Test-Path $orchestratePath)) { throw "Missing $orchestratePath" }
if (!(Test-Path $taskQueuePath)) { throw "Missing $taskQueuePath" }
if (!(Test-Path $taskActivePath)) { throw "Missing $taskActivePath" }
if (!(Test-Path $journalPath)) { throw "Missing $journalPath" }
if (!(Test-Path $statePath)) { throw "Missing $statePath" }

$startBranch = Get-CurrentBranch
$dirty = Get-DirtyPaths
if ($dirty.Count -gt 0) {
  throw "Working tree is not clean: $($dirty -join ', ')"
}

$targetBranch = "task/$TaskId"
if (Test-BranchExists -Branch $targetBranch) {
  throw "Target branch already exists: $targetBranch"
}

$previousBranch = $null
if ($startBranch -match '^task/TASK-\d+$') {
  $previousBranch = $startBranch
}

if ($DryRun) {
  Write-Host "[DRY-RUN] Step 1: verify clean working tree (PASS)"
  Write-Host "[DRY-RUN] Step 2: switch to master"
  Write-Host "[DRY-RUN] Step 3: optional pull (skip when no upstream or -NoPull)"
  if ($previousBranch) {
    Write-Host "[DRY-RUN] Step 4: merge previous branch into master if needed: $previousBranch"
  } else {
    Write-Host "[DRY-RUN] Step 4: no previous task branch detected from current branch"
  }
  Write-Host "[DRY-RUN] Step 5: run workflow preflight BEFORE creating $targetBranch"
  & $preflightPath
  if ($LASTEXITCODE -ne 0) {
    throw '[DRY-RUN] Preflight failed; initialization aborted before branch creation.'
  }
  Write-Host "[DRY-RUN] Step 6: create branch $targetBranch"
  Write-Host "[DRY-RUN] Step 7: update TASK_QUEUE/TASK_ACTIVE/STATE/JOURNAL"
  Write-Host "[DRY-RUN] Step 8: run orchestrator"
  if (-not $NoCommit) {
    Write-Host "[DRY-RUN] Step 9: commit initialization metadata"
  }
  exit 0
}

Invoke-Git -Args @('checkout', 'master')

if (-not $NoPull) {
  & git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Invoke-Git -Args @('pull')
  } else {
    Write-Host 'No upstream configured on master; skipping pull.'
  }
}

if ($previousBranch -and (Test-BranchExists -Branch $previousBranch)) {
  & git merge-base --is-ancestor $previousBranch master
  if ($LASTEXITCODE -ne 0) {
    Invoke-Git -Args @('merge', '--no-ff', $previousBranch)
  } else {
    Write-Host "Previous branch already merged into master: $previousBranch"
  }
}

& $preflightPath
if ($LASTEXITCODE -ne 0) {
  throw "Preflight failed; initialization aborted before creating $targetBranch."
}

Invoke-Git -Args @('checkout', '-b', $targetBranch)

$queueText = Get-Content -Raw -Path $taskQueuePath
if ($queueText -notmatch "(?m)^##\s+$([regex]::Escape($TaskId))\s*$") {
  $block = @"

## $TaskId
Goal: $Goal

Acceptance criteria:
- <define criterion 1>
- <define criterion 2>

Constraints:
- Keep scope narrow
- Do not modify product code unless explicitly required
- Preserve deterministic workflow conventions
"@
  Add-Content -Path $taskQueuePath -Value $block
}

@"
# Active Task

$TaskId

$Goal
"@ | Set-Content -Path $taskActivePath

$state = Get-Content -Raw -Path $statePath | ConvertFrom-Json
$state.task_id = $TaskId
$state.phase = 'triage'
$state.next_role = 'RESEARCH'
$state.attempt = 0
$state.updated_at = [DateTime]::UtcNow.ToString('o')
$state | ConvertTo-Json -Depth 10 | Set-Content -Path $statePath -Encoding UTF8

$ts = [DateTime]::UtcNow.ToString('o')
Add-Content -Path $journalPath -Value "- [$ts] Starting $TaskId via tools/start_task.ps1 with automated preflight gating."

& $orchestratePath
if ($LASTEXITCODE -ne 0) {
  throw 'claude_orchestrate.ps1 failed during initialization.'
}

if (-not $NoCommit) {
  Invoke-Git -Args @('add', 'claude/TASK_QUEUE.md', 'claude/TASK_ACTIVE.md', 'claude/JOURNAL.md')
  Invoke-Git -Args @('commit', '-m', "chore: initialize $TaskId")
}

Write-Host "start_task complete for $TaskId on branch $targetBranch"
