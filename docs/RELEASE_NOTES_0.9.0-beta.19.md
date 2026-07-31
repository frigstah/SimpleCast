# SimpleCast 0.9.0 beta 19

Beta 19 improves window scaling and makes large station collections easier to
navigate.

## Fixed

- Studio Dark now measures the completed dashboard during startup and grows
  the window within the available screen area so all broadcast controls are
  visible without initial page scrolling when the display has enough room.
- The main page scrollbar now appears only when the current page genuinely
  needs it.
- The Stations page stays fixed while its station table scrolls independently.
- The station table has its own vertical scrollbar and dedicated mouse-wheel
  handling, including for large imported station collections.
- Custom title-bar dragging now uses Windows' native movement loop instead of
  repainting the window for every mouse event, reducing movement artifacts and
  preventing drag gestures from being confused with interface actions.
- Shutdown logging now records whether closing came from Windows, the title
  bar, mini mode, tray menu, updater, or a skin restart.

## Verification

- All 120 automated tests pass.
- Studio Dark was checked with the current 55-station configuration at
  2560 × 1440: the dashboard and Stations page both fit without an outer
  scrollbar, while the station table remains independently scrollable.
- Python bytecode compilation and the Windows release gate pass.

The Windows beta artifacts are intentionally unsigned, so Windows may show a
SmartScreen or Smart App Control warning.
