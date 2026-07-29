param(
  [int]$SoakSeconds = 30,
  [switch]$RequireSigned
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$pythonVersion = python -c "from simplecast import __version__; print(__version__)"
$installerVersion = (
  Select-String -LiteralPath "installer\SimpleCast.iss" `
    -Pattern '#define MyAppVersion "([^"]+)"'
).Matches.Groups[1].Value
if ($pythonVersion -ne $installerVersion) {
  throw "Version mismatch: Python=$pythonVersion installer=$installerVersion"
}

python -m compileall -q simplecast tests tools
if ($LASTEXITCODE -ne 0) {
  throw "Python compilation failed."
}

python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
  throw "Automated tests failed."
}

$soakOutput = Join-Path $env:TEMP "SimpleCast-release-soak.mp3"
Remove-Item -LiteralPath $soakOutput -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath ([IO.Path]::ChangeExtension($soakOutput, ".json")) `
  -Force -ErrorAction SilentlyContinue
python tools\encoder_soak.py `
  --seconds $SoakSeconds `
  --processing "Mixed content" `
  --output $soakOutput
if ($LASTEXITCODE -ne 0) {
  throw "Encoder soak check failed."
}

$executable = Join-Path $projectRoot "dist\SimpleCast\SimpleCast.exe"
if (Test-Path -LiteralPath $executable) {
  $signature = Get-AuthenticodeSignature -LiteralPath $executable
  Write-Host "Authenticode status: $($signature.Status)"
  if ($RequireSigned -and $signature.Status -ne "Valid") {
    throw "A valid Authenticode signature is required for this release."
  }
}

Write-Host "Local release checks passed for SimpleCast $pythonVersion."
