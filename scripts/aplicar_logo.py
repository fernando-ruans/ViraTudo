"""Aplica a logo oficial (ViraTudo.png) nos assets do app.

Copia ViraTudo.png -> assets/icon.png e gera assets/icon.ico
multi-resolução (16..256 px) para a janela e o executável Windows.

Uso: python scripts/aplicar_logo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
LOGO = RAIZ / "ViraTudo.png"
ASSETS = RAIZ / "assets"
PNG_OUT = ASSETS / "icon.png"
ICO_OUT = ASSETS / "icon.ico"


def main() -> int:
    if not LOGO.exists():
        print(f"Logo não encontrada: {LOGO}")
        return 1
    ASSETS.mkdir(exist_ok=True)

    img = Image.open(LOGO).convert("RGBA")
    # Garante que o PNG seja quadrado (o Windows usa o ICO quadrado)
    w, h = img.size
    lado = max(w, h)
    if (w, h) != (lado, lado):
        canvas = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        canvas.paste(img, ((lado - w) // 2, (lado - h) // 2))
        img = canvas

    img.save(PNG_OUT, "PNG")
    print(f"PNG: {PNG_OUT} ({img.size[0]}x{img.size[1]})")

    # ICO multi-resolução (Windows exige 16/24/32/48/64/128/256)
    tamanhos = [16, 24, 32, 48, 64, 128, 256]
    img.save(ICO_OUT, "ICO", sizes=[(t, t) for t in tamanhos])
    print(f"ICO: {ICO_OUT} (tamanhos {tamanhos})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
