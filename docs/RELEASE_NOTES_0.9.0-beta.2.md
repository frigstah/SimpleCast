# SimpleCast 0.9.0 beta 2

This prerelease introduces the approved modern SimpleCast dashboard while
keeping the streaming and recording engine from beta 1.

## Download

- `SimpleCast-Setup-0.9.0-beta.2-x64.exe` — recommended Windows installer
- `SimpleCast-Windows-x64-v0.9.0-beta.2-portable.zip` — portable version
- `SimpleCast-FFmpeg-Corresponding-Source-0.9.0.zip` — pinned FFmpeg source and
  build materials
- `SHA256SUMS-0.9.0-beta.2.txt` — verification hashes

First-time users should read `QUICK_START.md`, which is included in both Windows
packages and available in the repository.

## What is new

- Modern high-contrast dashboard with sidebar navigation
- Six favorite-station slots for fast switching
- Manual Artist and Title fields with a dedicated **SEND NOW PLAYING** action
- Vertical stereo meters and a more compact broadcast workflow
- Separate Recordings and Settings views
- Improved dropdown, focus, disabled, and selection contrast
- New footer attribution: “By Doversoft, thank you for trying it out”
- Beginner quick-start guide covering installation through going on air

## Existing broadcast features

- Windows WASAPI shared-mode, DirectSound, and MME audio capture
- Icecast 2, SHOUTcast 1, and SHOUTcast 2-compatible source connections
- MP3 streaming at 128, 192, or 320 kbps
- 32, 44.1, or 48 kHz output
- Voice, Music, Mixed content, and unprocessed audio modes
- Multiple simultaneous destinations with independent reconnect
- Optional local 320 kbps MP3 recording
- Optional watched-file metadata and Windows startup automation

## Verification

- All 49 automated tests pass.
- The source and packaged application open and close normally on Windows 11.
- The dashboard fits the tested Windows scaling with all primary controls
  visible.
- The packaged FFmpeg encoder and license record remain unchanged from beta 1.

## Important beta notes

- The binaries are intentionally unsigned. Windows SmartScreen or Smart App
  Control may warn or block the application.
- Verify downloads with `SHA256SUMS-0.9.0-beta.2.txt`.
- SHOUTcast 2 support uses the legacy-source compatibility protocol rather than
  native Ultravox 2.1.
- Do not run the server connection test against a mount or SID that is already
  receiving a live source.

## Feedback

Use **Settings → Export support report** and inspect the generated file before
sharing it. Do not post source passwords or other credentials publicly.

SimpleCast is GPL-3.0-or-later. See `LICENSE`, `TRADEMARKS.md`,
`THIRD_PARTY_NOTICES.md`, and `FFMPEG_SOURCE.md`.
