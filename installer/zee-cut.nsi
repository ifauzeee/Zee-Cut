; Zee-Cut NSIS installer script (template).
; Build: makensis zee-cut.nsi   (requires the compiled Zee-Cut.exe in dist/)
;
; This produces an installer that drops Zee-Cut.exe, creates a Start Menu
; shortcut, and reminds the user that Npcap + Administrator rights are needed.

!define APPNAME "Zee-Cut"
!define APPVERSION "0.5.0"
!define PUBLISHER "ifauzeee"

Name "${APPNAME} ${APPVERSION}"
OutFile "dist\Zee-Cut-Setup-${APPVERSION}.exe"
InstallDir "$LOCALAPPDATA\${APPNAME}"
RequestExecutionLevel admin

!include "MUI2.nsh"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    File "dist\Zee-Cut.exe"

    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\Zee-Cut.exe"
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\Zee-Cut.exe"

    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\Zee-Cut.exe"
    Delete "$INSTDIR\Uninstall.exe"
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    Delete "$DESKTOP\${APPNAME}.lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"
    RMDir "$INSTDIR"
SectionEnd
