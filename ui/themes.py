"""Temas claro/escuro (Fusion + paletas Qt).

Alternar tema em runtime: chamar tema_escuro(app) / tema_claro(app)
redefine o QPalette global — todos os widgets atualizam na hora.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def tema_escuro(app: QApplication) -> None:
    """Paleta escura (estilo dark moderno)."""
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(35, 38, 46))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(230, 230, 230))
    pal.setColor(QPalette.ColorRole.Base, QColor(28, 30, 37))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(40, 43, 52))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(45, 48, 58))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(230, 230, 230))
    pal.setColor(QPalette.ColorRole.Text, QColor(230, 230, 230))
    pal.setColor(QPalette.ColorRole.Button, QColor(48, 52, 62))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(230, 230, 230))
    pal.setColor(QPalette.ColorRole.BrightText, QColor(255, 80, 80))
    pal.setColor(QPalette.ColorRole.Link, QColor(86, 156, 214))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(86, 156, 214))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(20, 22, 28))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(130, 135, 145))
    app.setPalette(pal)


def tema_claro(app: QApplication) -> None:
    """Paleta clara (padrão limpo)."""
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Text, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Button, QColor(235, 235, 235))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.BrightText, QColor(200, 30, 30))
    pal.setColor(QPalette.ColorRole.Link, QColor(0, 110, 200))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(0, 110, 200))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(130, 130, 130))
    app.setPalette(pal)


def aplicar_tema(app: QApplication, tema: str) -> None:
    """Aplica o tema salvo ('escuro', 'claro' ou 'auto')."""
    if tema == "escuro":
        tema_escuro(app)
    elif tema == "claro":
        tema_claro(app)
    else:  # auto: segue o sistema
        from PySide6.QtGui import QGuiApplication
        escuro = QGuiApplication.styleHints().colorScheme() == 2  # Qt::ColorScheme::Dark
        if escuro:
            tema_escuro(app)
        else:
            tema_claro(app)
