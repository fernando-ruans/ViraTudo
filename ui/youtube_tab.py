"""Aba YouTube: baixar vídeo/áudio do YouTube e converter localmente.

Opções: qualidade (até 4K), formato de saída (vídeo ou áudio), pasta de
destino. Playlists são suportadas (opção marcável). O download usa yt-dlp
e a conversão usa o FFmpeg local.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from converter import (
    VIDEO_QUALITIES, YouTubeJob, is_youtube_url, run_download,
)
from converter.presets import OUTPUT_FORMATS
from ui import settings

# Formatos que fazem sentido no YouTube, separados por categoria.
# A qualidade e o formato são sincronizados: "Somente áudio" só permite
# formatos de áudio, e formatos de vídeo só com qualidade de vídeo.
YT_VIDEO_FORMATS = ["mp4", "mkv", "webm", "gif"]
YT_AUDIO_FORMATS = ["mp3", "m4a", "flac", "wav", "ogg", "opus"]
YT_FORMATS = YT_VIDEO_FORMATS + YT_AUDIO_FORMATS
# Rótulos traduzidos: m4a tem label próprio em OUTPUT_FORMATS
_AUDIO_LABELS = {
    "mp3": "MP3 (192 kbps)",
    "m4a": "M4A (AAC) — iTunes/iPhone",
    "flac": "FLAC (sem perdas)",
    "wav": "WAV (PCM 16-bit)",
    "ogg": "OGG (Vorbis)",
    "opus": "Opus (melhor p/ fala/música)",
}


def _format_label(key: str) -> str:
    fmt = OUTPUT_FORMATS.get(key)
    if fmt:
        return fmt["label"]
    return _AUDIO_LABELS.get(key, key)


def _format_duration(segundos: float) -> str:
    """Formata duração em 'M:SS' ou 'H:MM:SS'."""
    s = int(segundos)
    h, resto = divmod(s, 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class YouTubeTab(QWidget):
    """Aba 'YouTube'."""

    _job_finished = Signal(str, str)  # status, mensagem
    _thumb_ready = Signal(str)  # URL da thumbnail para carregar

    def __init__(self, parent=None):
        super().__init__(parent)
        self.job: YouTubeJob | None = None
        self._running = False
        self._faixas_selecionadas: list[int] | None = None
        self._preview_info: dict | None = None
        self._build_ui()
        self._job_finished.connect(self._on_job_finished)
        self._thumb_ready.connect(self._load_thumb)
        # Rede para baixar a thumbnail (assíncrono, não bloqueia a UI)
        self._net = QNetworkAccessManager(self)
        self._net.finished.connect(self._on_thumb_downloaded)
        # Prévia automática com debounce (600ms após parar de digitar)
        from PySide6.QtCore import QTimer
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(600)
        self._preview_timer.timeout.connect(self._fetch_preview)
        self.edit_url.textChanged.connect(
            lambda *_: self._preview_timer.start())
        self.chk_playlist.toggled.connect(self._on_playlist_toggled)
        # Sincroniza qualidade <-> formato (evita combinações impossíveis)
        self.combo_quality.currentIndexChanged.connect(
            self._sync_quality_format)
        self.combo_format.currentIndexChanged.connect(
            self._sync_quality_format)
        # Corrige estado herdado do QSettings (ex.: "Somente áudio" salvo
        # com formato mp4) — o signal não dispara se o índice já é o mesmo.
        self._sync_quality_format()

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

        # Prévia automática (título, duração) com debounce
        row_preview = QHBoxLayout()
        self.label_thumb = QLabel()
        self.label_thumb.setFixedSize(160, 90)
        self.label_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_thumb.setStyleSheet(
            "border: 1px solid #888; border-radius: 4px; background: #2a2a2a;")
        self.label_thumb.setVisible(False)
        row_preview.addWidget(self.label_thumb, 0,
                              Qt.AlignmentFlag.AlignTop)
        self.label_preview = QLabel("")
        self.label_preview.setStyleSheet("color: #4a90d9; font-weight: bold;")
        self.label_preview.setWordWrap(True)
        row_preview.addWidget(self.label_preview, 1)
        v.addLayout(row_preview)

        row_playlist = QHBoxLayout()
        self.chk_playlist = QCheckBox("É uma playlist (baixar todos os vídeos)")
        row_playlist.addWidget(self.chk_playlist)
        self.btn_tracks = QPushButton("🎵 Selecionar faixas...")
        self.btn_tracks.setEnabled(False)
        self.btn_tracks.clicked.connect(self._select_tracks)
        row_playlist.addWidget(self.btn_tracks)
        row_playlist.addStretch(1)
        v.addLayout(row_playlist)
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
            self.combo_format.addItem(_format_label(key), key)
        f_idx = self.combo_format.findData(settings.get_yt_format())
        if f_idx < 0:
            f_idx = self.combo_format.findData("mp4")
        self.combo_format.setCurrentIndex(max(f_idx, 0))
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

        # ---- Opções extras ----
        row_extra = QHBoxLayout()
        self.chk_subtitles = QCheckBox("💬 Baixar legendas (PT/EN, se houver)")
        row_extra.addWidget(self.chk_subtitles)
        self.chk_keep = QCheckBox("📦 Manter o arquivo original")
        row_extra.addWidget(self.chk_keep)
        row_extra.addStretch(1)
        layout.addLayout(row_extra)

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

    def _sync_quality_format(self) -> None:
        """Garante que qualidade e formato de saída sempre 'casam'.

        A última mudança do usuário vence:
        - Mudou a qualidade p/ áudio (ou vídeo) -> ajusta o formato.
        - Mudou o formato p/ áudio (ou vídeo) -> ajusta a qualidade.
        - Chamada no __init__ (sem sender) -> o formato salvo manda.
        """
        sender = self.sender()
        quality = self.combo_quality.currentData() or ""
        fmt = self.combo_format.currentData() or ""
        q_audio = "bestaudio" in quality
        f_audio = fmt in YT_AUDIO_FORMATS

        if sender is self.combo_quality:
            # Usuário mexeu na qualidade: o formato acompanha
            if q_audio and not f_audio:
                self.combo_format.setCurrentIndex(
                    self.combo_format.findData("mp3"))
            elif not q_audio and f_audio:
                self.combo_format.setCurrentIndex(
                    self.combo_format.findData("mp4"))
        else:
            # Formato mudou (ou estado inicial): a qualidade acompanha
            if f_audio and not q_audio:
                self.combo_quality.setCurrentIndex(
                    self.combo_quality.findData(
                        VIDEO_QUALITIES["Somente áudio"]))
            elif not f_audio and q_audio:
                self.combo_quality.setCurrentIndex(
                    self.combo_quality.findData("best"))

    def _fetch_preview(self) -> None:
        """Busca título/duração do vídeo ao parar de digitar (thread)."""
        from converter.youtube import preview_video
        url = self.edit_url.text().strip()
        if not is_youtube_url(url) or self._running:
            self.label_preview.setText("")
            self.label_thumb.setVisible(False)
            self.btn_tracks.setEnabled(False)
            return
        self.label_preview.setText("🔍 Buscando informações...")
        self.label_thumb.setVisible(False)
        threading.Thread(
            target=self._preview_worker, args=(url,), daemon=True).start()

    def _preview_worker(self, url: str) -> None:
        from converter.youtube import preview_video
        try:
            info = preview_video(url)
            self._preview_info = info
            if info.get("is_playlist"):
                texto = (f"📋 {info['titulo']} — {info['total_faixas']} faixas")
                self.btn_tracks.setEnabled(True)
            else:
                dur = info.get("duracao")
                dur_s = _format_duration(dur) if dur else ""
                res = ", ".join(info.get("resolucoes", [])[:4])
                texto = f"🎬 {info['titulo']}"
                if dur_s:
                    texto += f" — {dur_s}"
                if res:
                    texto += f"  ({res})"
                self.btn_tracks.setEnabled(False)
            self.label_preview.setText(texto)
            thumb = info.get("thumbnail") or ""
            self._thumb_ready.emit(thumb)
        except Exception as e:
            self._preview_info = None
            self.label_preview.setText("")
            self.label_thumb.setVisible(False)
            self.btn_tracks.setEnabled(False)
            # silencioso: apenas não mostra prévia

    def _load_thumb(self, url: str) -> None:
        """Dispara o download da thumbnail (thread da GUI, assíncrono)."""
        if not url:
            self.label_thumb.setVisible(False)
            return
        self._net.get(QNetworkRequest(QUrl(url)))

    def _on_thumb_downloaded(self, reply: QNetworkReply) -> None:
        """Exibe a thumbnail baixada (ou esconde se falhou)."""
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = bytes(reply.readAll())
                pix = QPixmap()
                if pix.loadFromData(data):
                    self.label_thumb.setPixmap(
                        pix.scaled(self.label_thumb.size(),
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation))
                    self.label_thumb.setVisible(True)
                else:
                    self.label_thumb.setVisible(False)
            else:
                self.label_thumb.setVisible(False)
        finally:
            reply.deleteLater()

    def _on_playlist_toggled(self, checked: bool) -> None:
        self.btn_tracks.setEnabled(checked and bool(
            getattr(self, "_preview_info", None) or
            is_youtube_url(self.edit_url.text().strip())))

    def _select_tracks(self) -> None:
        """Abre diálogo com checkboxes das faixas da playlist."""
        from converter.youtube import listar_playlist
        url = self.edit_url.text().strip()
        self.label_preview.setText("🔍 Carregando faixas da playlist...")
        threading.Thread(
            target=self._tracks_worker, args=(url,), daemon=True).start()

    def _tracks_worker(self, url: str) -> None:
        from converter.youtube import listar_playlist
        try:
            faixas = listar_playlist(url)
            self._playlist_faixas = faixas
            # Abre o diálogo na thread da GUI
            self._open_tracks_dialog(faixas)
        except Exception as e:
            self.label_preview.setText("")
            QMessageBox.warning(
                self, "Erro ao listar playlist",
                f"Não foi possível carregar as faixas:\n{str(e)[:200]}")

    def _open_tracks_dialog(self, faixas: list[dict]) -> None:
        """Diálogo com checkboxes para selecionar faixas (limite 100)."""
        from PySide6.QtWidgets import (
            QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("Selecionar faixas da playlist")
        dlg.resize(520, 420)
        lay = QVBoxLayout(dlg)

        lista = QListWidget(dlg)
        for f in faixas[:100]:
            dur = _format_duration(f["duracao"]) if f.get("duracao") else ""
            item = QListWidgetItem(
                f"{f['index']:>3}. {f['titulo']}" + (f"  ({dur})" if dur else ""))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, f["index"])
            lista.addItem(item)
        lay.addWidget(lista)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            sel = []
            for i in range(lista.count()):
                item = lista.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    sel.append(item.data(Qt.ItemDataRole.UserRole))
            self._faixas_selecionadas = sel or None
            n = len(self._faixas_selecionadas or [])
            self.label_preview.setText(
                f"🎵 {n} faixa(s) selecionada(s) da playlist.")

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

        # Garante coerência qualidade <-> formato antes de montar o job
        self._sync_quality_format()

        self.job = YouTubeJob(
            url=url,
            output_dir=self.edit_dst.text().strip() or ".",
            quality=self.combo_quality.currentData(),
            output_format=self.combo_format.currentData(),
            is_playlist=self.chk_playlist.isChecked(),
            faixas=self._faixas_selecionadas,
            manter_original=self.chk_keep.isChecked(),
            legendas=self.chk_subtitles.isChecked(),
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
