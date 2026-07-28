# SimpleCast public-beta release checklist

## Automated gate

- Run `.\release-check.ps1 -SoakSeconds 1800` during beta preparation.
- Run with `-RequireSigned` only when the release policy requires signing.
- Confirm all automated tests pass.
- Confirm the generated MP3 decodes without errors.
- Build both installer and portable packages.
- Launch and close the packaged application normally.
- Launch minimized through the Windows startup path and cancel automatic start.
- Record SHA-256 hashes for both packages.

## Windows and hardware matrix

- Windows 11, WASAPI shared mode
- Windows 10, WASAPI shared mode
- USB input disconnect and reconnect while live
- Default input removed before automatic startup
- Display scaling at 100%, 125%, 150%, and 200%
- Small supported window size and keyboard-only navigation

## Server matrix

- Icecast 2 over plain TCP
- Icecast 2 over TLS
- SHOUTcast 1 legacy source
- SHOUTcast 2 legacy-source compatibility with SID
- One unavailable destination while another remains online
- Router or internet interruption followed by reconnect
- Automatic and manual metadata on every server type

## Endurance

- 8-hour broadcast and local recording
- 24-hour broadcast with at least one forced reconnect
- 72-hour final candidate run
- Confirm bounded shutdown after every endurance run
- Inspect the support report and logs for errors or credentials

## Distribution gate

- Include `LICENSE` and identify SimpleCast as GPL-3.0-or-later.
- Include `TRADEMARKS.md` so official branding is distinct from code rights.
- Have counsel or a qualified reviewer confirm the FFmpeg distribution plan.
- Provide exact corresponding FFmpeg and statically linked library source plus
  build information alongside the network download.
- Retain all third-party notices and license files.
- For an unsigned beta, publish a prominent SmartScreen/Smart App Control
  warning, SHA-256 checksums, and build provenance.
- For a signed release, verify Authenticode, timestamping, and publisher details.
- Test clean install, upgrade, uninstall, and portable removal.
- Publish privacy information, known limitations, hashes, and support route.

## Beta sign-off

- Assign a release owner and date.
- Record every matrix result in `CERTIFICATION.md`.
- Mark unresolved defects with severity and workaround.
- Do not label the build production-ready while any distribution gate is open.
