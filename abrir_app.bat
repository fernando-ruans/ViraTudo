@echo off
title ViraTudo
cd /d "%~dp0"
python app.py
if errorlevel 1 (
  echo.
  echo [ERRO] Nao foi possivel abrir o app.
  echo Verifique se o Python esta instalado e rode: pip install -r requirements.txt
  pause
)
