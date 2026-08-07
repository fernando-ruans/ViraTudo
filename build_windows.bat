# Build do ViraTudo para Windows (PyInstaller)
# Uso:  build_windows.bat
# Saída: dist\ViraTudo\ViraTudo.exe
@echo off
chcp 65001 >nul
title Build ViraTudo
cd /d "%~dp0"

echo [1/4] Gerando icone...
python -m assets.gerar_icone || goto :erro

echo [2/4] Instalando PyInstaller (se necessario)...
pip install pyinstaller --quiet || goto :erro

echo [3/4] Empacotando...
pyinstaller --noconfirm --clean --windowed --name ViraTudo ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --hidden-import yt_dlp ^
  app.py || goto :erro

echo [4/4] Concluido!
echo.
echo Executavel: dist\ViraTudo\ViraTudo.exe
echo Nota: o FFmpeg precisa estar no PATH da maquina de destino.
pause
exit /b 0

:erro
echo.
echo [ERRO] Build falhou. Veja a mensagem acima.
pause
exit /b 1
