; M0 template. M1 must validate this on a clean Windows VM before release.
#define BuildRoot "..\..\apps\desktop\build\windows\x64\runner\Release"
[Setup]
AppId={{64C69E18-79F7-47B8-82BC-6E6F39AA3A11}
AppName=StudyWorkbench
AppVersion=0.0.1
DefaultDirName={localappdata}\Programs\StudyWorkbench
DisableDirPage=no
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=StudyWorkbench-M0-setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\study_workbench.exe
[Files]
Source: "{#BuildRoot}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "..\..\dist\study_backend\*"; DestDir: "{app}\backend"; Flags: recursesubdirs createallsubdirs
[Icons]
Name: "{userprograms}\StudyWorkbench"; Filename: "{app}\study_workbench.exe"
; No UninstallDelete entries: personal data is retained by default.
