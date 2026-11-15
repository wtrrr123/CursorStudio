Unicode true
Name "Cursor Studio"
OutFile "CursorStudio-Setup-x64.exe"
InstallDir ""
RequestExecutionLevel user
SetCompressor /SOLID lzma
!include "x64.nsh"
Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Function .onInit
  StrCmp $INSTDIR "" 0 +2
  StrCpy $INSTDIR "$EXEDIR\CursorStudio"
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Cursor Studio requires 64-bit Windows."
    Abort
  ${EndIf}
FunctionEnd

Section
  SetOutPath "$INSTDIR"
  File /r "bundle\CursorStudio\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Cursor Studio"
  CreateShortCut "$SMPROGRAMS\Cursor Studio\Cursor Studio.lnk" "$INSTDIR\CursorStudio.exe"
  CreateShortCut "$SMPROGRAMS\Cursor Studio\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\Cursor Studio\Cursor Studio.lnk"
  Delete "$SMPROGRAMS\Cursor Studio\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Cursor Studio"
  Delete "$INSTDIR\CursorStudio.exe"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\source"
  RMDir "$INSTDIR"
SectionEnd
