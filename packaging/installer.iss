; Inno Setup script  ->  <BuildRoot>\OrbSim-Setup-<version>.exe   (Windows installer; macOS uses packaging/build_mac.sh)
; build.ps1 passes /DBuildRoot=<folder> (the project's release folder, which is git-ignored).
#define MyAppName "OrbSim"
#define MyAppVersion "1.0.0"
#define MyAppExe "OrbSim.exe"
#define MyAppUrl "https://github.com/Chiyami1213/orbit-simulator"
#ifndef BuildRoot
  #define BuildRoot "..\release"
#endif

[Setup]
AppId={{A2F62B20-3219-4BE0-8C24-B09ED4496101}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisherURL={#MyAppUrl}
AppSupportURL={#MyAppUrl}/issues
AppUpdatesURL={#MyAppUrl}/releases
DefaultDirName={autopf}\{#MyAppName}
DisableDirPage=no
UsePreviousAppDir=yes
DisableReadyPage=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#BuildRoot}
OutputBaseFilename=OrbSim-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icons\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
InfoAfterFile=..\docs\after_install.txt
WizardImageFile=..\assets\installer\side-164.bmp,..\assets\installer\side-246.bmp,..\assets\installer\side-328.bmp,..\assets\installer\side-410.bmp
WizardSmallImageFile=..\assets\installer\small-55.bmp,..\assets\installer\small-83.bmp,..\assets\installer\small-110.bmp,..\assets\installer\small-138.bmp
WizardImageStretch=no
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startmenuicon"; Description: "Create a &Start Menu shortcut (with the help page and project page)"; GroupDescription: "Shortcuts:"
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#BuildRoot}\OrbSim\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\docs\help.html"; DestDir: "{app}\help"; Flags: ignoreversion

[INI]
Filename: "{app}\help\Project Page.url"; Section: "InternetShortcut"; Key: "URL"; String: "{#MyAppUrl}"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: startmenuicon
Name: "{autoprograms}\{#MyAppName} Help"; Filename: "{app}\help\help.html"; Tasks: startmenuicon
Name: "{autoprograms}\{#MyAppName} Project Page"; Filename: "{app}\help\Project Page.url"; Tasks: startmenuicon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\help\help.html"; Description: "Open the help page"; Flags: shellexec postinstall skipifsilent
Filename: "{#MyAppUrl}"; Description: "Open the project page on GitHub"; Flags: shellexec postinstall skipifsilent unchecked

[UninstallDelete]
Type: files; Name: "{app}\help\Project Page.url"
