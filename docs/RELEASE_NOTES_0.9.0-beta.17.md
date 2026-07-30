# SimpleCast 0.9.0 beta 17

Beta 17 adds a simple adjustable reverb effect for the recording device.

## New

- Microphone reverb can be turned on or off from the Dashboard.
- A 0–100% amount slider adjusts the room ambience while monitoring,
  recording, or broadcasting.
- The off state is explicit: the amount slider is disabled and reads `Off`.
- Reverb is applied before the microphone is mixed with optional program
  audio, so Chrome, Spotify, KaraFun, and other application audio stays dry.
- The effect is included consistently in the live meter, five-second sound
  test, local recordings, broadcast recordings, and live streams.
- Reverb settings are saved and restored between sessions and are available in
  every installed interface skin.

## Verification

- All 99 automated tests pass.
- DSP tests cover transparent bypass, the delayed reverb tail, and live amount
  changes.
- Configuration tests cover saved settings and safe amount validation.
- Ten seconds of stereo audio processes substantially faster than real time on
  the development system.

The Windows beta artifacts are intentionally unsigned, so Windows may show a
SmartScreen or Smart App Control warning.
