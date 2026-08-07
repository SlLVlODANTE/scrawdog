; Inno Setup script для scrawdog
; Скомпилировать: ISCC.exe installer.iss

[Setup]
AppName=scrawdog
AppVersion=1.0
AppPublisher=разраб егор20
AppId={{5A8C1F2E-3D7B-4E9A-8F1C-9B2D4A6F5678}
DefaultDirName={autopf}\scrawdog
DefaultGroupName=scrawdog
UninstallDisplayIcon={app}\scrawdog.exe
OutputDir=installer
OutputBaseFilename=scrawdog Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DisableReadyPage=no
ShowLanguageDialog=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\scrawdog.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\scrawdog"; Filename: "{app}\scrawdog.exe"
Name: "{group}\{cm:UninstallProgram,scrawdog}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\scrawdog"; Filename: "{app}\scrawdog.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\scrawdog.exe"; Description: "{cm:LaunchProgram,scrawdog}"; Flags: nowait postinstall skipifsilent
