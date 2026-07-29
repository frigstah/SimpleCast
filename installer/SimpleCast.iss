#define MyAppName "SimpleCast"
#define MyAppVersion "0.9.0-beta.9"
#define MyAppPublisher "SimpleCast"
#define MyAppExeName "SimpleCast.exe"

[Setup]
AppId={{D57E7C73-2FC0-4F5F-B91A-D4D40F62D17A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SimpleCast
DefaultGroupName=SimpleCast
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=SimpleCast-Setup-{#MyAppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\simplecast.ico
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\SimpleCast\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SimpleCast"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\SimpleCast"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SimpleCast"; Flags: nowait postinstall skipifsilent
