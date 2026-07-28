# SimpleCast 0.9.0 beta

This is the first public-beta candidate for SimpleCast, a deliberately simple
Windows internet-radio streamer for Icecast and SHOUTcast-compatible servers.

## Download

- `SimpleCast-Setup-0.9.0-x64.exe` — per-user Windows installer
- `SimpleCast-Windows-x64-v0.9.0-beta-portable.zip` — portable version
- `SHA256SUMS-0.9.0.txt` — download verification hashes

## Highlights

- Windows WASAPI shared-mode, DirectSound, and MME input selection
- Live stereo meters and a 0–200% input-volume control
- Five-second original/processed sound comparison
- Off / Original, Voice, Music, and Mixed content processing presets
- MP3 streaming at 128, 192, or 320 kbps and 32, 44.1, or 48 kHz
- Multiple simultaneous Icecast, SHOUTcast 1, and SHOUTcast 2-compatible servers
- Independent reconnect for every destination
- Manual and watched-file now-playing metadata
- Optional local 320 kbps MP3 recording
- Optional Windows startup and automatic broadcast countdown
- In-app beta-readiness and credential-redacted support reports
- New SIMP application, taskbar, shortcut, and installer icon

## Verification

- 44 automated tests pass.
- Every processing preset renders and decodes through bundled FFmpeg.
- A real-time 48 kHz stereo encoder soak and full-file decode pass.
- The packaged application opens through WASAPI and closes cleanly on the
  certified Windows 11 test system.

## Important beta notes

- This beta is not digitally signed. Windows SmartScreen may display an
  unrecognized-app warning. Verify the SHA-256 hash before running it.
- Windows 11 is the currently certified environment. Windows 10 testing remains
  part of the beta matrix.
- SHOUTcast 2 uses the legacy-source compatibility protocol, not native
  Ultravox 2.1.
- FFmpeg and other third-party notices are included in the package.
- Do not use the server connection test against an already active mount or
  stream ID because it briefly opens a source connection.

## Feedback

When reporting a problem, use **Export support report** in SimpleCast and review
the generated text before attaching it. Password fields and common credential
forms are redacted, but users should always inspect diagnostic files before
sharing them publicly.
