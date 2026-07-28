$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$compiler = Get-Command iscc.exe -ErrorAction SilentlyContinue
$compilerPath = if ($compiler) { $compiler.Source } else { $null }

if (-not $compilerPath) {
  $knownPaths = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
  )
  $compilerPath = $knownPaths |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
}

if (-not $compilerPath) {
  throw "Inno Setup 6 is required. Install it, then run this script again."
}

& (Join-Path $projectRoot "build.ps1")
if ($LASTEXITCODE -ne 0) {
  throw "Application build failed with exit code $LASTEXITCODE."
}

& $compilerPath (Join-Path $projectRoot "installer\SimpleCast.iss")
if ($LASTEXITCODE -ne 0) {
  throw "Installer build failed with exit code $LASTEXITCODE."
}

Write-Host "Installer created in: $projectRoot\installer\output"
