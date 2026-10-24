; Seafari for Windows - NSIS Installer Script
; Compiles on both Linux (ubuntu-latest via `makensis`) and Windows

!include "MUI2.nsh"

!ifndef VERSION
  !define VERSION "1.0.0"
!endif

!ifndef SOURCE_DIR
  !define SOURCE_DIR "..\build_workspace\Seafari"
!endif

!ifndef OUT_FILE
  !define OUT_FILE "..\Seafari-Setup-${VERSION}.exe"
!endif

Name "Seafari ${VERSION}"
OutFile "${OUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\Seafari"
InstallDirRegKey HKCU "Software\InledGroup\Seafari" "Install_Dir"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!define MUI_ABORTWARNING
!define MUI_ICON "..\seafari.ico"
!define MUI_UNICON "..\seafari.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\seafari.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Seafari Browser"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Seafari Browser" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  File /r "${SOURCE_DIR}\*.*"

  ; Store installation folder and uninstaller info
  WriteRegStr HKCU "Software\InledGroup\Seafari" "Install_Dir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Seafari" "DisplayName" "Seafari Browser"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Seafari" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Seafari" "Publisher" "Inled Group"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Seafari" "DisplayIcon" "$INSTDIR\seafari.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Seafari" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Seafari" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Seafari" "NoRepair" 1

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Create Start Menu and Desktop shortcuts
  CreateDirectory "$SMPROGRAMS\Seafari"
  CreateShortCut "$SMPROGRAMS\Seafari\Seafari.lnk" "$INSTDIR\seafari.exe" "" "$INSTDIR\seafari.ico" 0
  CreateShortCut "$SMPROGRAMS\Seafari\Uninstall Seafari.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\seafari.ico" 0
  CreateShortCut "$DESKTOP\Seafari.lnk" "$INSTDIR\seafari.exe" "" "$INSTDIR\seafari.ico" 0
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\Seafari.lnk"
  Delete "$SMPROGRAMS\Seafari\Seafari.lnk"
  Delete "$SMPROGRAMS\Seafari\Uninstall Seafari.lnk"
  RMDir "$SMPROGRAMS\Seafari"

  RMDir /r "$INSTDIR"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Seafari"
  DeleteRegKey HKCU "Software\InledGroup\Seafari"
SectionEnd
