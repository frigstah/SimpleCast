# SimpleCast

SimpleCast is a deliberately small Windows internet-radio encoder. The MVP focuses
on the shortest safe route to air:

1. Choose an audio input.
2. Record and play back a five-second sound check.
3. Add and test one or more Icecast or SHOUTcast servers.
4. Start broadcasting MP3 audio.

New to internet radio? Follow the [SimpleCast quick-start guide](QUICK_START.md).

## Run from source

Requirements:

- Windows 10 or 11
- Python 3.11+
- `sounddevice`, `numpy`, `keyring`, and the pinned FFmpeg build

```powershell
python -m pip install -r requirements.txt
.\prepare-ffmpeg.ps1
python main.py
```

## Build the Windows executable

```powershell
.\prepare-ffmpeg.ps1
.\build.ps1
```

The executable is written to `dist\SimpleCast\SimpleCast.exe`.
Keep the entire `dist\SimpleCast` folder together; the executable depends on the
adjacent `_internal` directory.

## MVP capabilities

- Windows microphone/line input selection
- Live stereo level meter with quiet and clipping guidance
- Five-second original/processed record-and-playback sound check
- Named Icecast 2, SHOUTcast 1, and SHOUTcast 2-compatible server profiles
- Simultaneous broadcasting to multiple included server profiles
- TLS, host, port, mount, username, password, and SHOUTcast SID support
- Password storage through Windows Credential Manager
- DNS, TCP, TLS, Icecast, and SHOUTcast source-login diagnostics
- MP3 quality presets at 128, 192, and 320 kbps
- Off, Voice, Music, and Mixed content processing with safety limiting
- Automatic reconnection with a bounded backoff
- Independent server connections so one failed destination does not stop others
- Manual now-playing metadata through the Icecast or SHOUTcast admin endpoint
- Automatic now-playing metadata from a watched text file
- Independent metadata retries and automatic resend after server reconnect
- Local 320 kbps MP3 recording during a broadcast or as a recording-only session
- Timestamped recording files with live duration and file-size status
- Optional Windows startup, minimized tray launch, and automatic broadcasting
- Cancellable startup countdown and saved-device readiness waiting
- Sanitized support-report export
- In-app beta-readiness check for audio, encoder, folders, stations, and signing
- Repeatable real-time MP3 encoder soak and release-check tooling

## Current limitations

- One audio input at a time
- MP3 only
- SHOUTcast 2 uses the DNAS legacy-source compatibility protocol, not native
  Ultravox 2.1
- No input mixing or Windows speaker-loopback capture yet
- The server test briefly opens and closes the selected mount to validate source
  credentials. Do not run it against an active mount or stream ID.

See `docs/ROADMAP.md` for the planned production sequence.

## 0.1.1

- Audio-device stop/start operations no longer run on the interface thread.
- USB/WASAPI capture now retries transient driver-open failures.
- Capture streams use immediate abort on shutdown to avoid driver drain hangs.

## 0.1.2

- Added a persistent 0–200% input-volume slider.
- Volume changes affect the live meter, sound test, and active broadcast.
- Standard is now MP3 at 192 kbps; High quality is MP3 at 320 kbps.

## 0.2.0 — Phase 3 reliability build

- Prevents Windows sleep while connecting, broadcasting, or reconnecting.
- Minimizes to a Windows tray icon with open/start/stop/exit controls.
- Re-resolves audio hardware after USB disconnect/reconnect.
- Automatically restores the last good configuration if the main file is damaged.
- Includes an Inno Setup installer definition and build script.

Desktop-audio loopback remains deferred. The installed PortAudio wrapper does not
offer WASAPI loopback, and the available Realtek Stereo Mix endpoint fails through
its WDM-KS driver on the current test machine.

## 0.3.0 — SHOUTcast support

- Added SHOUTcast 1 source broadcasting.
- Added SHOUTcast 2 DNAS legacy-source compatibility with SID and optional DJ
  username.
- Added SHOUTcast connection diagnostics and manual now-playing updates.
- SHOUTcast defaults to the conventional source port of the entered port plus one.
  Turn off “Use port + 1” when a hosting provider gives an explicit source port.
- Icecast profiles and saved settings remain backward compatible.

## 0.3.1 — Display scaling and sample rate

- The main window is DPI-aware and opens at the height required by its controls
  when the screen has room.
- A vertical scrollbar keeps every control reachable on smaller displays.
- Dialog windows automatically fit and center within the current display.
- Added selectable 32, 44.1, and 48 kHz outgoing sample rates.
- The selected sample rate is saved and FFmpeg resamples the broadcast output
  independently of the recording device's native rate.

## 0.3.2 — Bounded shutdown

- Closing hides the interface immediately instead of waiting on an audio driver.
- Broadcast, audio-device, and tray cleanup now run independently outside Tk's
  interface thread.
- A three-second graceful-cleanup limit and six-second process watchdog prevent
  faulty USB/MME drivers from leaving SimpleCast permanently unresponsive.
- Shutdown stages and timeouts are recorded in the application log.

## 0.3.3 — Selectable Windows audio system

- Added Automatic, Windows WASAPI shared-mode, DirectSound, and MME choices.
- Automatic prefers WASAPI, then DirectSound, then MME for the same named input.
- Explicit WASAPI selection never silently changes to a different audio system.
- WASAPI shared mode uses the endpoint's native sample rate and automatic buffer
  sizing for improved USB-interface compatibility.
- The interface shows the audio system that is actually active.
- Audio-system choices apply consistently to metering, sound tests, and broadcasts.
- Failed open attempts now include the audio system and device in the log.

## 0.3.4 — Real-server certification fixes

- Fixed the FFmpeg input-pipe race that produced `Errno 22` during a normal stop.
- Encoder pipes are now closed explicitly without reporting a requested stop as
  a broadcast failure.
- Certified the real Icecast path with X-AIR WASAPI shared-mode capture, public
  MP3 decoding, 48 kHz stereo output, 192 kbps, clean stop, and automatic
  reconnection after an injected encoder failure.

## 0.3.5 — Quality preset names

- `SL Standard` — MP3 at 128 kbps
- `SL MAX unsafe` — MP3 at 192 kbps
- `Recording` — MP3 at 320 kbps
- Existing `Standard` selections migrate to `SL MAX unsafe` to retain their
  previous 192 kbps behavior.

## 0.4.0 — Local recording

- Added local MP3 recording at 320 kbps using the selected outgoing sample rate.
- Broadcasts can be recorded automatically without changing their streaming
  bitrate.
- Added recording-only sessions that do not require a configured server.
- Added a persistent destination folder, timestamped filenames, elapsed time,
  and live file-size status.
- Recordings continue through server reconnects and are finalized safely when
  stopped or when SimpleCast closes.

## 0.5.0 — Multiple server broadcasting

- Added simultaneous broadcasting to multiple included Icecast and SHOUTcast
  stations from one shared Windows audio capture.
- Added an include/exclude control and visible checkbox state for every saved
  station.
- Added per-server connection status and a combined online count.
- Each server reconnects independently; a failed destination no longer
  interrupts servers that remain online.
- Now-playing metadata is sent to every active server.
- Automatic local recording still creates one 320 kbps file regardless of the
  number of streaming destinations.
- Existing single-server configurations automatically retain their previous
  destination as the sole included server.

## 0.6.0 — Automatic metadata

- Added automatic now-playing updates from a selected text file.
- The watcher ignores empty content and unchanged duplicate titles.
- Added an optional two-line format that converts artist and title lines into
  `Artist - Title`.
- Updates are sent to every active server, and only failed destinations retry.
- The current title is resent automatically when a server reconnects.
- File location, automatic mode, and formatting choice are saved.
- Manual title entry and sending remain available.

## 0.7.0 — Startup automation

- Added optional per-user startup with Windows.
- Added optional minimized startup through the notification-area tray.
- Added opt-in automatic broadcasting with a cancellable 5, 10, 30, or
  60 second countdown.
- Automatic startup waits for the saved USB/WASAPI audio device instead of
  silently selecting another input.
- Included stations and stored passwords are validated before connecting.
- Startup scheduling and problems are reported in the interface and tray.
- “Record every broadcast” also records automatically started broadcasts.
- All startup and automatic-broadcast options remain disabled by default.

## 0.8.0 — Simple audio processing

- Added Off / Original, Voice, Music, and Mixed content processing presets.
- Active presets use clear fixed processing followed by a safety peak limiter.
- The selected processing is applied consistently to every station and to
  local 320 kbps MP3 recordings.
- The five-second sound test now creates both original and processed previews
  with separate playback buttons.
- Added a live warning when the input clips before processing.
- The selected processing preset is saved and older configurations safely
  default to Off / Original.

## 0.9.0 — Public-beta readiness

- Added an in-app readiness check with pass, warning, and failure results.
- Verifies audio-device availability, folders, station configuration,
  passwords, MP3/limiter capabilities, audio format, and Authenticode status.
- Support reports now include the active audio configuration and redact common
  credential forms from copied log lines.
- Added a repeatable real-time encoder soak tool with full post-run MP3 decode.
- Added an automated release gate plus public-beta, privacy, licensing, signing,
  hardware, server, and endurance checklists.
- The GPL-3.0-or-later license and unsigned-beta policy are now documented.
  Qualified FFmpeg review and the long-duration external matrix remain gates.
- Added the SIMP Windows application and installer icon.

## Distribution note

The Windows package includes a pinned FFmpeg 7.1 LGPLv3 executable with its
license, immutable build record, and corresponding source materials. See
`THIRD_PARTY_NOTICES.md` and `FFMPEG_SOURCE.md`.

## License

Copyright (C) 2026 SimpleCast contributors.

SimpleCast is free software licensed under the GNU General Public License,
version 3 or (at your option) any later version. See `LICENSE`.

The SimpleCast and SIMP names and logo identify the official project. The GPL
does not grant trademark rights or permission to imply that a modified build is
an official SimpleCast release. See `TRADEMARKS.md`.

The current beta binaries are intentionally unsigned. Windows may display a
SmartScreen or Smart App Control warning; verify downloads using the published
SHA-256 checksums. Build details are recorded in
`docs/BUILD_PROVENANCE_0.9.0.md`.
