# SimpleCast 0.9.0 beta build provenance

This record describes the Windows beta artifacts produced for
`v0.9.0-beta.1`.

## Source

- Repository: `https://github.com/frigstah/SimpleCast`
- License: GNU GPL version 3 or later
- Release tag: `v0.9.0-beta.1`
- The exact source revision and dirty/clean state are written into
  `COMPONENT_HASHES.txt` by `build.ps1`.

GitHub's automatically generated source archives for the release tag contain the
SimpleCast source. They do not replace the corresponding-source obligations for
the separately bundled FFmpeg executable.

## Build environment

- Windows 11 x64, build `10.0.26100`
- PowerShell `7.6.3`
- Python `3.14.3`
- PyInstaller `6.21.0`
- Inno Setup `6.7.3`
- Dependency versions are pinned in `requirements.txt`.
- Bundled encoder: `imageio-ffmpeg 0.6.0`, containing the gyan.dev FFmpeg 7.1
  essentials build

## Reproduction

From the tagged source checkout:

```powershell
python -m pip install -r requirements.txt
.\build-installer.ps1
Compress-Archive -Path .\dist\SimpleCast\* `
  -DestinationPath .\SimpleCast-Windows-x64-v0.9.0-beta-portable.zip `
  -CompressionLevel Optimal
Get-FileHash -Algorithm SHA256 `
  .\installer\output\SimpleCast-Setup-0.9.0-x64.exe, `
  .\SimpleCast-Windows-x64-v0.9.0-beta-portable.zip
```

PyInstaller and Inno Setup embed timestamps and other environment-dependent
metadata, so a correct rebuild is not guaranteed to be byte-for-byte identical.
The corresponding source must nevertheless match the source used for the
published binaries.

## Published verification

The release includes `SHA256SUMS-0.9.0.txt`. The generated
`COMPONENT_HASHES.txt` inside both packages records:

- SimpleCast version
- build time in UTC
- source revision and working-tree state
- `SimpleCast.exe` SHA-256
- bundled FFmpeg filename and SHA-256

## Signing

The beta artifacts are intentionally unsigned. Windows SmartScreen or Smart App
Control may warn users. Verify the SHA-256 checksums before running either
artifact.

## FFmpeg compliance gate

The bundled FFmpeg executable is GPLv3-configured and statically includes
third-party libraries. Do not publish the draft release until exact corresponding
source and build information for that executable are available alongside the
binaries, or the encoder is replaced by a distribution with a completed,
reviewed compliance package.
