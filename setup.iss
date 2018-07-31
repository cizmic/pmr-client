; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

#define MyAppName "PMR Launcher"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Julian Cizmic"
#define MyAppURL "http://getpmr.com/"
#define MyAppExeName "pmrclient.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{D422205D-A9E2-488D-9491-341F34B9650F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
;AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userdocs}\SimCity 4\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=C:\Users\Julian\Desktop\mak sc4\PMR Client\pmrlauncher-1.0\License.txt
OutputDir=C:\Users\Julian\Desktop\mak sc4\PMR Client\setupbuilds
OutputBaseFilename=PMR Setup
SetupIconFile=C:\Users\Julian\Desktop\mak sc4\PMR Client\pmrlauncher-1.0\resources\icon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "C:\Users\Julian\Desktop\mak sc4\PMR Client\pmrlauncher-1.0\pmrclient.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\Julian\Desktop\mak sc4\PMR Client\pmrlauncher-1.0\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[InstallDelete]
Type: filesandordirs; Name: "{userdocs}\SimCity 4\_PMR\Regions"
Type: filesandordirs; Name: "{userdocs}\SimCity 4\_PMR\Plugins"
Type: filesandordirs; Name: "{userdocs}\SimCity 4\_PMR\PMRSalvage"
Type: filesandordirs; Name: "{userdocs}\SimCity 4\_PMR\PMRCache"
Type: filesandordirs; Name: "{userdocs}\SimCity 4\_PMR\PMRPluginsCache"

[Icons]
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\pmrclient.exe"; IconFilename: "{app}\resources\icon.ico"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\pmrclient.exe"; IconFilename: "{app}\resources\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
