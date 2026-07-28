# Bundled FFmpeg source and license

SimpleCast invokes FFmpeg as a separate executable. The Windows beta bundles the
following reproducible LGPL build:

- Provider: BtbN/FFmpeg-Builds
- Build: `ffmpeg-n7.1.5-10-g2aefd64d48-win64-lgpl-7.1`
- Immutable release:
  `autobuild-2026-07-28-13-32`
- Release archive SHA-256:
  `C01DDCB52800391F546CC519D465997A6A75454A6483C47CEB01325B19F65711`
- Bundled `ffmpeg.exe` SHA-256:
  `0C3883925185BDAB1454C896910E4CF77CB9A087AC6D2D264F803D35493B5360`
- FFmpeg revision:
  `2aefd64d48`
- BtbN build-system revision:
  `8c736b2d6fe5da2a10a8896d01e53bfb0ca4f665`
- Build variant: `win64 lgpl 7.1`
- Effective FFmpeg license: GNU Lesser General Public License version 3

The exact build scripts pin the source revision for FFmpeg and every statically
included dependency:

- Build scripts:
  https://github.com/BtbN/FFmpeg-Builds/tree/autobuild-2026-07-28-13-32
- FFmpeg source:
  https://github.com/FFmpeg/FFmpeg/tree/2aefd64d48
- Binary release:
  https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-07-28-13-32

The release includes `SimpleCast-FFmpeg-Corresponding-Source-0.9.0.zip`. It
contains the pinned BtbN build scripts, the FFmpeg source revision, and a source
manifest for the build's external dependencies. The upstream repositories and
revisions are also retained in the pinned `scripts.d` files.

The FFmpeg LGPLv3 license text is included as
`vendor\ffmpeg\LICENSE.txt` in source builds and as
`vendor\ffmpeg\LICENSE.txt` inside packaged builds. Nothing in the SimpleCast
license or documentation limits rights granted by the FFmpeg license.
