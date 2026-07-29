# SimpleCast 0.9.0 beta 9

Beta 9 fixes live listener monitoring on legacy SHOUTcast servers.

## What is new

- SHOUTcast statistics requests now use a browser-compatible client identity.
- This prevents older SHOUTcast 1 servers from incorrectly routing the
  `/7.html` statistics request to an audio endpoint and returning an invalid
  `ICY 404 Resource Not Found` response.
- SHOUTcast 2 JSON statistics and Icecast listener monitoring are unchanged.

## Verification

- All 73 automated tests pass.
- The fix was verified against three configured SHOUTcast stations: one modern
  JSON-capable server and two legacy `/7.html` servers.
- The observed live listener counts were successfully read from all three.

The binaries are intentionally unsigned. Windows SmartScreen or Smart App
Control may display a warning.
