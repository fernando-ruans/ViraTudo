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

from converter import find_ffmpeg
from converter.presets import ALL_INPUT_EXT

from .convert_tab import ConvertTab
from .youtube_tab import YouTubeTab

APP_TITLE = "ViraTudo — Conversor Universal"
WINDOW_ICON = None  # placeholder; ícone real pode ser adicionado depois


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
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

        m_help = menubar.addMenu("&Ajuda")
        act_about = QAction("Sobre", self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)

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
            "<b>ViraTudo v1.0</b><br><br>"
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
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("ViraTudo")
    app.setStyle("Fusion")  # visual consistente em Windows/Linux

    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    win = MainWindow()
    win.show()
    return app.exec()
