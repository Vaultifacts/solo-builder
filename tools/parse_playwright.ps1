[CmdletBinding()]
param(
  [string]$Root = 'claude/artifacts'
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$scanRoot = if ([IO.Path]::IsPathRooted($Root)) { $Root } else { Join-Path $repoRoot $Root }
if (!(Test-Path $scanRoot)) { @() | ConvertTo-Json -Depth 10 | Write-Output; exit 0 }

$out = New-Object System.Collections.Generic.List[object]
Get-ChildItem -Path $scanRoot -Recurse -File -Filter *.json -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $raw = Get-Content -Raw -Path $_.FullName
    if ($raw -notmatch 'playwright|spec|tests|suites') { return }
    $obj = $raw | ConvertFrom-Json
    if ($obj.suites) {
      foreach ($suite in $obj.suites) {
        if ($suite.specs) {
          foreach ($spec in $suite.specs) {
            if ($spec.tests) {
              foreach ($test in $spec.tests) {
                $status = [string]$test.status
                if ($status -and $status -ne 'passed') {
                  $message = ''
                  if ($test.results -and $test.results[0] -and $test.results[0].error -and $test.results[0].error.message) {
                    $message = [string]$test.results[0].error.message
                  }
                  $out.Add([pscustomobject]@{
                    source = $_.FullName
                    title = [string]$spec.title
                    status = $status
                    message = $message
                  }) | Out-Null
                }
              }
            }
          }
        }
      }
    }
  } catch {}
}

$out | ConvertTo-Json -Depth 10 | Write-Output

