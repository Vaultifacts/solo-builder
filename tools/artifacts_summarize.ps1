[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$artifactRoot = Join-Path $repoRoot 'claude/artifacts'
$outPath = Join-Path $repoRoot 'claude/ARTIFACTS_SUMMARY.md'

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# Artifacts Summary') | Out-Null
$lines.Add('') | Out-Null
$lines.Add("Generated: $([DateTime]::UtcNow.ToString('o'))") | Out-Null
$lines.Add('') | Out-Null

if (Test-Path $artifactRoot) {
  $runDirs = Get-ChildItem -Path $artifactRoot -Directory | Sort-Object Name -Descending
  if ($runDirs.Count -eq 0) {
    $lines.Add('No artifact run directories found.') | Out-Null
  } else {
    foreach ($d in $runDirs) {
      $lines.Add("## Run $($d.Name)") | Out-Null
      $files = Get-ChildItem -Path $d.FullName -Recurse -File
      $lines.Add("Files: $($files.Count)") | Out-Null
      foreach ($f in $files | Select-Object -First 30) {
        $rel = $f.FullName.Substring($repoRoot.Length + 1)
        $lines.Add("- $rel ($([Math]::Round($f.Length / 1KB, 2)) KiB)") | Out-Null
      }
      if ($files.Count -gt 30) { $lines.Add("- ... $($files.Count - 30) more") | Out-Null }
      $lines.Add('') | Out-Null
    }
  }
} else {
  $lines.Add('Artifacts directory does not exist yet.') | Out-Null
}

$junit = @()
$play = @()
try { $junit = (& (Join-Path $PSScriptRoot 'parse_junit.ps1') -Root $artifactRoot | ConvertFrom-Json) } catch {}
try { $play = (& (Join-Path $PSScriptRoot 'parse_playwright.ps1') -Root $artifactRoot | ConvertFrom-Json) } catch {}

$lines.Add('## Parsed JUnit Failures (best effort)') | Out-Null
if ($junit -and $junit.Count -gt 0) {
  foreach ($j in $junit | Select-Object -First 20) {
    $lines.Add("- $($j.suite)::$($j.test) - $($j.message)") | Out-Null
  }
} else {
  $lines.Add('- None found') | Out-Null
}
$lines.Add('') | Out-Null

$lines.Add('## Parsed Playwright Failures (best effort)') | Out-Null
if ($play -and $play.Count -gt 0) {
  foreach ($p in $play | Select-Object -First 20) {
    $lines.Add("- $($p.title) [$($p.status)] - $($p.message)") | Out-Null
  }
} else {
  $lines.Add('- None found') | Out-Null
}

$lines -join "`r`n" | Set-Content -Path $outPath -Encoding UTF8
Write-Host "Wrote $outPath"

