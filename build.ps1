$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot
$vendorEncoder = Join-Path $projectRoot "vendor\ffmpeg\ffmpeg.exe"
$vendorLicense = Join-Path $projectRoot "vendor\ffmpeg\LICENSE.txt"
if (
  -not (Test-Path -LiteralPath $vendorEncoder) -or
  -not (Test-Path -LiteralPath $vendorLicense)
) {
  throw "Run .\prepare-ffmpeg.ps1 before building SimpleCast."
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name SimpleCast `
  --icon (Join-Path $projectRoot "assets\simplecast.ico") `
  --add-data "$projectRoot\assets\simplecast.ico;assets" `
  --add-data "$projectRoot\assets\simplecast-icon.png;assets" `
  --add-binary "$vendorEncoder;vendor\ffmpeg" `
  --add-data "$vendorLicense;vendor\ffmpeg" `
  --collect-all sounddevice `
  --collect-all keyring `
  --collect-all pystray `
  --collect-all PIL `
  main.py
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$distRoot = Join-Path $projectRoot "dist\SimpleCast"
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "QUICK_START.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "TRADEMARKS.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "FFMPEG_SOURCE.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\ROADMAP.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\CERTIFICATION.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\RELEASE_CHECKLIST.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\PRIVACY.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\BUILD_PROVENANCE_0.9.0-beta.5.md") -Destination $distRoot

$applicationHash = (Get-FileHash `
  -LiteralPath (Join-Path $distRoot "SimpleCast.exe") `
  -Algorithm SHA256).Hash
$ffmpegBinary = Get-Item -LiteralPath (
  Join-Path $distRoot "_internal\vendor\ffmpeg\ffmpeg.exe"
)
$ffmpegHash = if ($ffmpegBinary) {
  (Get-FileHash -LiteralPath $ffmpegBinary.FullName -Algorithm SHA256).Hash
} else {
  "NOT FOUND"
}
$sourceRevision = (git -C $projectRoot rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $sourceRevision) {
  $sourceRevision = "UNKNOWN"
}
$sourceState = if (git -C $projectRoot status --porcelain 2>$null) {
  "DIRTY"
} else {
  "CLEAN"
}
@(
  "SimpleCast version: $(python -c `"from simplecast import __version__; print(__version__)`")"
  "Build UTC: $([DateTime]::UtcNow.ToString('o'))"
  "Source revision: $sourceRevision"
  "Source working tree: $sourceState"
  "SimpleCast.exe SHA256: $applicationHash"
  "FFmpeg binary: $($ffmpegBinary.Name)"
  "FFmpeg SHA256: $ffmpegHash"
) | Set-Content `
  -LiteralPath (Join-Path $distRoot "COMPONENT_HASHES.txt") `
  -Encoding UTF8

Write-Host "Built: $projectRoot\dist\SimpleCast\SimpleCast.exe"
