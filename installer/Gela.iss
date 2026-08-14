#define MyAppName "Gela Voice Assistant"
#define MyAppVersion "1.6.0"
#define MyAppPublisher "Softcurse Systems"
#define MyAppURL "https://softcurse-website.pages.dev/"
#define MyAppExeName "Gela.exe"

[Setup]
AppId={{6B0B790B-621D-49B2-AF7E-A9C4256D34C8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\Gela
DefaultGroupName=Gela Voice Assistant
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\release
OutputBaseFilename=Gela-Setup-{#MyAppVersion}-x64
SetupIconFile=..\assets\icons\gela_tray.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
AppMutex=Local\GelaVoiceAssistant
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductName={#MyAppName}
VersionInfoDescription=Install {#MyAppName}
VersionInfoCompany={#MyAppPublisher}

[Tasks]
Name: "startup"; Description: "Start Gela automatically when I sign in"; GroupDescription: "Startup:"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Gela\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Gela Voice Assistant"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall Gela"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Gela Voice Assistant"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\Simple Voice Assistant"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Start Gela"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{userstartup}\Simple Voice Assistant.lnk"

[Code]
var
  RemovePersonalData: Boolean;

function InitializeUninstall(): Boolean;
begin
  RemovePersonalData :=
    MsgBox(
      'Remove personal Gela data too?' + #13#10 + #13#10 +
      'Choose No to keep settings, aliases, application profiles, routines, and logs for a future update or reinstall.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and RemovePersonalData then
    DelTree(ExpandConstant('{localappdata}\Gela'), True, True, True);
end;
