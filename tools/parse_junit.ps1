[CmdletBinding()]
param(
  [string]$Root = 'claude/artifacts'
)
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$scanRoot = if ([IO.Path]::IsPathRooted($Root)) { $Root } else { Join-Path $repoRoot $Root }
if (!(Test-Path $scanRoot)) { @() | ConvertTo-Json -Depth 8 | Write-Output; exit 0 }

$out = New-Object System.Collections.Generic.List[object]
Get-ChildItem -Path $scanRoot -Recurse -File -Filter *.xml -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    [xml]$doc = Get-Content -Raw -Path $_.FullName
    $nodes = $doc.SelectNodes('//testcase')
    foreach ($tc in $nodes) {
      $failure = $tc.SelectSingleNode('failure')
      $error = $tc.SelectSingleNode('error')
      if ($failure -or $error) {
        $node = if ($failure) { $failure } else { $error }
        $out.Add([pscustomobject]@{
          source = $_.FullName
          suite = [string]$tc.classname
          test = [string]$tc.name
          message = [string]$node.message
        }) | Out-Null
      }
    }
  } catch {}
}

$out | ConvertTo-Json -Depth 8 | Write-Output

