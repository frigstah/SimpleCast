# SimpleCast 0.9.0 beta 8

Beta 8 refines Studio Dark, station management, broadcast stopping, branding,
and the Windows frame.

## What is new

- Studio Dark is now the default skin for new installations. Existing saved
  skin choices are preserved.
- A new **Settings → Broadcast controls** checkbox chooses whether Stop
  Broadcast asks for confirmation or ends the stream immediately.
- **Manage stations** now opens the integrated Stations page instead of a
  separate manager window.
- The Stations navigation tab contains favorites, multi-destination inclusion,
  editing, connection testing, listener highs, and deletion.
- In Studio Dark, Input volume and Processing are placed beneath the stereo VU
  meters in the Signal panel.
- The former **On air** panel is now **Sound quality & Info**.
- The SIMP icon replaces the written SIMP abbreviation in the main navigation.
- The native white title strip is replaced by a themed SimpleCast frame with
  drag, minimize, maximize/restore, close, native resizing, and taskbar support.
- The footer now reads:
  `Software devoloped by BenDover Sporg - Please provide feedback in IM`.

## Verification

- All 72 automated tests pass.
- All four skins opened with the integrated title bar and SIMP image, displayed
  six favorites, opened the Stations page with six test rows, maximized,
  restored, stopped without prompting when configured, and closed cleanly.
- Studio Dark placed both Input volume and Processing inside the Signal panel.

The binaries are intentionally unsigned. Windows SmartScreen or Smart App
Control may display a warning.
