# context_window_warn.ps1 — Non-blocking context window size check (AI-012)
# Warns when CLAUDE.md, MEMORY.md, or JOURNAL.md approach the compaction limit.
# Always exits 0 — never blocks the commit.
$python = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { $null }
if (-not $python) { exit 0 }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tool = Join-Path $repoRoot 'tools\context_window_check.py'
if (-not (Test-Path $tool)) { exit 0 }

$output = & $python $tool --quiet 2>&1
$exitCode = $LASTEXITCODE

if ($exitCode -eq 1) {
    Write-Host ""
    Write-Host "  WARNING: Context window threshold exceeded — run /compact or /clear before next session." -ForegroundColor Yellow
    if ($output) {
        foreach ($line in ($output -split "`n")) {
            if ($line.Trim()) {
                Write-Host "    $line" -ForegroundColor DarkYellow
            }
        }
    }
    Write-Host ""
} elseif ($exitCode -eq 0 -and $output) {
    # warn threshold hit (exit 0 but tool printed something)
    Write-Host ""
    Write-Host "  NOTICE: Context window approaching limit." -ForegroundColor Cyan
    foreach ($line in ($output -split "`n")) {
        if ($line.Trim()) {
            Write-Host "    $line" -ForegroundColor DarkCyan
        }
    }
    Write-Host ""
}

exit 0
