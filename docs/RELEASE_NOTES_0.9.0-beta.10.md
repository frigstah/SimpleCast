# SimpleCast 0.9.0 beta 10

Beta 10 completes the integrated Windows frame introduced with Studio Dark.

## What is new

- Removed the remaining pale Windows 11 DWM border from the top and rounded
  corners of the SimpleCast window.
- Replaced the native resize frame with an invisible, themed edge and corner
  resize area inside the SimpleCast window.
- Dragging, edge and corner resizing, minimize, maximize/restore, close, taskbar
  behavior, and the themed title bar are preserved.

## Verification

- All 74 automated tests pass.
- The borderless Win32 style flags are covered by a Windows-frame regression
  test.
- Packaged-window pixel capture confirms that the native pale top strip is no
  longer drawn.

The binaries are intentionally unsigned. Windows SmartScreen or Smart App
Control may display a warning.
