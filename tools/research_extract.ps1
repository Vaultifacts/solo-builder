[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$claudeDir = Join-Path $repoRoot 'claude'
$ciPath = Join-Path $claudeDir 'ci_context.json'
$logPath = Join-Path $claudeDir 'logs/latest.txt'
$outPath = Join-Path $claudeDir 'RESEARCH_DRAFT.md'

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# Research Draft') | Out-Null
$lines.Add('') | Out-Null
$lines.Add("Generated: $([DateTime]::UtcNow.ToString('o'))") | Out-Null
$lines.Add('') | Out-Null

$lines.Add('## CI Context') | Out-Null
if (Test-Path $ciPath) {
  $ci = Get-Content -Raw -Path $ciPath | ConvertFrom-Json
  $lines.Add("- Run ID: $($ci.run_id)") | Out-Null
  $lines.Add("- Workflow: $($ci.workflow)") | Out-Null
  $lines.Add("- Branch: $($ci.branch)") | Out-Null
  $lines.Add("- Title: $($ci.title)") | Out-Null
} else {
  $lines.Add('- No ci_context.json found') | Out-Null
}
$lines.Add('') | Out-Null

$lines.Add('## Log Tail (latest 200 lines)') | Out-Null
if (Test-Path $logPath) {
  $lines.Add('```text') | Out-Null
  Get-Content -Path $logPath -Tail 200 | ForEach-Object { $lines.Add($_) | Out-Null }
  $lines.Add('```') | Out-Null
} else {
  $lines.Add('No log file found at claude/logs/latest.txt') | Out-Null
}
$lines.Add('') | Out-Null

$junit = @()
$play = @()
try { $junit = (& (Join-Path $PSScriptRoot 'parse_junit.ps1') -Root (Join-Path $claudeDir 'artifacts') | ConvertFrom-Json) } catch {}
try { $play = (& (Join-Path $PSScriptRoot 'parse_playwright.ps1') -Root (Join-Path $claudeDir 'artifacts') | ConvertFrom-Json) } catch {}

$lines.Add('## Parsed Failures') | Out-Null
$lines.Add('### JUnit') | Out-Null
if ($junit -and $junit.Count -gt 0) {
  foreach ($j in $junit | Select-Object -First 20) { $lines.Add("- $($j.suite)::$($j.test) - $($j.message)") | Out-Null }
} else {
  $lines.Add('- None found') | Out-Null
}
$lines.Add('### Playwright') | Out-Null
if ($play -and $play.Count -gt 0) {
  foreach ($p in $play | Select-Object -First 20) { $lines.Add("- $($p.title) [$($p.status)] - $($p.message)") | Out-Null }
} else {
  $lines.Add('- None found') | Out-Null
}

$lines -join "`r`n" | Set-Content -Path $outPath -Encoding UTF8
Write-Host "Wrote $outPath"

