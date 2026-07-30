# SimpleCast 0.9.0 beta 15

Beta 15 adds a compact broadcaster view and makes Windows minimization and
recording-folder access more predictable.

## New

- **Mini mode** switches the existing SimpleCast window to an approximately
  150×600 broadcaster with vertical L/R VU meters, live status and timer,
  Start/Stop Broadcast control, and the current server at the bottom.
- The mini server chooser opens downward below the mini window with a smooth
  transition and lists saved favorites first. Server switching remains locked
  while broadcasting.
- **Open folder** on the Recordings page creates the selected recording folder
  when necessary and opens it in Windows Explorer.
- The optional `--mini` launch argument starts directly in mini mode.

## Changed

- Pressing Minimize now keeps SimpleCast on the Windows taskbar by default.
- A new **Minimize makes the software go to tray** checkbox under
  **Settings → Window behavior** restores the earlier tray behavior when
  preferred.
- Existing configurations safely use taskbar minimization until the new option
  is explicitly enabled.

## Verification

- All 92 automated tests pass.
- The mini layout, taskbar/tray behavior, recording-folder action, server order,
  and packaged application are included in the beta release checks.

The Windows beta artifacts are intentionally unsigned, so Windows may show a
SmartScreen or Smart App Control warning.
