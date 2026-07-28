# Third-party notices

The packaged SimpleCast MVP includes third-party components.

## FFmpeg

The packaged FFmpeg 7.1 binary is the gyan.dev essentials build configured with
GPLv3 components, including LAME. Its version/configuration can be inspected with:

```powershell
.\_internal\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe -version
```

The packaged application retains the `imageio-ffmpeg` license and binary README
under `_internal\imageio_ffmpeg`. Review FFmpeg's GPL and source-distribution
requirements before distributing SimpleCast commercially.

Before public distribution, record the exact FFmpeg binary hash and publish or
offer the corresponding source for that exact build as required by the selected
distribution method. This notice is an engineering checklist, not legal advice;
have the final plan reviewed by a qualified licensing professional.
The packaged `COMPONENT_HASHES.txt` records the exact included FFmpeg binary.

- FFmpeg legal information: https://ffmpeg.org/legal.html
- FFmpeg source: https://ffmpeg.org/download.html
- Binary provider: https://www.gyan.dev/ffmpeg/builds/

## Other components

Licenses for Python, Tcl/Tk, NumPy, sounddevice/PortAudio, keyring, and other
packaged dependencies are retained in the corresponding folders under
`_internal`.
