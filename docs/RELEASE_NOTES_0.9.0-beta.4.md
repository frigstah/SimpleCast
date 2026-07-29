# SimpleCast 0.9.0 beta 4

Beta 4 fixes live listener monitoring for older Icecast servers.

## What is fixed

- SimpleCast still uses Icecast's JSON statistics endpoint when available.
- If that endpoint is missing or unusable, SimpleCast now automatically reads
  the standard `status2.xsl` CSV statistics endpoint.
- The configured mount is selected exactly when a server hosts multiple
  streams.
- CSV quoting and byte-order marks are handled safely.
- Listener-stat compatibility failures remain non-fatal and never interrupt
  audio broadcasting.

This specifically supports Icecast installations that return `404` for
`status-json.xsl` but provide `status2.xsl`.

## Verification

- All 59 automated tests pass.
- Regression tests cover the exact legacy Icecast status header and mount
  structure observed during diagnosis.

The binaries are intentionally unsigned. Windows SmartScreen or Smart App
Control may display a warning.
