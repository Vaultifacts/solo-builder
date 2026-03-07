[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$violations = New-Object System.Collections.Generic.List[string]

# ---------------------------------------------------------------------------
# Phase A: Script-reference integrity
# Check that all tools/*.ps1 references in contract source files exist on disk.
# ---------------------------------------------------------------------------

$contractSources = @(
  'claude/AGENT_ENTRY.md',
  'claude/WORKFLOW_SPEC.md',
  'claude/NEXT_ACTION.md',
  'claude/RULES.md',
  '.github/workflows/ci.yml'
)

$checklistDir = Join-Path $repoRoot 'claude/checklists'
if (Test-Path $checklistDir) {
  Get-ChildItem -Path $checklistDir -Filter '*.md' | ForEach-Object {
    $contractSources += "claude/checklists/$($_.Name)"
  }
}

$refPattern = [regex]'tools/([A-Za-z_]+\.ps1)'

foreach ($rel in $contractSources) {
  $full = Join-Path $repoRoot $rel
  if (!(Test-Path $full)) { continue }
  $content = Get-Content -Raw -Path $full
  foreach ($m in $refPattern.Matches($content)) {
    $scriptRel = "tools/$($m.Groups[1].Value)"
    $scriptFull = Join-Path $repoRoot $scriptRel
    if (!(Test-Path $scriptFull)) {
      $violations.Add("[A] $rel references missing script: $scriptRel") | Out-Null
    }
  }
}

# ---------------------------------------------------------------------------
# Phase B: Lifecycle file declaration integrity
# Assert all files written by known lifecycle scripts appear in allowed_files.txt.
# ---------------------------------------------------------------------------

$allowedPath = Join-Path $repoRoot 'claude/allowed_files.txt'

# Read allowed_files.txt from git HEAD for CI-consistent determinism.
# This avoids false positives when allowed_files.txt is narrowed to DEV scope locally.
$allowedRaw = & git -C $repoRoot show "HEAD:claude/allowed_files.txt" 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($allowedRaw)) {
  # Fall back to working tree when HEAD version is unavailable
  if (!(Test-Path $allowedPath)) {
    Write-Error "workflow_contract_check: FAIL — claude/allowed_files.txt not found in HEAD or working tree."
    exit 1
  }
  $allowedRaw = Get-Content -Raw -Path $allowedPath
}

$allowed = @($allowedRaw -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })

# Canonical map: lifecycle script -> files it writes (relative to repo root, forward-slash)
$lifecycleMap = [ordered]@{
  'tools/start_task.ps1'          = @('claude/TASK_ACTIVE.md', 'claude/TASK_QUEUE.md', 'claude/JOURNAL.md', 'claude/STATE.json')
  'tools/advance_state.ps1'       = @('claude/JOURNAL.md', 'claude/STATE.json', 'claude/NEXT_ACTION.md')
  'tools/claude_orchestrate.ps1'  = @('claude/NEXT_ACTION.md')
  'tools/audit_check.ps1'         = @('claude/verify_last.json')
  'tools/extract_allowed_files.ps1' = @('claude/allowed_files.txt')
}

foreach ($script in $lifecycleMap.Keys) {
  foreach ($file in $lifecycleMap[$script]) {
    if ($allowed -notcontains $file) {
      $violations.Add("[B] $script writes $file but it is not declared in claude/allowed_files.txt") | Out-Null
    }
  }
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

if ($violations.Count -eq 0) {
  Write-Host "workflow_contract_check: PASS"
  exit 0
} else {
  Write-Host "workflow_contract_check: FAIL ($($violations.Count) violation(s))"
  foreach ($v in $violations) {
    Write-Host "  $v"
  }
  exit 1
}
