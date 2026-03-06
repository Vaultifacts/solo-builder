[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$statePath = Join-Path $repoRoot 'claude/STATE.json'
$nextActionPath = Join-Path $repoRoot 'claude/NEXT_ACTION.md'

if (!(Test-Path $statePath)) { throw "Missing $statePath" }
if (!(Test-Path $nextActionPath)) { throw "Missing $nextActionPath" }

function Get-NextActionField {
  param(
    [Parameter(Mandatory = $true)][string]$Text,
    [Parameter(Mandatory = $true)][string]$Heading
  )

  $pattern = "(?ms)^\s*##\s+$([regex]::Escape($Heading))\s*\r?\n(.+?)(?=^\s*##\s+|\z)"
  $m = [regex]::Match($Text, $pattern)
  if (!$m.Success) {
    throw "NEXT_ACTION.md missing section '## $Heading'."
  }
  return $m.Groups[1].Value.Trim()
}

$state = Get-Content -Raw -Path $statePath | ConvertFrom-Json
$nextAction = Get-Content -Raw -Path $nextActionPath

$actualTask = Get-NextActionField -Text $nextAction -Heading 'Task'
$actualPhase = Get-NextActionField -Text $nextAction -Heading 'Phase'
$actualRole = Get-NextActionField -Text $nextAction -Heading 'Role'

$expectedTask = ([string]$state.task_id).Trim()
$expectedPhase = ([string]$state.phase).Trim()
$expectedRole = ([string]$state.next_role).Trim()

$mismatches = New-Object System.Collections.Generic.List[string]
if ($expectedTask -ne $actualTask) {
  $mismatches.Add("Task mismatch: STATE.task_id='$expectedTask' vs NEXT_ACTION.Task='$actualTask'") | Out-Null
}
if ($expectedPhase -ne $actualPhase) {
  $mismatches.Add("Phase mismatch: STATE.phase='$expectedPhase' vs NEXT_ACTION.Phase='$actualPhase'") | Out-Null
}
if ($expectedRole -ne $actualRole) {
  $mismatches.Add("Role mismatch: STATE.next_role='$expectedRole' vs NEXT_ACTION.Role='$actualRole'") | Out-Null
}

if ($mismatches.Count -gt 0) {
  Write-Error ("STATE/NEXT_ACTION consistency check failed:`n- " + ($mismatches -join "`n- "))
  exit 1
}

Write-Host "STATE/NEXT_ACTION consistency check passed."
Write-Host "Task=$actualTask Phase=$actualPhase Role=$actualRole"
exit 0
