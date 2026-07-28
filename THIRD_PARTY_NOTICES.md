# Third-party notices

The packaged SimpleCast beta includes third-party components. SimpleCast itself
is licensed under GNU GPL version 3 or later; see `LICENSE`.

## FFmpeg

The packaged FFmpeg 7.1 binary is the gyan.dev essentials build configured as
GPLv3 and statically includes external libraries such as LAME, x264, and x265.
Its version/configuration can be inspected with:

```powershell
.\_internal\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe -version
```

The packaged application retains the `imageio-ffmpeg` license and binary README
under `_internal\imageio_ffmpeg`.

The packaged `COMPONENT_HASHES.txt` records the exact included FFmpeg binary:

- Filename: `ffmpeg-win-x86_64-v7.1.exe`
- SHA-256:
  `2CE797A0F88D7F067180338FB227F7B1928EA727BD9A4D7A1D022F7C52AF71A3`
- Configuration includes `--enable-gpl`, `--enable-version3`, static linking,
  `libx264`, `libx265`, and `libmp3lame`.

Before public distribution, publish the exact corresponding FFmpeg and
statically linked library sources and the build information for this executable,
or replace it with an encoder distribution whose corresponding-source package
has been completed. A link to a newer generic FFmpeg source archive is not
sufficient. This notice is an engineering compliance record, not legal advice;
have the final plan reviewed by a qualified licensing professional.

- FFmpeg legal information: https://ffmpeg.org/legal.html
- FFmpeg source: https://ffmpeg.org/download.html
- Binary provider: https://www.gyan.dev/ffmpeg/builds/
- SimpleCast build provenance: `BUILD_PROVENANCE_0.9.0.md`

## Other components

Licenses for Python, Tcl/Tk, NumPy, sounddevice/PortAudio, keyring, and other
packaged dependencies are retained in the corresponding folders under
`_internal`.
