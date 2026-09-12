; =====================================================================
; ViraTudo — Instalador Windows (NSIS 3)
;
; Uso (a partir da raiz do projeto):
;   "C:\Program Files (x86)\NSIS\makensis.exe" ViraTudo-setup.nsi
;
; Pré-requisito: pasta dist\ViraTudo\ gerada pelo PyInstaller
;   (rode build_windows.bat antes).
; Saída: dist\ViraTudo_1.3.0_win64-setup.exe
;
; Instalação por usuário (sem admin/UAC): %LOCALAPPDATA%\ViraTudo
; =====================================================================

!define APP_NAME "ViraTudo"
!define APP_VERSION "1.3.0"
!define APP_PUBLISHER "ViraTudo"
!define APP_EXE "ViraTudo.exe"
!define SRC_DIR "dist\ViraTudo"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "dist\${APP_NAME}_${APP_VERSION}_win64-setup.exe"
InstallDir "$LOCALAPPDATA\${APP_NAME}"
RequestExecutionLevel user
SetCompressor /SOLID lzma

Function .onInit
  SetShellVarContext current
FunctionEnd

Function un.onInit
  SetShellVarContext current
FunctionEnd

; Versão embutida no próprio instalador
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "FileDescription" "${APP_NAME} ${APP_VERSION} Setup"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "LegalCopyright" "${APP_PUBLISHER}"

!include "MUI2.nsh"
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\icon.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"
!insertmacro MUI_LANGUAGE "English"

; ---------------------------------------------------------------- install
Section "Instalar" SEC_INSTALL
  ; Se o app estiver aberto, o .exe fica travado: pede para fechar e aborta.
  Delete "$INSTDIR\${APP_EXE}"
  IfFileExists "$INSTDIR\${APP_EXE}" 0 +3
    MessageBox MB_OK|MB_ICONSTOP "Feche o ${APP_NAME} antes de continuar a instalação."
    Abort

  ; Limpa restos de versão anterior (pasta 100% gerenciada pelo instalador)
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\_internal"

  SetOutPath "$INSTDIR"
  File /r "${SRC_DIR}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Atalhos: Menu Iniciar + Área de Trabalho
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE},0"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Desinstalar.lnk" \
    "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE},0"

  ; Registro em "Adicionar ou remover programas" (HKCU, sem admin)
  WriteRegStr HKCU \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKCU \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegDWORD HKCU \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "NoModify" 1
  WriteRegDWORD HKCU \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "NoRepair" 1
SectionEnd

; -------------------------------------------------------------- uninstall
Section "Uninstall"
  Delete "$INSTDIR\${APP_EXE}"
  IfFileExists "$INSTDIR\${APP_EXE}" 0 +3
    MessageBox MB_OK|MB_ICONSTOP "Feche o ${APP_NAME} antes de desinstalar."
    Abort

  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\_internal"
  ; Remove arquivos restantes da instalação (logs e configs do usuário
  ; ficam em %USERPROFILE%\ViraTudo e no registro do app — preservados)
  Delete "$INSTDIR\*.*"
  RMDir "$INSTDIR"

  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Desinstalar.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"

  DeleteRegKey HKCU \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
SectionEnd
