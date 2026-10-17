; Chicken Macro - local installer test. Keep this AppId unchanged for future releases.
#define AppName "Chicken Macro"
#define AppVersion "1.0.0"
#define AppExe "Chicken.exe"

#if !FileExists("dist\Chicken\Chicken.exe")
  #error Save this script in the project folder containing dist\Chicken\Chicken.exe.
#endif

[Setup]
AppId={{B74EE832-FBC8-4D04-AC6B-E1313B8A7614}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=ggaril88
AppPublisherURL=https://github.com/ggaril88/Chicken-Macro
AppSupportURL=https://github.com/ggaril88/Chicken-Macro/issues
DefaultDirName={localappdata}\Programs\Chicken Macro
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=installer-output
OutputBaseFilename=Chicken-Macro-Setup-{#AppVersion}
SetupIconFile=chicken.ico
UninstallDisplayIcon={app}\{#AppExe}
Uninstallable=yes
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; CHICKEN THIRD-PARTY RELEASE MATERIALS
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "REBUILDING.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "third_party\*"; DestDir: "{app}\third_party"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "source-release\Chicken-Macro-source.zip"; DestDir: "{app}\source-release"; Flags: ignoreversion

Source: "dist\Chicken\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent


[Code]
var
  DeleteSavedData: Boolean;

function InitializeUninstall(): Boolean;
var
  Form: TSetupForm;
  LabelText: TNewStaticText;
  DeleteBox: TNewCheckBox;
  ContinueButton, CancelButton: TNewButton;
begin
  DeleteSavedData := False;
  Result := True;
  if UninstallSilent then Exit;
  Form := CreateCustomForm(ScaleX(520), ScaleY(245), False, False);
  try
    Form.Caption := 'Uninstall Chicken Macro';
    Form.Position := poScreenCenter;
    LabelText := TNewStaticText.Create(Form);
    LabelText.Parent := Form;
    LabelText.AutoSize := False;
    LabelText.WordWrap := True;
    LabelText.SetBounds(ScaleX(18), ScaleY(16), ScaleX(484), ScaleY(62));
    LabelText.Caption := 'Remove Chicken Macro from this computer?' + #13#10 + #13#10 +
      'Your macros and settings will be kept unless you select the option below.';
    DeleteBox := TNewCheckBox.Create(Form);
    DeleteBox.Parent := Form;
    DeleteBox.SetBounds(ScaleX(18), ScaleY(87), ScaleX(484), ScaleY(26));
    DeleteBox.Caption := 'Also permanently delete saved macros and settings';
    DeleteBox.Checked := False;
    LabelText := TNewStaticText.Create(Form);
    LabelText.Parent := Form;
    LabelText.AutoSize := False;
    LabelText.WordWrap := True;
    LabelText.SetBounds(ScaleX(18), ScaleY(122), ScaleX(484), ScaleY(60));
    LabelText.Caption := 'Close Chicken before continuing. If selected, a second dialog will show the exact folders and ask you to type delete (any capitalization).' + #13#10 +
      'Exports, old custom-library copies and development backups are not removed.';
    ContinueButton := TNewButton.Create(Form);
    ContinueButton.Parent := Form;
    ContinueButton.SetBounds(ScaleX(264), ScaleY(199), ScaleX(115), ScaleY(28));
    ContinueButton.Caption := 'Continue';
    ContinueButton.ModalResult := mrOk;
    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.SetBounds(ScaleX(387), ScaleY(199), ScaleX(115), ScaleY(28));
    CancelButton.Caption := 'Cancel';
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;
    Result := Form.ShowModal = mrOk;
    if Result then DeleteSavedData := DeleteBox.Checked;
  finally
    Form.Free;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Launched: Boolean;
begin
  if (CurUninstallStep = usUninstall) and DeleteSavedData and (not UninstallSilent) then
  begin
    Launched := Exec(ExpandConstant('{app}\Chicken.exe'), '--uninstall-data-confirm',
      ExpandConstant('{app}'), SW_SHOW, ewWaitUntilTerminated, ResultCode);
    if not Launched then
      MsgBox('The data-removal dialog could not start. No data-removal request was completed. Uninstall will continue; check your data folders manually.', mbError, MB_OK)
    else if ResultCode = 10 then
      MsgBox('Data deletion was not confirmed. Uninstall will continue and keep your saved data.', mbInformation, MB_OK)
    else if ResultCode <> 0 then
      MsgBox('Some saved data may remain. Uninstall will continue. Check the folders shown in the previous dialog.', mbError, MB_OK);
  end;
end;
