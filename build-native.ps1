$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $projectRoot "native\process_loopback.cpp"
$outputDirectory = Join-Path $projectRoot "native\bin"
$output = Join-Path $outputDirectory "simplecast-process-loopback.exe"
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"

if (-not (Test-Path -LiteralPath $vswhere)) {
  throw "Visual Studio Build Tools were not found."
}

$visualStudio = & $vswhere `
  -latest `
  -products * `
  -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
  -property installationPath
if (-not $visualStudio) {
  throw "The Visual C++ x64 build tools are required."
}

$developerShell = Join-Path $visualStudio "Common7\Tools\VsDevCmd.bat"
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$compile = (
  "call `"$developerShell`" -no_logo -arch=x64 -host_arch=x64 && " +
  "cl.exe /nologo /std:c++17 /EHsc /O2 /DUNICODE /D_UNICODE " +
  "`"$source`" /Fo:`"$outputDirectory\process_loopback.obj`" " +
  "/Fe:`"$output`" /link /SUBSYSTEM:CONSOLE ole32.lib mmdevapi.lib"
)

cmd.exe /d /c $compile
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $output)) {
  throw "The process-loopback helper build failed."
}

Write-Host "Built: $output"
