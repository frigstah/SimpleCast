# Third-party notices

The packaged SimpleCast beta includes third-party components. SimpleCast itself
is licensed under GNU GPL version 3 or later; see `LICENSE`.

## FFmpeg

The packaged encoder is BtbN's reproducible FFmpeg 7.1 LGPL build:
`ffmpeg-n7.1.5-10-g2aefd64d48-win64-lgpl-7.1`. SimpleCast invokes it as
a separate executable. Its version and configuration can be inspected with:

```powershell
.\_internal\vendor\ffmpeg\ffmpeg.exe -version
```

The packaged `COMPONENT_HASHES.txt` records the exact included FFmpeg binary:

- Filename: `ffmpeg.exe`
- SHA-256:
  `0C3883925185BDAB1454C896910E4CF77CB9A087AC6D2D264F803D35493B5360`
- Configuration includes `--enable-version3`, `--disable-gpl`,
  `--disable-nonfree`, static linking, and `libmp3lame`.
- FFmpeg source revision: `2aefd64d48`
- BtbN build-system revision:
  `8c736b2d6fe5da2a10a8896d01e53bfb0ca4f665`
- Effective license: GNU Lesser General Public License version 3

The FFmpeg license is retained under `_internal\vendor\ffmpeg\LICENSE.txt`.
Exact source and build materials accompany the release as
`SimpleCast-FFmpeg-Corresponding-Source-0.9.0.zip`.

- FFmpeg legal information: https://ffmpeg.org/legal.html
- Pinned build scripts:
  https://github.com/BtbN/FFmpeg-Builds/tree/autobuild-2026-07-28-13-32
- Pinned FFmpeg source:
  https://github.com/FFmpeg/FFmpeg/tree/2aefd64d48
- SimpleCast build provenance: `BUILD_PROVENANCE_0.9.0.md`
- Full encoder source record: `FFMPEG_SOURCE.md`

## Other components

Licenses for Python, Tcl/Tk, NumPy, sounddevice/PortAudio, keyring, and other
packaged dependencies are retained in the corresponding folders under
`_internal`.
