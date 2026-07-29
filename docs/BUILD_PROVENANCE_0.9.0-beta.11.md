# SimpleCast 0.9.0 beta 11 build provenance

This record describes the Windows artifacts produced for
`v0.9.0-beta.11`.

## Source

- Repository: `https://github.com/frigstah/SimpleCast`
- License: GNU GPL version 3 or later
- Release tag: `v0.9.0-beta.11`
- The exact source revision and dirty/clean state are written into
  `COMPONENT_HASHES.txt` by `build.ps1`.

GitHub's automatically generated source archives for the release tag contain the
SimpleCast source. They do not replace the corresponding-source obligations for
the separately bundled FFmpeg executable.

## Build environment

- Windows 11 x64
- Dependency versions are pinned in `requirements.txt`.
- Bundled encoder:
  `ffmpeg-n7.1.5-10-g2aefd64d48-win64-lgpl-7.1`
- FFmpeg revision `2aefd64d48`; BtbN build revision
  `8c736b2d6fe5da2a10a8896d01e53bfb0ca4f665`

## Reproduction

Tagged releases are built by `.github/workflows/release-windows.yml`. For a
local equivalent:

```powershell
python -m pip install -r requirements.txt
.\prepare-ffmpeg.ps1
.\release-check.ps1 -SoakSeconds 15
.\build.ps1
& "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe" `
  .\installer\SimpleCast.iss
Compress-Archive -Path .\dist\SimpleCast `
  -DestinationPath .\SimpleCast-Windows-x64-v0.9.0-beta.11-portable.zip `
  -CompressionLevel Optimal
Get-FileHash -Algorithm SHA256 `
  .\installer\output\SimpleCast-Setup-0.9.0-beta.11-x64.exe, `
  .\SimpleCast-Windows-x64-v0.9.0-beta.11-portable.zip, `
  .\SimpleCast-FFmpeg-Corresponding-Source-0.9.0.zip
```

PyInstaller and Inno Setup embed timestamps and other environment-dependent
metadata, so a correct rebuild is not guaranteed to be byte-for-byte identical.

## Verification and signing

`COMPONENT_HASHES.txt` records the SimpleCast version, UTC build time, source
revision and state, application hash, and bundled FFmpeg hash.

The beta artifacts are intentionally unsigned. The updater verifies an official
GitHub installer's expected size and SHA-256 digest before launching it.

The release must include
`SimpleCast-FFmpeg-Corresponding-Source-0.9.0.zip`. See `FFMPEG_SOURCE.md`.
