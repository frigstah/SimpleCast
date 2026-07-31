# SimpleCast 0.9.0 beta 18

Beta 18 makes large station collections and program-audio selection much
easier to manage.

## New

- The Stations page can import server profiles from a user-selected BUTT
  configuration export.
- The importer reads only named Icecast and SHOUTcast server profiles and
  source passwords. It ignores BUTT audio, recording, DSP, metadata, and
  interface settings.
- A confirmation preview shows the number and names of supported profiles
  without displaying credentials.
- Exact duplicate profiles are skipped, and imported source passwords are
  stored through Windows Credential Manager.
- The default Program audio list now shows recognized browsers, karaoke
  programs, music services, and media players instead of every running
  process.
- An advanced setting can show every capturable process when an uncommon
  application is needed.
- Previously selected uncommon program sources remain available after the
  upgrade, and capture resolution still follows restarted process IDs.
- Favorite stars are directly clickable in the Stations table.
- The Stations page now labels the inclusion controls as multi-streaming and
  explains that every Included station receives the same live broadcast.

## Verification

- All 116 automated tests pass.
- The supplied BUTT export was parsed without exposing credentials: all 54
  profiles were recognized, consisting of 51 SHOUTcast and 3 Icecast
  profiles.
- Program filtering, advanced enumeration, saved uncommon sources, direct
  favorite interaction, duplicate imports, and first-import selection are
  covered by automated tests.
- On the development computer, the normal Program audio list reduced 35
  capturable process groups to the one recognized audio-capable application
  that was open.

The Windows beta artifacts are intentionally unsigned, so Windows may show a
SmartScreen or Smart App Control warning.
