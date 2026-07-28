# SimpleCast privacy

SimpleCast does not include analytics, advertising, crash-report uploads, or
telemetry. It does not send configuration or support information to SimpleCast.

The application makes network connections only when needed for user-configured
radio servers, connection tests, streaming, and now-playing metadata. Server
passwords are stored through Windows Credential Manager. Other settings are
stored locally in the user's SimpleCast configuration folder.

Support reports are created only when the user chooses an export location.
They include technical settings, sanitized station details, and recent log
lines. Password fields and common credential forms in log text are redacted.
Users should still review a report before sharing it.

Local recordings remain in the folder selected by the user. Removing the
portable application does not remove recordings, settings, or Windows
Credential Manager entries.
