[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$claudeDir = Join-Path $repoRoot 'claude'
$verifyPath = Join-Path $claudeDir 'VERIFY.json'
$resultPath = Join-Path $claudeDir 'verify_last.json'
$statePath = Join-Path $claudeDir 'STATE.json'
$nextActionCheckPath = Join-Path $PSScriptRoot 'check_next_action_consistency.ps1'

function Get-TrackedChangedPaths {
  $lines = @(git status --porcelain 2>$null)
  if ($LASTEXITCODE -ne 0) { throw 'git status --porcelain failed.' }
  $paths = New-Object System.Collections.Generic.List[string]
  foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    if ($line.StartsWith('?? ')) { continue }
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

function Invoke-CommandWithTimeout {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [int]$TimeoutSec = 300
  )
  $stdoutFile = [IO.Path]::GetTempFileName()
  $stderrFile = [IO.Path]::GetTempFileName()
  try {
    $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/d', '/s', '/c', $Command -NoNewWindow -PassThru -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
    $timedOut = -not $proc.WaitForExit($TimeoutSec * 1000)
    if ($timedOut) { try { $proc.Kill() } catch {} }
    [pscustomobject]@{
      exit_code = if ($timedOut) { 124 } else { $proc.ExitCode }
      timed_out = $timedOut
      stdout = if (Test-Path $stdoutFile) { Get-Content -Raw -Path $stdoutFile } else { '' }
      stderr = if (Test-Path $stderrFile) { Get-Content -Raw -Path $stderrFile } else { '' }
    }
  } finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $stdoutFile, $stderrFile
  }
}

if (!(Test-Path $verifyPath)) { throw "Missing $verifyPath" }
if (!(Test-Path $statePath)) { throw "Missing $statePath" }
if (!(Test-Path $nextActionCheckPath)) { throw "Missing $nextActionCheckPath" }

# Fail fast if rendered agent-facing state diverges from machine state.
& $nextActionCheckPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$beforeTracked = Get-TrackedChangedPaths
$verify = Get-Content -Raw -Path $verifyPath | ConvertFrom-Json
$results = New-Object System.Collections.Generic.List[object]
$requiredFailures = 0

foreach ($cmd in $verify.commands) {
  $timeoutSec = if ($cmd.timeout_sec) { [int]$cmd.timeout_sec } else { 300 }
  Write-Host "Running: $($cmd.name)"
  $run = Invoke-CommandWithTimeout -Command $cmd.command -TimeoutSec $timeoutSec
  $passed = (-not $run.timed_out) -and ($run.exit_code -eq 0)
  if (($cmd.required -eq $true) -and (-not $passed)) { $requiredFailures++ }
  $results.Add([pscustomobject]@{
    name = $cmd.name
    command = $cmd.command
    required = [bool]$cmd.required
    timeout_sec = $timeoutSec
    passed = $passed
    exit_code = $run.exit_code
    timed_out = $run.timed_out
    stdout = $run.stdout
    stderr = $run.stderr
  }) | Out-Null
}

$afterTracked = Get-TrackedChangedPaths
$dirtyFiles = @($afterTracked | Where-Object { $beforeTracked -notcontains $_ })
$workingTreeDirty = ($dirtyFiles.Count -gt 0)
$dirtyFilesRemaining = @()

if ($workingTreeDirty) {
  try {
    git restore --source=HEAD --worktree --staged -- $dirtyFiles | Out-Null
  } catch {}
  $afterRestoreTracked = Get-TrackedChangedPaths
  $dirtyFilesRemaining = @($afterRestoreTracked | Where-Object { $beforeTracked -notcontains $_ })
}

$passedAll = ($requiredFailures -eq 0) -and (-not $workingTreeDirty)
if ($workingTreeDirty) {
  $message = "Working tree mutated during verification: $($dirtyFiles -join ', ')"
} else {
  $message = if ($passedAll) { 'All required verification commands passed.' } else { "$requiredFailures required command(s) failed." }
}

[pscustomobject]@{
  generated_at = [DateTime]::UtcNow.ToString('o')
  passed = $passedAll
  message = $message
  working_tree_dirty = $workingTreeDirty
  dirty_files = $dirtyFiles
  dirty_files_remaining = $dirtyFilesRemaining
  results = $results
} | ConvertTo-Json -Depth 12 | Set-Content -Path $resultPath -Encoding UTF8

$state = Get-Content -Raw -Path $statePath | ConvertFrom-Json
if ($passedAll) {
  $state.last_verify_pass = $true
  $state.phase = 'done'
} else {
  $state.last_verify_pass = $false
  $state.attempt = [int]$state.attempt + 1
  $state.phase = 'verify'
  $state.next_role = 'ARCHITECT'
}
$state.updated_at = [DateTime]::UtcNow.ToString('o')
$state | ConvertTo-Json -Depth 8 | Set-Content -Path $statePath -Encoding UTF8

if (-not $passedAll) {
  try { & (Join-Path $PSScriptRoot 'claude_snapshot.ps1') -Label 'verify-fail' | Out-Null } catch {}
  Write-Error $message
  exit 1
}

Write-Host $message
exit 0
