"""Janela principal: abas de conversão de arquivos e YouTube."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QLabel, QMainWindow, QMessageBox,
    QTabWidget, QVBoxLayout, QWidget,
)

from converter import __version__, find_ffmpeg
from converter.presets import ALL_INPUT_EXT
from ui import settings

from .convert_tab import ConvertTab
from .youtube_tab import YouTubeTab

APP_TITLE = f"ViraTudo — Conversor Universal v{__version__}"


def _load_icon():
    """Carrega o ícone do app (assets/icon.png ou .ico)."""
    from PySide6.QtGui import QIcon
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "assets"
    for nome in ("icon.ico", "icon.png"):
        caminho = base / nome
        if caminho.exists():
            return QIcon(str(caminho))
    return QIcon()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(_load_icon())
        self.resize(860, 640)
        self.setMinimumSize(720, 520)

        self._build_ui()
        self._build_menu()
        self._check_ffmpeg()

    # ------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget(central)
        self.tab_convert = ConvertTab(self)
        self.tab_youtube = YouTubeTab(self)
        self.tabs.addTab(self.tab_convert, "📁  Converter Arquivos")
        self.tabs.addTab(self.tab_youtube, "▶️  YouTube")
        layout.addWidget(self.tabs)

        # Barra de status com info do FFmpeg
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Pronto.")

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        m_file = menubar.addMenu("&Arquivo")
        act_exit = QAction("Sair", self)
        act_exit.setShortcut(QKeySequence.Quit)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        m_view = menubar.addMenu("&Ver")
        act_dark = QAction("Tema escuro", self)
        act_dark.setCheckable(True)
        act_dark.setChecked(settings.get_theme() == "escuro")
        act_dark.triggered.connect(lambda: self._set_theme("escuro"))
        m_view.addAction(act_dark)
        act_light = QAction("Tema claro", self)
        act_light.setCheckable(True)
        act_light.setChecked(settings.get_theme() == "claro")
        act_light.triggered.connect(lambda: self._set_theme("claro"))
        m_view.addAction(act_light)
        act_auto = QAction("Seguir o sistema", self)
        act_auto.setCheckable(True)
        act_auto.setChecked(settings.get_theme() == "auto")
        act_auto.triggered.connect(lambda: self._set_theme("auto"))
        m_view.addAction(act_auto)

        m_help = menubar.addMenu("&Ajuda")
        act_about = QAction("Sobre", self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)

        # Guarda referências às ações de tema (não dependem da ordem do menu)
        self._theme_actions_ref = (act_dark, act_light, act_auto)

    def _set_theme(self, tema: str) -> None:
        from .themes import aplicar_tema
        settings.set_theme(tema)
        aplicar_tema(QApplication.instance(), tema)
        # Atualiza os checkmarks do menu
        for act, t in zip(self._theme_actions(), ("escuro", "claro", "auto")):
            act.setChecked(t == tema)

    def _theme_actions(self):
        return self._theme_actions_ref

    def closeEvent(self, event) -> None:
        # Cancela downloads/conversões ativos antes de destruir os widgets,
        # evitando que threads de background emitam signals em objetos Qt
        # já destruídos durante o shutdown.
        self.tab_convert.begin_close()
        self.tab_youtube.begin_close()
        super().closeEvent(event)

    # ------------------------------------------------------------- Ações
    def _check_ffmpeg(self) -> None:
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            ver = _ffmpeg_version(ffmpeg)
            self.status_bar.showMessage(
                f"FFmpeg: {ver or ffmpeg}  |  Conversão 100% offline")
        else:
            self.status_bar.showMessage("⚠️ FFmpeg não encontrado no PATH")

    def _show_about(self) -> None:
        ffmpeg = find_ffmpeg()
        msg = (
            f"<b>ViraTudo v{__version__}</b><br><br>"
            "Conversor de mídia nativo (Qt6) que roda em Windows e Linux.<br>"
            "Toda a conversão é feita localmente pelo FFmpeg — sem nuvem, "
            "sem upload, sem internet.<br><br>"
            f"FFmpeg: {'✓ encontrado' if ffmpeg else '✗ não encontrado'}<br>"
            "YouTube: downloads via yt-dlp (requer internet só para baixar)."
        )
        QMessageBox.about(self, "Sobre o ViraTudo", msg)


def _ffmpeg_version(ffmpeg: str) -> str:
    import subprocess
    try:
        out = subprocess.run([ffmpeg, "-version"], capture_output=True,
                             text=True, timeout=5).stdout
        return out.splitlines()[0].split("Copyright")[0].strip()
    except Exception:
        return ""


def run_app() -> int:
    """Entry point da GUI."""
    from ui import settings
    from ui.themes import aplicar_tema

    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("ViraTudo")
    app.setStyle("Fusion")  # visual consistente em Windows/Linux
    aplicar_tema(app, settings.get_theme())  # tema salvo (escuro/claro/auto)

    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    win = MainWindow()
    win.show()
    return app.exec()
