# SimpleCast 0.9.0 beta 5

Beta 5 adds secure, user-initiated update checks through the official SimpleCast
GitHub releases.

## What is new

- A **Software updates** section under Settings.
- A **Check for updates** button; SimpleCast never checks silently.
- Beta-release discovery while SimpleCast remains in beta.
- Version and release-note confirmation before downloading.
- Download progress in the Settings page.
- Installer size and SHA-256 verification against GitHub's release-asset
  metadata.
- A second confirmation before the verified installer is launched.
- Installation is blocked while broadcasting or recording.
- The existing installer upgrades SimpleCast in place and preserves saved
  stations, passwords, settings, favorites, and listener records.

Portable users can use the same button. Launching the downloaded installer
creates or upgrades the normal per-user Windows installation; it does not
overwrite a running portable folder.

## Privacy and safety

- Update checks occur only after a button click.
- Requests go only to the public GitHub API and the pinned
  `frigstah/SimpleCast` release path.
- Station details and credentials are never included.
- Downloads that do not match GitHub's expected size and SHA-256 digest are
  deleted and never launched.

## Verification

- All 66 automated tests pass.
- Live GitHub testing correctly recognized beta 4 as current.
- Live GitHub testing offered beta 4, its exact installer, and its published
  digest to a simulated beta 3 installation.

The binaries are intentionally unsigned. Windows SmartScreen or Smart App
Control may display a warning.
