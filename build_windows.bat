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

echo [3/4] Localizando FFmpeg (sera embutido no pacote)...
where ffmpeg >nul 2>nul || (echo [ERRO] FFmpeg nao encontrado no PATH. Instale e tente de novo. & goto :erro)
where ffprobe >nul 2>nul || (echo [ERRO] ffprobe nao encontrado no PATH. Instale e tente de novo. & goto :erro)
for /f "delims=" %%F in ('where ffmpeg') do set FFMPEG_EXE=%%F & goto :ffmpeg_ok
:ffmpeg_ok
for /f "delims=" %%F in ('where ffprobe') do set FFPROBE_EXE=%%F & goto :ffprobe_ok
:ffprobe_ok
echo     FFmpeg: %FFMPEG_EXE%
echo     ffprobe: %FFPROBE_EXE%

echo [4/4] Empacotando...
python -m PyInstaller --noconfirm --clean --windowed --name ViraTudo ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --add-binary "%FFMPEG_EXE%;." ^
  --add-binary "%FFPROBE_EXE%;." ^
  --hidden-import yt_dlp ^
  app.py || goto :erro

echo [5/5] Criando atalho na raiz do projeto...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%~dp0ViraTudo.lnk'); $s.TargetPath = '%~dp0dist\ViraTudo\ViraTudo.exe'; $s.WorkingDirectory = '%~dp0dist\ViraTudo'; $s.IconLocation = '%~dp0dist\ViraTudo\ViraTudo.exe,0'; $s.Save()" || goto :erro

echo [5/5] Concluido!
echo.
echo Executavel: dist\ViraTudo\ViraTudo.exe
echo Atalho criado: ViraTudo.lnk (raiz do projeto) - use SEMPRE este, nunca o de build\ViraTudo\
echo FFmpeg + ffprobe embutidos no pacote: funciona em qualquer maquina Windows.
pause
exit /b 0

:erro
echo.
echo [ERRO] Build falhou. Veja a mensagem acima.
pause
exit /b 1
