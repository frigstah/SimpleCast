# SimpleCast 0.9.0 beta 3

Beta 3 adds real listener monitoring and a personal listener record for each
saved station.

## What is new

- Shows the latest live listener count for each on-air Icecast or SHOUTcast
  destination.
- Refreshes public listener statistics about every 10 seconds without blocking
  the interface or broadcast.
- Stores the highest listener count SimpleCast has observed separately for each
  saved station profile.
- Keeps personal records across restarts and station edits.
- Shows every station's personal high in **Manage stations**.
- Treats unavailable or blocked statistics as non-fatal; audio continues
  broadcasting normally.

## Supported statistics

- Icecast 2 public JSON statistics for the configured mount
- SHOUTcast 2 JSON statistics, with its compatible legacy endpoint as a fallback
- SHOUTcast 1 legacy listener statistics

Listener counts are sampled, so a short spike between refreshes may not be
recorded. Some hosting providers disable public statistics; those stations show
the listener count as unavailable.

## Verification

- All 57 automated tests pass.
- The source application opens and closes normally on Windows 11.

The binaries are intentionally unsigned. Windows SmartScreen or Smart App
Control may display a warning.
