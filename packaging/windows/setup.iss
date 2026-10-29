; Local M1 validation build; clean-machine acceptance is recorded separately.
#ifndef BuildRoot
  #define BuildRoot "..\..\apps\desktop\build\windows\x64\runner\Release"
#endif
#ifndef WebViewInstaller
  #define WebViewInstaller "..\..\.local\release-tools\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
[Setup]
AppId={{64C69E18-79F7-47B8-82BC-6E6F39AA3A11}
AppName=StudyWorkbench
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\StudyWorkbench
DisableDirPage=no
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=StudyWorkbench-M1-setup
MinVersion=10.0.17763
AppMutex=Local\StudyWorkbench.Desktop
CloseApplications=yes
RestartApplications=no
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\study_workbench.exe
[Files]
Source: "{#BuildRoot}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "{#WebViewInstaller}"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebViewRuntime
[Icons]
Name: "{userprograms}\StudyWorkbench"; Filename: "{app}\study_workbench.exe"
; No UninstallDelete entries: personal data is retained by default.

[Run]
Filename: "{tmp}\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft WebView2 Runtime..."; Flags: waituntilterminated; Check: NeedsWebViewRuntime

[Code]
function NeedsWebViewRuntime: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := not ((RegQueryStringValue(HKLM32, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
                 (RegQueryStringValue(HKCU, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')));
end;
