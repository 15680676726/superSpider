; Spider Mesh desktop NSIS installer. Run makensis from repo root after
; building dist/win-unpacked (see scripts/pack/build_win.ps1).
; Usage: makensis /DCOPAW_VERSION=1.2.3 /DOUTPUT_EXE=dist\Spider-Mesh-Setup-1.2.3.exe scripts\pack\copaw_desktop.nsi

!include "MUI2.nsh"
!define MUI_ABORTWARNING
; Use custom icon from unpacked env (copied by build_win.ps1)
!define MUI_ICON "${UNPACKED}\icon.ico"
!define MUI_UNICON "${UNPACKED}\icon.ico"
!define PRODUCT_DISPLAY_NAME "Spider Mesh"
!define PRODUCT_INSTALL_DIR "SpiderMesh"
!define PRODUCT_REG_KEY "Software\SpiderMesh"
!define MAIN_LAUNCHER "baize-desktop.vbs"
!define DEBUG_LAUNCHER "baize-desktop-debug.bat"

!ifndef COPAW_VERSION
  !define COPAW_VERSION "0.0.0"
!endif
!ifndef OUTPUT_EXE
  !define OUTPUT_EXE "dist\Spider-Mesh-Setup-${COPAW_VERSION}.exe"
!endif

Name "${PRODUCT_DISPLAY_NAME}"
OutFile "${OUTPUT_EXE}"
InstallDir "$LOCALAPPDATA\${PRODUCT_INSTALL_DIR}"
InstallDirRegKey HKCU "${PRODUCT_REG_KEY}" "InstallPath"
RequestExecutionLevel user

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

; Pass /DUNPACKED=full_path from build_win.ps1 so path works when cwd != repo root
!ifndef UNPACKED
  !define UNPACKED "dist\win-unpacked"
!endif

Section "${PRODUCT_DISPLAY_NAME}" SEC01
  SetOutPath "$INSTDIR"
  File /r /x "*.pyc" /x "__pycache__" "${UNPACKED}\*.*"
  WriteRegStr HKCU "${PRODUCT_REG_KEY}" "InstallPath" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Main shortcut - uses VBS to hide console window
  CreateShortcut "$SMPROGRAMS\${PRODUCT_DISPLAY_NAME}.lnk" "$INSTDIR\${MAIN_LAUNCHER}" "" "$INSTDIR\icon.ico" 0
  CreateShortcut "$DESKTOP\${PRODUCT_DISPLAY_NAME}.lnk" "$INSTDIR\${MAIN_LAUNCHER}" "" "$INSTDIR\icon.ico" 0

  ; Debug shortcut - shows console window for troubleshooting
  CreateShortcut "$SMPROGRAMS\${PRODUCT_DISPLAY_NAME}（调试）.lnk" "$INSTDIR\${DEBUG_LAUNCHER}" "" "$INSTDIR\icon.ico" 0
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\${PRODUCT_DISPLAY_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_DISPLAY_NAME}（调试）.lnk"
  Delete "$DESKTOP\${PRODUCT_DISPLAY_NAME}.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${PRODUCT_REG_KEY}"
SectionEnd
