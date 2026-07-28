$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name SimpleCast `
  --collect-all sounddevice `
  --collect-all keyring `
  --collect-all imageio_ffmpeg `
  --collect-all pystray `
  --collect-all PIL `
  main.py
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$distRoot = Join-Path $projectRoot "dist\SimpleCast"
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\ROADMAP.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\CERTIFICATION.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\RELEASE_CHECKLIST.md") -Destination $distRoot
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\PRIVACY.md") -Destination $distRoot

$applicationHash = (Get-FileHash `
  -LiteralPath (Join-Path $distRoot "SimpleCast.exe") `
  -Algorithm SHA256).Hash
$ffmpegBinary = Get-ChildItem `
  -LiteralPath (Join-Path $distRoot "_internal\imageio_ffmpeg\binaries") `
  -Filter "ffmpeg*.exe" |
  Select-Object -First 1
$ffmpegHash = if ($ffmpegBinary) {
  (Get-FileHash -LiteralPath $ffmpegBinary.FullName -Algorithm SHA256).Hash
} else {
  "NOT FOUND"
}
@(
  "SimpleCast version: $(python -c `"from simplecast import __version__; print(__version__)`")"
  "Build UTC: $([DateTime]::UtcNow.ToString('o'))"
  "SimpleCast.exe SHA256: $applicationHash"
  "FFmpeg binary: $($ffmpegBinary.Name)"
  "FFmpeg SHA256: $ffmpegHash"
) | Set-Content `
  -LiteralPath (Join-Path $distRoot "COMPONENT_HASHES.txt") `
  -Encoding UTF8

Write-Host "Built: $projectRoot\dist\SimpleCast\SimpleCast.exe"
