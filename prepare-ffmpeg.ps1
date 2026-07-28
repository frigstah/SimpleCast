$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$vendorRoot = Join-Path $projectRoot "vendor\ffmpeg"
$archiveName = "ffmpeg-n7.1.5-10-g2aefd64d48-win64-lgpl-7.1.zip"
$archiveUri = (
  "https://github.com/BtbN/FFmpeg-Builds/releases/download/" +
  "autobuild-2026-07-28-13-32/$archiveName"
)
$archiveHash = "C01DDCB52800391F546CC519D465997A6A75454A6483C47CEB01325B19F65711"
$encoderHash = "0C3883925185BDAB1454C896910E4CF77CB9A087AC6D2D264F803D35493B5360"
$archivePath = Join-Path $env:TEMP "SimpleCast-$archiveName"

Write-Host "Downloading pinned LGPL FFmpeg build..."
Invoke-WebRequest -UseBasicParsing -Uri $archiveUri -OutFile $archivePath

try {
  $actualArchiveHash = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath
  ).Hash
  if ($actualArchiveHash -ne $archiveHash) {
    throw "FFmpeg archive hash mismatch."
  }

  New-Item -ItemType Directory -Path $vendorRoot -Force | Out-Null
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
  try {
    $encoderEntry = $archive.Entries |
      Where-Object { $_.FullName -match "/bin/ffmpeg\.exe$" } |
      Select-Object -First 1
    $licenseEntry = $archive.Entries |
      Where-Object { $_.FullName -match "/LICENSE\.txt$" } |
      Select-Object -First 1
    if (-not $encoderEntry -or -not $licenseEntry) {
      throw "Pinned FFmpeg archive is missing the encoder or license."
    }

    [System.IO.Compression.ZipFileExtensions]::ExtractToFile(
      $encoderEntry,
      (Join-Path $vendorRoot "ffmpeg.exe"),
      $true
    )
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile(
      $licenseEntry,
      (Join-Path $vendorRoot "LICENSE.txt"),
      $true
    )
  } finally {
    $archive.Dispose()
  }

  $actualEncoderHash = (
    Get-FileHash -Algorithm SHA256 `
      -LiteralPath (Join-Path $vendorRoot "ffmpeg.exe")
  ).Hash
  if ($actualEncoderHash -ne $encoderHash) {
    throw "Extracted FFmpeg executable hash mismatch."
  }

  Write-Host "Prepared pinned FFmpeg: $vendorRoot\ffmpeg.exe"
} finally {
  if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
  }
}
