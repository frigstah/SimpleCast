# SimpleCast 0.9.0 beta 14

Beta 14 fixes sound-test metering and makes the inactive optional program
source easier to understand.

## Fixes

- The VU meters now follow the actual captured and mixed signal throughout
  **Test my sound**.
- The live input meter resumes before the automatic processed-preview playback.
- When **Program audio** is set to **None**, its volume row explicitly says
  **off**, the value reads **Off**, and the slider and reset button are visibly
  muted and disabled.
- A saved program-volume setting returns unchanged when a program is selected
  again.

## Verification

- All 85 automated tests pass.
- A real Windows WASAPI test using a Behringer X-AIR recording device and Chrome
  program capture produced 200 live VU callbacks over two seconds at 48 kHz
  stereo.

The Windows beta artifacts are intentionally unsigned, so Windows may show a
SmartScreen or Smart App Control warning.
