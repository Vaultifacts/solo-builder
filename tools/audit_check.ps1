[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$claudeDir = Join-Path $repoRoot 'claude'
$verifyPath = Join-Path $claudeDir 'VERIFY.json'
$resultPath = Join-Path $claudeDir 'verify_last.json'
$statePath = Join-Path $claudeDir 'STATE.json'
$nextActionCheckPath = Join-Path $PSScriptRoot 'check_next_action_consistency.ps1'

# Autonomous Architecture Auditor -- resolved from env var or sibling directory.
$auditorDir = if ($env:ARCH_AUDITOR_PATH) {
  $env:ARCH_AUDITOR_PATH
} else {
  $candidate = Join-Path (Split-Path $repoRoot -Parent) 'Autonomous-Architecture-Auditor'
  if (Test-Path (Join-Path $candidate 'main.py')) { $candidate } else { $null }
}

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
    # Scalars only -- strip PSObject metadata that Get-Content -Raw attaches.
    # Prevents ConvertTo-Json circular-reference infinite loops in PS 5.1.
    $ec  = if ($timedOut) { 124 } else { [int]$proc.ExitCode }
    $out = if (Test-Path $stdoutFile) { [string](Get-Content -Raw -Path $stdoutFile) } else { '' }
    $err = if (Test-Path $stderrFile) { [string](Get-Content -Raw -Path $stderrFile) } else { '' }
    [pscustomobject]@{
      exit_code = $ec
      timed_out = $timedOut
      stdout    = $out
      stderr    = $err
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

# Restore known-volatile files mutated by the test suite before dirty-tree check.
# metrics.jsonl is written by executor/metrics modules during every test run.
$_knownVolatile = @('solo_builder/metrics.jsonl')
foreach ($_vf in $_knownVolatile) {
  git restore --source=HEAD --worktree -- $_vf 2>$null | Out-Null
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

# -- Architecture audit (non-blocking -- appended as extra data) ------------
$archResult = [pscustomobject]@{ ran = $false; skipped_reason = 'auditor not found' }
if ($auditorDir) {
  $tmpOut = Join-Path ([IO.Path]::GetTempPath()) "sb_arch_$([DateTime]::UtcNow.Ticks)"
  $null = New-Item -ItemType Directory -Path $tmpOut -Force -ErrorAction SilentlyContinue
  try {
    Write-Host "Running: architecture-audit"
    $env:PYTHONIOENCODING = 'utf-8'
    # Use & (synchronous call operator) -- avoids Start-Process/WaitForExit
    # deadlock on shared-console child processes on Windows.
    Push-Location $auditorDir
    & python main.py "$repoRoot" --output-format json-summary --output-dir "$tmpOut" --quiet --diff-from master --plugins-dir plugins --no-snapshot
    $archExitCode = $LASTEXITCODE
    Pop-Location

    $archFile = Get-ChildItem -Path $tmpOut -Filter '*.json-summary' -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($archFile -and ($archExitCode -le 3)) {
      $ad = Get-Content -Raw -Path $archFile.FullName | ConvertFrom-Json
      # Scalars only -- nested PSCustomObjects from ConvertFrom-Json cause
      # ConvertTo-Json to loop forever in PS 5.1 (circular reference bug).
      # The full json-summary file is preserved in claude/arch_last.json.
      Copy-Item -Path $archFile.FullName -Destination (Join-Path $claudeDir 'arch_last.json') -Force -ErrorAction SilentlyContinue
      $archResult = [pscustomobject]@{
        ran            = $true
        health_score   = [double]$ad.health_score
        risk_score     = [double]$ad.risk_score
        critical       = [int]$ad.counts.critical
        major          = [int]$ad.counts.major
        minor          = [int]$ad.counts.minor
        gaps           = [int]$ad.counts.gaps
        recommendation = [string]$ad.recommendation
        exit_code      = [int]$archExitCode
      }
    } else {
      $archResult = [pscustomobject]@{
        ran           = $false
        skipped_reason = "exit $archExitCode"
      }
    }
  } catch {
    $archResult = [pscustomobject]@{ ran = $false; skipped_reason = "exception: $_" }
  } finally {
    Remove-Item -Recurse -Force $tmpOut -ErrorAction SilentlyContinue
  }
}

[pscustomobject]@{
  generated_at = [DateTime]::UtcNow.ToString('o')
  passed = $passedAll
  message = $message
  working_tree_dirty = $workingTreeDirty
  dirty_files = $dirtyFiles
  dirty_files_remaining = $dirtyFilesRemaining
  results = $results
  architecture = $archResult
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
