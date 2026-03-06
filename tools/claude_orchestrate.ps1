[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$statePath = Join-Path $repoRoot 'claude/STATE.json'
$nextActionPath = Join-Path $repoRoot 'claude/NEXT_ACTION.md'
$nextActionTemplatePath = Join-Path $repoRoot 'claude/templates/NEXT_ACTION_TEMPLATE.md'
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

function Get-RoleContract {
  param(
    [Parameter(Mandatory=$true)][string]$Phase,
    [Parameter(Mandatory=$true)][string]$Role,
    [Parameter(Mandatory=$true)][string]$TaskId
  )

  if ($Phase -eq 'done') {
    $donePrompt = switch ($Role) {
      'ARCHITECT' {
@'
COPY/PASTE PROMPT
You are ARCHITECT.
1) Read claude/AGENT_ENTRY.md, claude/CONTROL.md, and claude/NEXT_ACTION.md.
2) Initialize the next task only (no implementation on closed task).
'@
      }
      'AUDITOR' {
@'
COPY/PASTE PROMPT
You are AUDITOR.
1) Read claude/AGENT_ENTRY.md and claude/VERIFY.json.
2) Run: pwsh tools/audit_check.ps1
3) Report pass/fail from claude/verify_last.json.
'@
      }
      default {
@"
COPY/PASTE PROMPT
You are $Role.
1) Read claude/AGENT_ENTRY.md, claude/CONTROL.md, and claude/NEXT_ACTION.md.
2) Task is closed. Initialize the next task only.
"@
      }
    }

    return @{
      Status = 'closed'
      AllowedOperation = "Task $TaskId is closed. Initialize the next task only."
      RequiredReads = @(
        'claude/AGENT_ENTRY.md',
        'claude/CONTROL.md',
        'claude/NEXT_ACTION.md'
      )
      RequiredCommand = 'pwsh tools/claude_orchestrate.ps1'
      CommitExpectation = "chore: initialize next task after closing $TaskId"
      Rules = @(
        'Do not reopen closed task without a new task entry.',
        'Merge closed task branch to master before creating the next task branch.',
        'Preserve deterministic workflow conventions.'
      )
      Prompt = $donePrompt
    }
  }

  switch ($Role) {
    'RESEARCH' {
      return @{
        Status = 'ready'
        AllowedOperation = 'Write claude/HANDOFF_ARCHITECT.md only.'
        RequiredReads = @(
          'claude/AGENT_ENTRY.md',
          'claude/CONTROL.md',
          'claude/NEXT_ACTION.md'
        )
        RequiredCommand = 'pwsh tools/research_extract.ps1'
        CommitExpectation = "research: $TaskId handoff to architect"
        Rules = @(
          'Do not implement yet.',
          'Keep implementation decisions out of research output.',
          'Do not modify unrelated files.'
        )
        Prompt = @'
COPY/PASTE PROMPT
You are RESEARCH.
1) Read claude/AGENT_ENTRY.md, claude/CONTROL.md, and claude/NEXT_ACTION.md.
2) Run: pwsh tools/research_extract.ps1
3) Write findings and hypotheses to claude/HANDOFF_ARCHITECT.md.
4) Keep implementation decisions out of research output.
'@
      }
    }
    'ARCHITECT' {
      return @{
        Status = 'ready'
        AllowedOperation = 'Write claude/HANDOFF_DEV.md only.'
        RequiredReads = @(
          'claude/AGENT_ENTRY.md',
          'claude/CONTROL.md',
          'claude/NEXT_ACTION.md',
          'claude/HANDOFF_ARCHITECT.md'
        )
        RequiredCommand = 'pwsh tools/claude_orchestrate.ps1'
        CommitExpectation = "architect: $TaskId handoff to dev"
        Rules = @(
          'Do not implement yet.',
          'Include strict Allowed changes file list and acceptance criteria.',
          'Do not modify unrelated files.'
        )
        Prompt = @'
COPY/PASTE PROMPT
You are ARCHITECT.
1) Read claude/AGENT_ENTRY.md, claude/CONTROL.md, claude/NEXT_ACTION.md, and existing handoffs.
2) Produce implementation plan in claude/HANDOFF_DEV.md.
3) Include strict Allowed changes file list and acceptance criteria.
'@
      }
    }
    'DEV' {
      return @{
        Status = 'ready'
        AllowedOperation = 'Implement only files listed in claude/allowed_files.txt and write claude/HANDOFF_AUDIT.md.'
        RequiredReads = @(
          'claude/AGENT_ENTRY.md',
          'claude/CONTROL.md',
          'claude/NEXT_ACTION.md',
          'claude/HANDOFF_DEV.md'
        )
        RequiredCommand = 'pwsh tools/extract_allowed_files.ps1'
        CommitExpectation = "dev: $TaskId implementation"
        Rules = @(
          'Implement only allowed files.',
          'Run dev gate before handoff to auditor.',
          'Do not modify unrelated files.'
        )
        Prompt = @'
COPY/PASTE PROMPT
You are DEV.
1) Read claude/AGENT_ENTRY.md, claude/CONTROL.md, claude/NEXT_ACTION.md, and claude/HANDOFF_DEV.md.
2) Run: pwsh tools/extract_allowed_files.ps1
3) Implement only allowed files.
4) Run: pwsh tools/dev_gate.ps1 -Mode Manual
'@
      }
    }
    'AUDITOR' {
      return @{
        Status = 'ready'
        AllowedOperation = 'Run verification and append auditor evidence to claude/HANDOFF_AUDIT.md only.'
        RequiredReads = @(
          'claude/AGENT_ENTRY.md',
          'claude/CONTROL.md',
          'claude/NEXT_ACTION.md',
          'claude/VERIFY.json',
          'claude/HANDOFF_AUDIT.md'
        )
        RequiredCommand = 'pwsh tools/audit_check.ps1'
        CommitExpectation = "audit: $TaskId verification result"
        Rules = @(
          'Do not modify implementation files.',
          'Report pass/fail from claude/verify_last.json.',
          'Do not expand task scope during audit.'
        )
        Prompt = @'
COPY/PASTE PROMPT
You are AUDITOR.
1) Read claude/AGENT_ENTRY.md, claude/CONTROL.md, claude/NEXT_ACTION.md, and claude/VERIFY.json.
2) Run: pwsh tools/audit_check.ps1
3) Report pass/fail from claude/verify_last.json.
'@
      }
    }
    default { throw "Unsupported role '$Role'" }
  }
}

function Format-BulletLines {
  param([string[]]$Items)
  return ($Items | ForEach-Object { "- $_" }) -join "`n"
}

$contract = Get-RoleContract -Phase $state.phase -Role $state.next_role -TaskId $state.task_id
$template = @'
# Next Action

## Task
{{TASK_ID}}

## Phase
{{PHASE}}

## Role
{{ROLE}}

## Status
{{STATUS}}

## Allowed operation
{{ALLOWED_OPERATION}}

## Required reads
{{REQUIRED_READS}}

## Required command
{{REQUIRED_COMMAND}}

## Commit expectation
{{COMMIT_EXPECTATION}}

## Rules
{{RULES}}
'@

if (Test-Path $nextActionTemplatePath) {
  $template = Get-Content -Raw -Path $nextActionTemplatePath
}

$renderedNextAction = $template
$renderedNextAction = $renderedNextAction.Replace('{{TASK_ID}}', [string]$state.task_id)
$renderedNextAction = $renderedNextAction.Replace('{{PHASE}}', [string]$state.phase)
$renderedNextAction = $renderedNextAction.Replace('{{ROLE}}', [string]$state.next_role)
$renderedNextAction = $renderedNextAction.Replace('{{STATUS}}', [string]$contract.Status)
$renderedNextAction = $renderedNextAction.Replace('{{ALLOWED_OPERATION}}', [string]$contract.AllowedOperation)
$renderedNextAction = $renderedNextAction.Replace('{{REQUIRED_READS}}', (Format-BulletLines -Items $contract.RequiredReads))
$renderedNextAction = $renderedNextAction.Replace('{{REQUIRED_COMMAND}}', [string]$contract.RequiredCommand)
$renderedNextAction = $renderedNextAction.Replace('{{COMMIT_EXPECTATION}}', [string]$contract.CommitExpectation)
$renderedNextAction = $renderedNextAction.Replace('{{RULES}}', (Format-BulletLines -Items $contract.Rules))

Set-Content -Path $nextActionPath -Value $renderedNextAction -Encoding UTF8

Write-Host "Current task: $($state.task_id)"
Write-Host "Phase: $($state.phase)"
Write-Host "Next role: $($state.next_role)"
Write-Host "Attempts: $($state.attempt)/$($state.max_attempts)"
Write-Host ''
$contract.Prompt | Write-Host
