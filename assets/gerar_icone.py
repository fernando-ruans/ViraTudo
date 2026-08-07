"""Gera o ícone do ViraTudo (assets/icon.png e icon.ico).

Usa a logo oficial (ViraTudo.png na raiz) quando disponível; senão,
desenha o ícone padrão (retângulo gradiente + seta). Roda manualmente:

    python -m assets.gerar_icone

Usa apenas PySide6 (QPainter) e Pillow (ICO multi-resolução).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).parent
RAIZ = ASSETS.parent
LOGO = RAIZ / "ViraTudo.png"

TAMANHOS_ICO = [16, 24, 32, 48, 64, 128, 256]


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


def _carregar_logo() -> QPixmap | None:
    """Carrega a logo oficial (ViraTudo.png) se existir; None caso contrário."""
    if not LOGO.exists():
        return None
    pix = QPixmap(str(LOGO))
    if pix.isNull():
        return None
    # Garante quadrado para o ICO (fundo transparente ao redor)
    lado = max(pix.width(), pix.height())
    if (pix.width(), pix.height()) != (lado, lado):
        canvas = QPixmap(lado, lado)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.drawPixmap((lado - pix.width()) // 2, (lado - pix.height()) // 2,
                     pix)
        p.end()
        pix = canvas
    return pix


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    ASSETS.mkdir(exist_ok=True)

    logo = _carregar_logo()

    png_path = ASSETS / "icon.png"
    if logo is not None:
        logo.save(str(png_path), "PNG")
        print(f"PNG: {png_path} (logo oficial {LOGO.name})")
    else:
        desenhar_icone(256).save(str(png_path), "PNG")
        print(f"PNG: {png_path} (ícone padrão desenhado)")

    # ICO multi-resolução via Pillow
    try:
        from PIL import Image
        fonte = Image.open(LOGO).convert("RGBA") if logo is not None else None
        if fonte is None:
            # Converte o QPixmap desenhado para PNG temporário -> PIL
            tmp = ASSETS / "_tmp_icon.png"
            desenhar_icone(256).save(str(tmp), "PNG")
            fonte = Image.open(tmp).convert("RGBA")
            tmp.unlink(missing_ok=True)
        w, h = fonte.size
        lado = max(w, h)
        if (w, h) != (lado, lado):
            canvas = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
            canvas.paste(fonte, ((lado - w) // 2, (lado - h) // 2))
            fonte = canvas
        ico_path = ASSETS / "icon.ico"
        fonte.save(ico_path, "ICO",
                   sizes=[(t, t) for t in TAMANHOS_ICO])
        print(f"ICO: {ico_path} (tamanhos {TAMANHOS_ICO})")
    except Exception as e:  # noqa: BLE001 — fallback não deve quebrar o build
        print(f"ICO falhou (Pillow indisponível?): {e}")
        # Fallback: QIcon com várias resoluções salvo como ICO simples
        ico_path = ASSETS / "icon.ico"
        icon = QIcon(desenhar_icone(256))
        if not icon.pixmap(256, 256).isNull():
            if not desenhar_icone(256).save(str(ico_path), "ICO"):
                print(f"ICO falhou, salvando PNG em {ico_path}.png")


if __name__ == "__main__":
    main()
