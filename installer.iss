; VoiceToText 安装脚本 — Inno Setup 7
; 编译: iscc installer.iss  ->  输出 dist\VoiceToText-Setup-1.0.0.exe
#define MyAppName "语音转文字 VoiceToText"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Local"
#define MyAppURL "https://github.com/"
#define MyAppExeName "VoiceToText.exe"

[Setup]
; 基本标识
AppId={{A1B2C3D4-E5F6-7890-ABCD-1234567890AB}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription=本地录音/文件转文字（线上识别）
VersionInfoProductName={#MyAppName}

; 安装位置：用户程序目录，免管理员 UAC
DefaultDirName={userpf}\VoiceToText
DefaultGroupName=VoiceToText
PrivilegesRequired=lowest
; 64 位系统以 64 位模式安装
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; 输出
OutputDir=D:\VoiceToText\dist
OutputBaseFilename=VoiceToText-Setup-{#MyAppVersion}
SetupIconFile=D:\VoiceToText\src\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 简体中文向导
LanguageDetectionMethod=uilanguage
ShowLanguageDialog=auto

[Languages]
Name: "ChineseSimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
; 如需英文可取消下一行注释，并改上面的 Name/MessagesFile
; Name: "English"; MessagesFile: "compiler:English.isl"

[Files]
; 主程序（文件夹版：exe + _internal 依赖，比单文件更不易被杀软误拦）
Source: "D:\VoiceToText\dist\VoiceToText\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式:"; Flags: unchecked

[Run]
; 安装完成可选启动
Filename: "{app}\{#MyAppExeName}"; Description: "启动语音转文字"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\config.json"
Type: filesandordirs; Name: "{app}\__pycache__"
