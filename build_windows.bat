@echo off
REM Build do ViraTudo para Windows (PyInstaller)
REM Uso:  build_windows.bat
REM Saida: dist\ViraTudo\ViraTudo.exe
chcp 65001 >nul
title Build ViraTudo
cd /d "%~dp0"

echo [1/4] Gerando icone...
python -m assets.gerar_icone || goto :erro

echo [2/4] Instalando PyInstaller (se necessario)...
python -m pip install pyinstaller --quiet || goto :erro

echo [3/4] Empacotando...
python -m PyInstaller --noconfirm --clean --windowed --name ViraTudo ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --hidden-import yt_dlp ^
  app.py || goto :erro

echo [4/4] Criando atalho na raiz do projeto...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%~dp0ViraTudo.lnk'); $s.TargetPath = '%~dp0dist\ViraTudo\ViraTudo.exe'; $s.WorkingDirectory = '%~dp0dist\ViraTudo'; $s.IconLocation = '%~dp0dist\ViraTudo\ViraTudo.exe,0'; $s.Save()" || goto :erro

echo [5/5] Concluido!
echo.
echo Executavel: dist\ViraTudo\ViraTudo.exe
echo Atalho criado: ViraTudo.lnk (raiz do projeto) - use SEMPRE este, nunca o de build\ViraTudo\
echo Nota: o FFmpeg precisa estar no PATH da maquina de destino.
pause
exit /b 0

:erro
echo.
echo [ERRO] Build falhou. Veja a mensagem acima.
pause
exit /b 1
