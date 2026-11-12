; Voice Typer installer (Inno Setup 6.7+). Built by build.ps1, which passes /DAppVersion=x.y.z.
; Per-user install: no administrator rights needed (works on locked-down work PCs).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Voice Typer"
#define AppExe "Voice Typer.exe"

[Setup]
AppId={{7C4E2B9A-5D13-4F8E-9A6C-3B1D0E7F42A5}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
AppComments=Dictée vocale 100 % locale
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} - installation
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=no
DisableWelcomePage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=VoiceTyperSetup-{#AppVersion}
SetupIconFile=build_assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
; Look: modern wizard, Windows 11 styling, follows the system light/dark mode
WizardStyle=modern dynamic windows11
; The logo (make_assets.py): one image per DPI, Setup picks the closest. Same images in dark mode.
WizardImageFile=build_assets\wizard_*.bmp
WizardImageFileDynamicDark=build_assets\wizard_*.bmp
WizardSmallImageFile=build_assets\small_*.png
WizardSmallImageFileDynamicDark=build_assets\small_*.png
; Close a running copy before updating it (same mutex as voice_typer/app.py)
AppMutex=VoiceTyper.SingleInstance
CloseApplications=yes
RestartApplications=no
; Fast enough to rebuild often, still a small download
Compression=lzma2/normal
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
ShowLanguageDialog=auto
LanguageDetectionMethod=uilanguage

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
fr.WelcomeLabel2=Voice Typer va être installé sur votre ordinateur.%n%nMaintenez un raccourci, parlez, et votre texte s'écrit tout seul dans n'importe quelle application. La reconnaissance vocale et l'IA d'écriture fonctionnent entièrement sur votre PC : rien n'est envoyé sur Internet.%n%nAucun droit administrateur n'est nécessaire.
en.WelcomeLabel2=Voice Typer will be installed on your computer.%n%nHold a shortcut, speak, and your words are typed into any app. Speech recognition and the writing AI run entirely on your PC: nothing is sent to the Internet.%n%nNo administrator rights needed.
fr.FinishedLabel=Voice Typer est installé.%n%nAu premier lancement, un court assistant vous aide à choisir votre langue, à télécharger le modèle de voix adapté à votre ordinateur et à tester votre micro.
en.FinishedLabel=Voice Typer is installed.%n%nOn first launch, a short assistant helps you pick your language, download the right voice model for your computer and test your microphone.

[CustomMessages]
fr.TaskDesktop=Créer un raccourci sur le Bureau
en.TaskDesktop=Create a desktop shortcut
fr.TaskAutostart=Démarrer Voice Typer avec Windows (recommandé)
en.TaskAutostart=Start Voice Typer with Windows (recommended)
fr.TaskGroup=Options :
en.TaskGroup=Options:
fr.LaunchNow=Lancer Voice Typer maintenant
en.LaunchNow=Launch Voice Typer now
fr.AskKeepData=Voulez-vous aussi supprimer vos réglages, votre historique et les modèles IA téléchargés ?%n%nChoisissez « Non » si vous comptez réinstaller Voice Typer : vous retrouverez tout tel quel, sans retélécharger les modèles.
en.AskKeepData=Also delete your settings, history and downloaded AI models?%n%nChoose "No" if you plan to reinstall Voice Typer: everything will be kept as is, with no need to download the models again.

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:TaskGroup}"
Name: "autostart"; Description: "{cm:TaskAutostart}"; GroupDescription: "{cm:TaskGroup}"

[InstallDelete]
; drop files left by an older version before copying the new ones
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Voice Typer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; same value the app's own "Start with Windows" switch uses (voice_typer/autostart.py)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VoiceTyper"; ValueData: """{app}\{#AppExe}"" --minimized"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchNow}"; Flags: nowait postinstall skipifsilent
; automatic update (voice_typer/updater.py passes /UPDATE=1): start the new version again
Filename: "{app}\{#AppExe}"; Parameters: "--updated"; Flags: nowait; Check: IsUpdate

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
function IsUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  HubDir: String;
  Find: TFindRec;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;
  { the app may have set this itself, even if the installer task was unticked }
  RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'VoiceTyper');
  if UninstallSilent then
    exit;
  if MsgBox(CustomMessage('AskKeepData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) <> IDYES then
    exit;
  DelTree(ExpandConstant('{userappdata}\VoiceTyper'), True, True, True);
  { Speech and writing models live in the Hugging Face cache; only remove the ones this app uses. }
  HubDir := GetEnv('HF_HUB_CACHE');
  if HubDir = '' then
    if GetEnv('HF_HOME') <> '' then
      HubDir := AddBackslash(GetEnv('HF_HOME')) + 'hub'
    else
      HubDir := ExpandConstant('{%USERPROFILE}\.cache\huggingface\hub');
  HubDir := AddBackslash(HubDir);
  if FindFirst(HubDir + 'models--*', Find) then
  try
    repeat
      if (Pos('faster-whisper', Lowercase(Find.Name)) > 0) or
         (Pos('whisper-large-v3-french', Lowercase(Find.Name)) > 0) or
         (Pos('distil-large-v3', Lowercase(Find.Name)) > 0) or
         ((Pos('qwen2.5', Lowercase(Find.Name)) > 0) and (Pos('ct2', Lowercase(Find.Name)) > 0)) then
        DelTree(HubDir + Find.Name, True, True, True);
    until not FindNext(Find);
  finally
    FindClose(Find);
  end;
end;
