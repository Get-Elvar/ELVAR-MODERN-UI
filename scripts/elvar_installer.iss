[Setup]
AppId={{D3B3A5E1-7B8A-4F9A-B2C1-D8E9F0A1B2C3}
AppName=Elvar
AppVersion=8.0
AppVerName=Elvar 8.0
AppPublisher=Ash
AppPublisherURL=https://github.com/HFFX4
AppSupportURL=https://github.com/HFFX4
AppUpdatesURL=https://github.com/HFFX4
DefaultDirName={localappdata}\Programs\ElvarByAsh
DefaultGroupName=Elvar
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=Elvar_v8.0_Setup
SetupIconFile=..\src\elvar_icon.ico
UninstallDisplayIcon={app}\elvar_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DirExistsWarning=no
CloseApplications=yes
RestartApplications=yes
PrivilegesRequired=lowest
VersionInfoVersion=8.0.0.0
VersionInfoCompany=Ash
VersionInfoDescription=Elvar Setup
VersionInfoProductName=Elvar

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Run Elvar on Windows startup"; GroupDescription: "Startup Options"; Flags: unchecked

[Files]
Source: "..\dist\Elvar\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\src\elvar_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Elvar"; Filename: "{app}\Elvar.exe"; IconFilename: "{app}\elvar_icon.ico"
Name: "{group}\{cm:UninstallProgram,Elvar}"; Filename: "{uninstallexe}"; IconFilename: "{app}\elvar_icon.ico"
Name: "{autodesktop}\Elvar"; Filename: "{app}\Elvar.exe"; IconFilename: "{app}\elvar_icon.ico"; Tasks: desktopicon
Name: "{userstartup}\Elvar"; Filename: "{app}\Elvar.exe"; IconFilename: "{app}\elvar_icon.ico"; Tasks: startupicon

[Run]
Filename: "{app}\Elvar.exe"; Description: "{cm:LaunchProgram,Elvar}"; Flags: nowait postinstall skipifsilent
