Unicode true
SetCompressor lzma

!include "MUI2.nsh"
!include "FileFunc.nsh"

!define PRODUCT_NAME "VoirolClass"
!define PRODUCT_PUBLISHER "VoirolClass"

Name "${PRODUCT_NAME} ${VERSION}"
OutFile "VoirolClass-${VERSION}-Setup.exe"
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"
RequestExecutionLevel admin

!define MUI_ABORTWARNING
!define MUI_ICON "assets\img\icon.png"
!define MUI_UNICON "assets\img\icon.png"
!define MUI_WELCOMEPAGE_TITLE "VoirolClass ${VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through installing VoirolClass ${VERSION}.\r\n\r\nVoirolClass is a voice-controlled classroom assistant with speaker verification, offline ASR, and AI command matching.\r\n\r\nClick Next to continue."
!define MUI_DIRECTORYPAGE_VERIFYONINIT

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File "dist\VoirolClass.exe"

  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\VoirolClass.lnk" "$INSTDIR\VoirolClass.exe"
  CreateShortCut "$DESKTOP\VoirolClass.lnk" "$INSTDIR\VoirolClass.exe"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
    "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
    "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
    "DisplayIcon" "$INSTDIR\VoirolClass.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
    "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
    "DisplayVersion" "${VERSION}"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\VoirolClass.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  Delete "$SMPROGRAMS\${PRODUCT_NAME}\VoirolClass.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
  Delete "$DESKTOP\VoirolClass.lnk"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
