# SimpleCast certification status

Updated: 2026-07-29

## Certified real environment

- Windows 11
- BEHRINGER X-AIR `IN 1-2`
- Windows WASAPI shared mode
- Icecast 2 at `radio.frig.tv:8169/stream`
- MP3 stereo, 48 kHz, 192 kbps

## Results

| Check | Result |
| --- | --- |
| DNS resolution | Pass |
| TCP source port | Pass |
| Icecast source credentials | Pass |
| WASAPI shared-mode capture | Pass |
| Public mount availability | Pass (`HTTP 200`, `audio/mpeg`) |
| External FFmpeg decode | Pass |
| Output format | Pass (MP3, stereo, 48 kHz, 192 kbps) |
| Requested stop | Pass |
| Encoder-failure detection | Pass |
| Automatic reconnect | Pass |
| Return to public mount after reconnect | Pass |

## Phase 9 automated beta checks

| Check | Result |
| --- | --- |
| Automated test suite | Pass (44 tests) |
| Processing-preview FFmpeg render | Pass (all four presets) |
| Readiness FFmpeg capability detection | Pass |
| Credential redaction regression test | Pass |
| Real-time synthetic MP3 encoder soak | Pass (15 seconds, 48 kHz stereo) |
| Mixed-content processing and limiter | Pass |
| Post-run full MP3 decode | Pass |
| Packaged Authenticode signature | Open — publisher certificate required |

The included soak tool supports longer 8, 24, and 72-hour runs. The short run
above validates the harness and decode check; it does not replace the required
real hardware/server endurance matrix.

## Defect found and resolved

Stopping FFmpeg while its PCM input pipe was being flushed could produce Windows
`Errno 22`. The stream still stopped, but the event was incorrectly logged as a
broadcast failure and Python could warn while finalizing the pipe. Version 0.3.4
handles a requested pipe closure normally and explicitly closes all encoder pipes.

## Still required

- Eight-hour, 24-hour, and 72-hour endurance runs
- Physical USB disconnect/reconnect during broadcast
- Router/internet interruption and recovery
- Windows 10 validation
- Real SHOUTcast 1 server validation
- Real SHOUTcast 2-compatible server validation
- Installer upgrade/uninstall validation
- Code signing and FFmpeg licensing review
- Choose and publish the SimpleCast application license
