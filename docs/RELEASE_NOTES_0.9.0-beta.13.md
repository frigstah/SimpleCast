# SimpleCast 0.9.0 beta 13

Beta 13 adds direct audio capture from a chosen Windows program and mixes it
with the selected recording device for karaoke and live performance.

## What is new

- Keep a microphone or mixer selected under **Recording device**, then choose
  an optional second source under **Program audio**.
- Capture Chrome, Spotify, KaraFun, VLC, or another running program through
  Windows WASAPI process loopback.
- Child-process audio is included, which supports multi-process applications
  such as web browsers.
- Recording-device and program audio are mixed into one stereo signal before
  metering, processing, sound testing, recording, and multi-server broadcast.
- Independent 0–200% volume controls make it easy to balance a singer's
  microphone against karaoke backing music while live.
- Saved programs are rediscovered by executable path when their process ID
  changes.
- The interface explains when a saved program is closed or the Windows version
  does not support per-process capture.

## Compatibility

- Program audio requires Windows build 20348 or newer; Windows 11 is
  recommended.
- A selected program must remain running. If it closes, SimpleCast reports the
  stopped source instead of continuing an empty broadcast.
- DRM-protected playback may return silence.

## Verification

- All automated tests pass.
- The native x64 capture helper builds with Visual C++ and the Windows SDK.
- Real process-loopback PCM capture was verified at 44.1 kHz stereo.
- Automated PCM tests verify stereo addition, mono microphone duplication, and
  safe clipping at full scale.

The binaries are intentionally unsigned. Windows SmartScreen or Smart App
Control may display a warning.
