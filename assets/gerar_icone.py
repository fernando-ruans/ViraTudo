"""Gera o ícone do ViraTudo (assets/icon.png e icon.ico).

Roda manualmente: python -m assets.gerar_icone
Usa apenas PySide6 (QPainter) — sem dependências extras.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).parent


def desenhar_icone(tamanho: int = 256) -> QPixmap:
    """Desenha o ícone: retângulo arredondado gradiente + seta de conversão."""
    pix = QPixmap(tamanho, tamanho)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fundo: gradiente roxo -> azul
    fundo = QRectF(tamanho * 0.04, tamanho * 0.04,
                   tamanho * 0.92, tamanho * 0.92)
    from PySide6.QtGui import QLinearGradient
    g = QLinearGradient(fundo.topLeft(), fundo.bottomRight())
    g.setColorAt(0.0, QColor(88, 86, 214))    # roxo
    g.setColorAt(1.0, QColor(0, 110, 200))    # azul
    p.setBrush(g)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(fundo, tamanho * 0.22, tamanho * 0.22)

    # Seta de conversão (⟳) branca
    p.setPen(QColor(255, 255, 255))
    fonte = QFont("Segoe UI Symbol", int(tamanho * 0.42))
    p.setFont(fonte)
    p.drawText(fundo, Qt.AlignmentFlag.AlignCenter, "⇄")
    p.end()
    return pix


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    ASSETS.mkdir(exist_ok=True)

    pix = desenhar_icone(256)
    png_path = ASSETS / "icon.png"
    pix.save(str(png_path), "PNG")
    print(f"PNG: {png_path}")

    # ICO: várias resoluções (PySide6 gera multi-size ico)
    ico_path = ASSETS / "icon.ico"
    icon = QIcon(pix)
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(desenhar_icone(size))
    if not icon.pixmap(256, 256).isNull():
        # Salva via QPixmap em tamanhos múltiplos é limitado; gera ICO
        # com a maior resolução (Windows escala)
        pix256 = desenhar_icone(256)
        if not pix256.save(str(ico_path), "ICO"):
            # Fallback: salva como PNG mesmo
            print(f"ICO falhou, salvando PNG em {ico_path}.png")
            pix256.save(str(ico_path) + ".png", "PNG")
    print(f"ICO: {ico_path}")


if __name__ == "__main__":
    main()
