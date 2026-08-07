#!/usr/bin/env bash
# Build do ViraTudo para Linux (PyInstaller)
# Uso:  ./build_linux.sh
# Saída: dist/viratudo/viratudo
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/4] Verificando Python 3 e venv..."
if ! command -v python3 >/dev/null; then
    echo "[ERRO] python3 não encontrado. Instale: sudo apt install python3 python3-venv"
    exit 1
fi
if [ ! -d .venv-linux ]; then
    echo "  Criando .venv-linux..."
    python3 -m venv .venv-linux
fi
# shellcheck disable=SC1091
source .venv-linux/bin/activate

echo "[2/4] Instalando dependências..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt pyinstaller

echo "[3/4] Gerando ícone..."
python -m assets.gerar_icone

echo "[4/4] Empacotando com PyInstaller..."
python -m PyInstaller --noconfirm --clean --windowed --name viratudo \
  --icon assets/icon.png \
  --add-data "assets:assets" \
  --hidden-import yt_dlp \
  app.py

echo
echo "Concluído! Executável: dist/viratudo/viratudo"
echo "Nota: o FFmpeg precisa estar instalado (sudo apt install ffmpeg)."
