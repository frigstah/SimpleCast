# SimpleCast 0.9.0 beta 16

Beta 16 adds live listener information to the compact broadcaster.

## New

- Mini mode shows the current live listener count using the same Icecast and
  SHOUTcast statistics polling as the full interface.
- The indicator clearly distinguishes between checking, unavailable, and
  offline states.
- When broadcasting to multiple servers, available listener counts are added
  together. A trailing `+` indicates that at least one connected server has not
  returned a count.
- The taller mini-mode VU meters make better use of the available vertical
  space and bring the source label closer to the broadcast control.

## Verification

- All 95 automated tests pass.
- Listener totals, partial results, unavailable statistics, and the packaged
  mini layout are covered by the beta release checks.

The Windows beta artifacts are intentionally unsigned, so Windows may show a
SmartScreen or Smart App Control warning.
