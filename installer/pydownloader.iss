; Inno Setup 6 script of PyDownloader (spec 7.3).
; build.ps1 passes the version: iscc /DProductVersion=1.2.3 installer\pydownloader.iss

#define ProductVersion "0.0.0-dev"
; build.ps1 passes the four-part numeric version for the file properties.
#if !defined(VersionTuple)
#define VersionTuple "0.0.0.0"
#endif
#define AppName "PyDownloader"
#define ExeName "PyDownloader.exe"

[Setup]
AppId={{DD959C2D-4F33-43F3-A35D-3082096EF251}
AppName={#AppName}
AppVersion={#ProductVersion}
AppVerName={#AppName} {#ProductVersion}
AppPublisher=flynet
AppPublisherURL=https://github.com/flynet/pyDownloader
AppSupportURL=https://github.com/flynet/pyDownloader/issues
AppUpdatesURL=https://github.com/flynet/pyDownloader/releases
VersionInfoVersion={#VersionTuple}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
LicenseFile=..\NOTICE
OutputDir=..\dist\install
OutputBaseFilename={#AppName}-Setup-{#ProductVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#ExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardImageFile=assets\wizard.bmp
WizardSmallImageFile=assets\wizard-small.bmp
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=6.2sp2
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "eng"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\PyDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent runascurrentuser

[Code]
{ Settings and logs are removed only when the user asks for it (spec 7.3). }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataDir: String;
  LocalDataDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;
  if UninstallSilent then
    exit;
  if MsgBox('Удалить настройки, логи и профиль браузера {#AppName}?',
            mbConfirmation, MB_YESNO or MB_DEFBUTTON2) <> IDYES then
    exit;
  AppDataDir := ExpandConstant('{userappdata}\{#AppName}');
  LocalDataDir := ExpandConstant('{localappdata}\{#AppName}');
  DelTree(AppDataDir, True, True, True);
  DelTree(LocalDataDir, True, True, True);
end;
