"""Aba YouTube: baixar vídeo/áudio do YouTube e converter localmente.

Opções: qualidade (até 4K), formato de saída (vídeo ou áudio), pasta de
destino. Playlists são suportadas (opção marcável). O download usa yt-dlp
e a conversão usa o FFmpeg local.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from converter import (
    VIDEO_QUALITIES, YouTubeJob, is_youtube_url, run_download,
)
from converter.presets import OUTPUT_FORMATS
from ui import settings

# Formatos que fazem sentido no YouTube
YT_FORMATS = ["mp4", "mkv", "webm", "gif"] + \
    [k for k in OUTPUT_FORMATS if not OUTPUT_FORMATS[k].get("video")]


class YouTubeTab(QWidget):
    """Aba 'YouTube'."""

    _job_finished = Signal(str, str)  # status, mensagem

    def __init__(self, parent=None):
        super().__init__(parent)
        self.job: YouTubeJob | None = None
        self._running = False
        self._build_ui()
        self._job_finished.connect(self._on_job_finished)

    # ------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ---- URL ----
        gb_url = QGroupBox("1. Link do YouTube")
        v = QVBoxLayout(gb_url)
        self.edit_url = QLineEdit()
        self.edit_url.setPlaceholderText(
            "Cole aqui o link do vídeo, short ou playlist...")
        v.addWidget(self.edit_url)
        self.chk_playlist = QCheckBox("É uma playlist (baixar todos os vídeos)")
        v.addWidget(self.chk_playlist)
        layout.addWidget(gb_url)

        # ---- Opções ----
        gb_opts = QGroupBox("2. Opções de download")
        grid = QHBoxLayout(gb_opts)

        col1 = QVBoxLayout()
        col1.addWidget(QLabel("Qualidade:"))
        self.combo_quality = QComboBox()
        for label in VIDEO_QUALITIES:
            self.combo_quality.addItem(label, VIDEO_QUALITIES[label])
        q_idx = self.combo_quality.findData(settings.get_yt_quality())
        if q_idx >= 0:
            self.combo_quality.setCurrentIndex(q_idx)
        col1.addWidget(self.combo_quality)

        col2 = QVBoxLayout()
        col2.addWidget(QLabel("Formato de saída:"))
        self.combo_format = QComboBox()
        for key in YT_FORMATS:
            self.combo_format.addItem(OUTPUT_FORMATS[key]["label"], key)
        f_idx = self.combo_format.findData(settings.get_yt_format())
        if f_idx >= 0:
            self.combo_format.setCurrentIndex(f_idx)
        col2.addWidget(self.combo_format)

        col3 = QVBoxLayout()
        col3.addWidget(QLabel("Salvar em:"))
        row_dst = QHBoxLayout()
        self.edit_dst = QLineEdit(settings.get_yt_dst())
        row_dst.addWidget(self.edit_dst)
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(36)
        btn_browse.clicked.connect(self._browse_dst)
        row_dst.addWidget(btn_browse)
        col3.addLayout(row_dst)

        grid.addLayout(col1, 2)
        grid.addLayout(col2, 3)
        grid.addLayout(col3, 3)
        layout.addWidget(gb_opts)

        # ---- Progresso ----
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.label_status = QLabel("Cole um link para começar.")
        layout.addWidget(self.label_status)

        # ---- Ação ----
        self.btn_download = QPushButton("⬇️ Baixar e converter")
        self.btn_download.clicked.connect(self._start)
        layout.addWidget(self.btn_download)

        # Dica
        hint = QLabel(
            "💡 O download precisa de internet. A conversão do arquivo "
            "baixado (ex.: para MP3) é feita localmente, sem nuvem.")
        hint.setStyleSheet("color: gray;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    # ------------------------------------------------------------- Eventos
    def _browse_dst(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Pasta de destino", self.edit_dst.text())
        if d:
            self.edit_dst.setText(d)

    # ------------------------------------------------------------- Execução
    def _start(self) -> None:
        if self._running:
            self._cancel()
            return
        url = self.edit_url.text().strip()
        if not url:
            QMessageBox.information(self, "Link vazio", "Cole um link do YouTube.")
            return
        if not is_youtube_url(url):
            QMessageBox.warning(
                self, "Link inválido",
                "Isso não parece um link do YouTube.\n"
                "Exemplos:\n  https://youtube.com/watch?v=...\n  "
                "https://youtu.be/...\n  https://youtube.com/shorts/...")
            return

        self.job = YouTubeJob(
            url=url,
            output_dir=self.edit_dst.text().strip() or ".",
            quality=self.combo_quality.currentData(),
            output_format=self.combo_format.currentData(),
            is_playlist=self.chk_playlist.isChecked(),
        )

        # Persiste as preferências do usuário
        settings.set_yt_dst(self.edit_dst.text().strip() or ".")
        settings.set_yt_format(self.combo_format.currentData())
        settings.set_yt_quality(self.combo_quality.currentData())

        self._running = True
        self.btn_download.setText("⏹ Cancelar")
        self.edit_url.setEnabled(False)
        self.progress.setValue(0)
        self.label_status.setText("Conectando ao YouTube...")
        threading.Thread(target=self._worker, args=(self.job,), daemon=True).start()

    def _worker(self, job: YouTubeJob) -> None:
        def cb(pct, speed, eta, status):
            self.progress.setValue(int(pct))
            self.label_status.setText(
                f"{status} {pct:.0f}%  {speed or ''} {eta or ''}")

        run_download(job, callback=cb)
        self._job_finished.emit(job.status, job.error)

    def _cancel(self) -> None:
        if self.job:
            self.job.cancel()
        self.label_status.setText("Cancelando...")

    def _on_job_finished(self, status: str, error: str) -> None:
        self._running = False
        self.btn_download.setText("⬇️ Baixar e converter")
        self.edit_url.setEnabled(True)

        if status == "done":
            n = len(self.job.downloaded_files) if self.job else 0
            self.progress.setValue(100)
            self.label_status.setText(
                f"✓ Concluído! {n} arquivo(s) salvo(s) na pasta de destino.")
            self._show_open_folder()
        elif status == "cancelled":
            self.progress.setValue(0)
            self.label_status.setText("⏹ Download cancelado.")
        else:
            self.progress.setValue(0)
            self.label_status.setText("✗ Erro no download.")
            QMessageBox.warning(self, "Erro no download", error)

    def _show_open_folder(self) -> None:
        import os
        folder = self.job.output_dir if self.job else ""
        if not folder or not os.path.isdir(folder):
            return
        ret = QMessageBox.question(
            self, "Download concluído",
            "Arquivos salvos em:\n" + folder +
            "\n\nQuer abrir a pasta agora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            import subprocess
            import sys
            if sys.platform == "win32":
                os.startfile(folder)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
