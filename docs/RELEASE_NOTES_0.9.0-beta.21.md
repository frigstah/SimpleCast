# SimpleCast 0.9.0 beta 21

Beta 21 improves window stability and corrects the bitrate information sent to
Icecast servers.

## Safer Windows frame

- Restored the standard Windows-owned title bar, movement, resizing, minimize,
  maximize, and close behavior. SimpleCast no longer implements these fragile
  operations itself.
- Uses Windows DWM colors to blend the native title bar with the selected
  SimpleCast skin while retaining standard Windows behavior.
- Removes the custom drag and resize path that could cause visual artifacts or
  terminate the application while the window was being moved.
- Keeps mini mode accessible through a dedicated MINI button and preserves its
  compact layout using the same native frame.

## Correct Icecast stream information

- Added a dedicated Icecast source uploader instead of relying on FFmpeg's
  limited Icecast header support.
- Icecast now receives the selected bitrate, output sample rate, and channel
  count through `Ice-Bitrate`, `Ice-Samplerate`, `Ice-Channels`, and
  `Ice-Audio-Info` source headers.
- The server should now report 128, 192, or 320 kbps in agreement with the
  selected SimpleCast quality preset.
- The new upload path supports normal and multistream broadcasts, TLS,
  authentication, reconnecting, and existing station information.

## Verification

- All 127 automated tests pass.
- The 15-second 48 kHz stereo encoder soak and decode check pass.
- The packaged Windows application builds successfully.
- A native-frame smoke test is included for checking packaged builds without
  replacing Windows' own window-management behavior.

The Windows beta artifacts are intentionally unsigned, so Windows may show a
SmartScreen or Smart App Control warning.
