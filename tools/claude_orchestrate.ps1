[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$statePath = Join-Path $repoRoot 'claude/STATE.json'
if (!(Test-Path $statePath)) { throw "Missing $statePath" }
$state = Get-Content -Raw -Path $statePath | ConvertFrom-Json

$allowedPhases = @('triage', 'research', 'plan', 'build', 'verify', 'done')
$allowedRoles = @('RESEARCH', 'ARCHITECT', 'DEV', 'AUDITOR')
$phaseRoleMap = @{
  triage = 'RESEARCH'
  research = 'ARCHITECT'
  plan = 'DEV'
  build = 'DEV'
  verify = 'AUDITOR'
}

if ($allowedPhases -notcontains $state.phase) { throw "Invalid phase '$($state.phase)'" }
if ($allowedRoles -notcontains $state.next_role) { throw "Invalid next_role '$($state.next_role)'" }
if ($state.phase -ne 'done' -and $phaseRoleMap[$state.phase] -ne $state.next_role) {
  throw "State violates transition mapping in STATE_SCHEMA.md for phase '$($state.phase)'."
}
if ([int]$state.attempt -gt [int]$state.max_attempts) {
  throw "Attempt count exceeds max_attempts."
}

Write-Host "Current task: $($state.task_id)"
Write-Host "Phase: $($state.phase)"
Write-Host "Next role: $($state.next_role)"
Write-Host "Attempts: $($state.attempt)/$($state.max_attempts)"
Write-Host ''

switch ($state.next_role) {
  'RESEARCH' {
@'
COPY/PASTE PROMPT
You are RESEARCH.
1) Read claude/AGENT_ENTRY.md and claude/CONTROL.md.
2) Run: pwsh tools/research_extract.ps1
3) Write findings and hypotheses to claude/HANDOFF_ARCHITECT.md.
4) Keep implementation decisions out of research output.
'@ | Write-Host
  }
  'ARCHITECT' {
@'
COPY/PASTE PROMPT
You are ARCHITECT.
1) Read claude/AGENT_ENTRY.md and existing handoffs.
2) Produce implementation plan in claude/HANDOFF_DEV.md.
3) Include strict Allowed changes file list and acceptance criteria.
'@ | Write-Host
  }
  'DEV' {
@'
COPY/PASTE PROMPT
You are DEV.
1) Read claude/AGENT_ENTRY.md and claude/HANDOFF_DEV.md.
2) Run: pwsh tools/extract_allowed_files.ps1
3) Implement only allowed files.
4) Run: pwsh tools/dev_gate.ps1 -Mode Manual
'@ | Write-Host
  }
  'AUDITOR' {
@'
COPY/PASTE PROMPT
You are AUDITOR.
1) Read claude/AGENT_ENTRY.md and claude/VERIFY.json.
2) Run: pwsh tools/audit_check.ps1
3) Report pass/fail from claude/verify_last.json.
'@ | Write-Host
  }
}

