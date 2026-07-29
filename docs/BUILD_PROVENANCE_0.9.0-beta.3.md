# SimpleCast 0.9.0 beta 3 build provenance

This record describes the Windows artifacts produced for
`v0.9.0-beta.3`.

## Source

- Repository: `https://github.com/frigstah/SimpleCast`
- License: GNU GPL version 3 or later
- Release tag: `v0.9.0-beta.3`
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
- Bundled encoder:
  `ffmpeg-n7.1.5-10-g2aefd64d48-win64-lgpl-7.1`
- FFmpeg revision `2aefd64d48`; BtbN build revision
  `8c736b2d6fe5da2a10a8896d01e53bfb0ca4f665`

## Reproduction

From the tagged source checkout:

```powershell
python -m pip install -r requirements.txt
.\prepare-ffmpeg.ps1
.\build.ps1
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" `
  .\installer\SimpleCast.iss
Compress-Archive -Path .\dist\SimpleCast `
  -DestinationPath .\SimpleCast-Windows-x64-v0.9.0-beta.3-portable.zip `
  -CompressionLevel Optimal
Get-FileHash -Algorithm SHA256 `
  .\installer\output\SimpleCast-Setup-0.9.0-beta.3-x64.exe, `
  .\SimpleCast-Windows-x64-v0.9.0-beta.3-portable.zip, `
  .\SimpleCast-FFmpeg-Corresponding-Source-0.9.0.zip
```

PyInstaller and Inno Setup embed timestamps and other environment-dependent
metadata, so a correct rebuild is not guaranteed to be byte-for-byte identical.
The corresponding source must nevertheless match the source used for the
published binaries.

## Verification

The generated `COMPONENT_HASHES.txt` inside both Windows packages records:

- SimpleCast version
- Build time in UTC
- Source revision and working-tree state
- `SimpleCast.exe` SHA-256
- Bundled FFmpeg filename and SHA-256

## Signing

The beta artifacts are intentionally unsigned. Windows SmartScreen or Smart App
Control may warn users. Verify the SHA-256 checksums before running either
artifact.

## FFmpeg source and license

The bundled FFmpeg executable is LGPLv3, includes its license, and is pinned by
archive and executable hashes. A published release must include
`SimpleCast-FFmpeg-Corresponding-Source-0.9.0.zip`, containing the exact FFmpeg
source revision, exact BtbN build scripts, and the dependency source manifest.
See `FFMPEG_SOURCE.md`.
