# SimpleCast 0.9.0 beta 20

Beta 20 is a corrective release for the window-drag crash introduced in Beta
19. It also makes packaged builds more resilient and gives first-time radio
and karaoke broadcasters a clearer route into SimpleCast.

## Critical fix

- Removed the native Windows title-bar movement call introduced in Beta 19.
  On affected systems that path could terminate `SimpleCast.exe` inside
  `ucrtbase.dll` with exception code `0xc0000409` while the window was being
  dragged.
- Custom title-bar movement is once again managed by Tk. Mouse movement is
  coalesced and applied at most about 60 times per second, with the final
  position applied on release. This avoids the unsafe native message path
  without returning to unthrottled repainting.
- The same safe movement path is used by the complete interface and mini mode.

## Packaging and startup resilience

- The SIMP brand image now falls back from the bundled PNG to the bundled ICO
  and finally to a generated radio-style icon. A missing or quarantined PNG can
  no longer prevent SimpleCast from opening.
- The Windows build now fails before packaging if the executable, PNG, ICO,
  FFmpeg encoder, or process-loopback helper is missing or empty.

## Beginner experience

- The SimpleCast website now offers separate, plain-language setup paths for
  internet radio and karaoke users.
- A three-check pre-broadcast board explains when sound, station, and quality
  are ready, and a short glossary explains mount, SID, and bitrate.
- The Support section includes the requested Urban Harvy quality-control
  credit.

## Verification

- All 124 automated tests pass.
- The 15-second 48 kHz stereo encoder soak and decode check pass.
- Python bytecode compilation and the Windows release gate pass.
- The website onboarding section was visually checked at desktop size and has
  responsive tablet and mobile layouts.

The Windows beta artifacts are intentionally unsigned, so Windows may show a
SmartScreen or Smart App Control warning.
