; Inno Setup script для SC Mini
; Скомпилировать: ISCC.exe installer.iss

[Setup]
AppName=EGoRCL0uD
AppVersion=1.0
AppPublisher=разраб егор20
AppId={{8E3F1A8C-2B4D-4F8A-9E1C-7D5B3A9F1234}
DefaultDirName={autopf}\EGoRCL0uD
DefaultGroupName=EGoRCL0uD
UninstallDisplayIcon={app}\EGoRCL0uD.exe
OutputDir=installer
OutputBaseFilename=EGoRCL0uD Setup
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
Source: "dist\EGoRCL0uD.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\EGoRCL0uD"; Filename: "{app}\EGoRCL0uD.exe"
Name: "{group}\{cm:UninstallProgram,EGoRCL0uD}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\EGoRCL0uD"; Filename: "{app}\EGoRCL0uD.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EGoRCL0uD.exe"; Description: "{cm:LaunchProgram,EGoRCL0uD}"; Flags: nowait postinstall skipifsilent
