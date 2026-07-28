# SimpleCast roadmap

## 0.1 — MVP

- Input-device capture and levels
- Five-second sound check
- Icecast profile management and diagnostics
- MP3 broadcast with reconnect
- Manual now-playing metadata
- Windows executable build

## 0.2 — Pilot hardening

- Windows speaker-loopback capture
- Device hot-plug recovery
- 72-hour soak tests
- Windows sleep prevention while live
- Automatic configuration backup
- Tray controls
- Installer definition (code signing still requires a publisher certificate)
- Better Icecast compatibility tests across hosting providers

## 0.3 — Phase 3

- SHOUTcast 1 source protocol
- SHOUTcast 2 DNAS legacy-source compatibility
- SHOUTcast SID and optional DJ username
- SHOUTcast connection tests and now-playing metadata
- DPI-aware, screen-fitting Windows interface
- Selectable 32, 44.1, and 48 kHz stream output
- Bounded asynchronous shutdown for unresponsive Windows audio drivers
- Explicit WASAPI shared-mode, DirectSound, and MME selection with active-API status

## 0.4 — Phase 4

- Local MP3 recording at 320 kbps
- Record the broadcast audio or record without connecting to a server
- Persistent recording folder and automatic timestamped filenames
- Live recording duration and file-size status
- Safe MP3 finalization on stop, close, and bounded shutdown
- Recording continues while a broadcast reconnects

## 0.5 — Phase 5

- Multiple simultaneous Icecast and SHOUTcast destinations
- One shared Windows audio capture feeding independent server encoders
- Per-server connection state and combined online count
- Independent reconnect so one failed server does not interrupt the others
- Now-playing metadata sent to every active server
- One local recording regardless of the number of destinations
- Backward-compatible migration of existing single-server configurations

## 0.6 — Phase 6

- Automatic now-playing metadata from a watched text file
- As-written and two-line `Artist - Title` formatting
- Empty and duplicate title suppression
- Delivery to every currently active server
- Independent retry for failed metadata destinations
- Automatic resend when a server reconnects
- Persistent file, enable/disable, and formatting settings
- Manual now-playing entry remains available

## 0.7 — Phase 7

- Optional per-user Windows startup registration
- Optional minimized startup through the tray
- Opt-in automatic broadcasting with a visible cancellable countdown
- Configurable 5, 10, 30, or 60 second startup delay
- Saved-device safety: never silently switch to a different input
- Automatic wait/retry while a saved USB/WASAPI device is unavailable
- Included-server and password validation before automatic broadcast
- Tray notifications for scheduled starts and problems
- Existing “Record every broadcast” option applies to automatic starts

## 0.8 — Phase 8

- Simple Off / Original, Voice, Music, and Mixed content processing presets
- Voice-focused filtering and compression
- Gentle music and balanced mixed-content level control
- Safety peak limiter on every active processing preset
- Identical processing for every stream and local 320 kbps recording
- Five-second original/processed sound-test comparison
- Live warning when the captured input clips before processing
- Persistent processing selection with safe migration of older configurations

## 0.9 — Current Phase 9: public-beta readiness

- In-app beta-readiness check with clear pass, warning, and failure results
- Verification of audio devices, writable folders, station credentials, and format
- Bundled FFmpeg MP3 encoder and safety-limiter capability check
- Authenticode status check for packaged executables
- Credential-redacted support reports with complete audio configuration
- Repeatable real-time encoder soak tool with post-run decode validation
- Automated release gate for versions, tests, compilation, soak, and signing status
- Public-beta release checklist and local-data privacy documentation

## External release gates

- GPL-3.0-or-later application license and branding policy (complete)
- Complete qualified FFmpeg distribution/licensing review
- Publish exact corresponding source for the bundled FFmpeg/static libraries
- Unsigned-beta warnings, checksums, and build provenance (complete)
- Optional publisher signing for a later release
- Complete Windows/server/hardware matrix and 8/24/72-hour field runs
- Public beta distribution and feedback

## Next product work

- AAC and Opus after codec review

## Later

- Native SHOUTcast Ultravox 2.1 support if licensing and interoperability allow it
- Microphone plus computer-audio mixing
- Automation metadata over TCP/UDP
- Failover server and remote alerts
- VST3 and detailed broadcast processing
