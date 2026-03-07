[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$consistencyCheck = Join-Path $PSScriptRoot 'check_next_action_consistency.ps1'
$runtimeArtifacts = @(
  'claude/allowed_files.txt',
  'claude/verify_last.json'
)

function Get-ChangedPaths {
  $lines = @(git status --porcelain 2>$null)
  if ($LASTEXITCODE -ne 0) { throw 'git status --porcelain failed.' }

  $paths = New-Object System.Collections.Generic.List[string]
  foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line.Length -lt 4) { continue }

    $path = $line.Substring(3).Trim()
    if ($path -match ' -> ') {
      $path = ($path -split ' -> ')[1].Trim()
    }
    if ($path -and ($paths -notcontains $path)) {
      $paths.Add($path) | Out-Null
    }
  }
  return @($paths)
}

function Fail([string]$Message) {
  Write-Error $Message
  exit 1
}

if (!(Test-Path $consistencyCheck)) {
  Fail "Missing required helper: $consistencyCheck"
}

$branch = (git branch --show-current 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
  Fail 'Unable to determine current branch (detached HEAD is not allowed for preflight).'
}

$changedPaths = Get-ChangedPaths
$dirtyRuntime = @($changedPaths | Where-Object { $runtimeArtifacts -contains $_ })
if ($dirtyRuntime.Count -gt 0) {
  $list = $dirtyRuntime -join ', '
  Fail "Runtime artifacts are dirty: $list`nRemediation: git restore --source=HEAD --worktree --staged claude/allowed_files.txt claude/verify_last.json"
}

if ($changedPaths.Count -gt 0) {
  $list = $changedPaths -join ', '
  Fail "Working tree is not clean on branch '$branch': $list`nRemediation: commit/stash/restore changes before initializing a new task."
}

& $consistencyCheck
if ($LASTEXITCODE -ne 0) {
  Fail 'STATE/NEXT_ACTION consistency check failed. Remediation: run pwsh tools/claude_orchestrate.ps1 and resolve state drift.'
}

if ($branch -eq 'master') {
  Write-Host 'Baseline check: running on master; branch ancestry condition satisfied.'
} elseif ($branch -match '^task/TASK-(\d+)$') {
  $currentNum = [int]$Matches[1]
  if ($currentNum -gt 1) {
    $prevNum = $currentNum - 1
    $prevBranch = ('task/TASK-{0}' -f $prevNum.ToString('000'))

    git show-ref --verify --quiet "refs/heads/$prevBranch"
    if ($LASTEXITCODE -eq 0) {
      git merge-base --is-ancestor $prevBranch master
      if ($LASTEXITCODE -ne 0) {
        Fail "Unsafe baseline: master does not contain $prevBranch.`nRemediation: git checkout master && git merge --no-ff $prevBranch"
      }
      Write-Host "Baseline check passed: master contains $prevBranch."
    } else {
      Write-Host "Baseline check: previous branch $prevBranch not found locally; conservative merge check skipped."
    }
  } else {
    Write-Host 'Baseline check: TASK number <= 1; previous-branch merge check skipped.'
  }
} else {
  Fail "Unsupported branch '$branch' for preflight. Use master or task/TASK-### branches."
}

Write-Host "workflow_preflight: PASS (branch=$branch)"
exit 0
