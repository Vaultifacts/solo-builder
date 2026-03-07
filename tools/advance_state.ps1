[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('triage', 'research', 'plan', 'build', 'verify', 'done')]
  [string]$ToPhase,

  [Parameter(Mandatory = $true)]
  [ValidateSet('RESEARCH', 'ARCHITECT', 'DEV', 'AUDITOR')]
  [string]$ToRole,

  [string]$TaskId,
  [string]$RunId,
  [string]$Note
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$statePath = Join-Path $repoRoot 'claude/STATE.json'
$journalPath = Join-Path $repoRoot 'claude/JOURNAL.md'
$schemaPath = Join-Path $repoRoot 'claude/STATE_SCHEMA.md'

if (!(Test-Path $statePath)) { throw "Missing $statePath" }
if (!(Test-Path $schemaPath)) { throw "Missing $schemaPath" }

$state = Get-Content -Raw -Path $statePath | ConvertFrom-Json

# Keep validation mapping aligned with tools/claude_orchestrate.ps1.
$phaseRoleMap = @{
  triage = 'RESEARCH'
  research = 'ARCHITECT'
  plan = 'DEV'
  build = 'DEV'
  verify = 'AUDITOR'
}
if ($ToPhase -ne 'done' -and $phaseRoleMap[$ToPhase] -ne $ToRole) {
  throw "Requested transition invalid for phase '$ToPhase'. Expected role '$($phaseRoleMap[$ToPhase])'."
}

$fromPhase = [string]$state.phase
$fromRole = [string]$state.next_role

$state.phase = $ToPhase
$state.next_role = $ToRole
if ($PSBoundParameters.ContainsKey('TaskId') -and $TaskId) { $state.task_id = $TaskId }
if ($PSBoundParameters.ContainsKey('RunId') -and $RunId) { $state.run_id = $RunId }
if ($ToPhase -eq 'triage' -and $ToRole -eq 'RESEARCH' -and $null -eq $state.attempt) {
  $state | Add-Member -NotePropertyName attempt -NotePropertyValue 0 -Force
}
$state.updated_at = [DateTime]::UtcNow.ToString('o')
$tmpPath = [System.IO.Path]::ChangeExtension($statePath, '.tmp')
$state | ConvertTo-Json -Depth 8 | Set-Content -Path $tmpPath -Encoding UTF8
Move-Item -Force -Path $tmpPath -Destination $statePath

if (!(Test-Path $journalPath)) {
  "# Journal`r`n" | Set-Content -Path $journalPath -Encoding UTF8
}
$ts = [DateTime]::UtcNow.ToString('o')
$entry = "- [$ts] state transition: $fromPhase/$fromRole -> $ToPhase/$ToRole"
if ($PSBoundParameters.ContainsKey('Note') -and $Note) {
  $entry = "$entry | note: $Note"
}
Add-Content -Path $journalPath -Value $entry

Write-Host "Updated state: $fromPhase/$fromRole -> $ToPhase/$ToRole"
