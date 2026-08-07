"""Aba de conversão de arquivos locais (offline).

Fluxo: selecionar arquivo(s) -> escolher formato de saída -> pasta de destino
-> converter. Múltiplos arquivos entram numa fila e rodam em sequência,
cada um na sua thread, com barra de progresso.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from converter import ConversionJob, find_ffmpeg, run_conversion
from converter.presets import (
    ALL_INPUT_EXT, INPUT_AUDIO, INPUT_IMAGE, INPUT_VIDEO, OUTPUT_FORMATS,
    QUALITY_PROFILES, SCALE_OPTIONS,
)
from ui import settings


class ConvertTab(QWidget):
    """Aba 'Converter Arquivos'."""

    _job_finished = Signal(str, str)  # status, mensagem

    def __init__(self, parent=None):
        super().__init__(parent)
        self.jobs: list[ConversionJob] = []
        self.current_index = 0
        self._running = False
        self._build_ui()
        self._job_finished.connect(self._on_job_finished)
        # Qualidade dinâmica conforme o formato selecionado
        self.combo_format.currentIndexChanged.connect(
            self._refresh_quality_combo)
        self._refresh_quality_combo()

    # ------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ---- Seleção de arquivos ----
        gb_input = QGroupBox("1. Arquivos de entrada")
        v = QVBoxLayout(gb_input)
        row = QHBoxLayout()
        self.btn_add = QPushButton("➕ Adicionar arquivos...")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_clear = QPushButton("Limpar lista")
        self.btn_clear.clicked.connect(self._clear_files)
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_clear)
        row.addStretch(1)
        v.addLayout(row)

        self.list_files = QListWidget()
        self.list_files.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        self.list_files.setMinimumHeight(120)
        v.addWidget(self.list_files)
        layout.addWidget(gb_input)

        # ---- Opções de saída ----
        gb_out = QGroupBox("2. Opções de saída")
        grid = QHBoxLayout(gb_out)

        col1 = QVBoxLayout()
        col1.addWidget(QLabel("Formato:"))
        self.combo_format = QComboBox()
        for key, fmt in OUTPUT_FORMATS.items():
            self.combo_format.addItem(fmt["label"], key)
        # Restaura o último formato usado
        idx = self.combo_format.findData(settings.get_convert_format())
        if idx >= 0:
            self.combo_format.setCurrentIndex(idx)
        col1.addWidget(self.combo_format)

        col1.addWidget(QLabel("Qualidade:"))
        self.combo_quality = QComboBox()
        col1.addWidget(self.combo_quality)

        col1.addWidget(QLabel("Redimensionar:"))
        self.combo_scale = QComboBox()
        for label, value in SCALE_OPTIONS.items():
            self.combo_scale.addItem(label, value)
        col1.addWidget(self.combo_scale)

        col2 = QVBoxLayout()
        col2.addWidget(QLabel("Pasta de destino:"))
        row_dst = QHBoxLayout()
        self.edit_dst = QLineEdit(settings.get_convert_dst())
        row_dst.addWidget(self.edit_dst)
        self.btn_browse = QPushButton("...")
        self.btn_browse.setFixedWidth(36)
        self.btn_browse.clicked.connect(self._browse_dst)
        row_dst.addWidget(self.btn_browse)
        col2.addLayout(row_dst)

        # Corte
        col2.addWidget(QLabel("Cortar trecho (segundos):"))
        row_cut = QHBoxLayout()
        row_cut.addWidget(QLabel("De"))
        self.spin_start = QDoubleSpinBox()
        self.spin_start.setRange(0, 99999)
        self.spin_start.setDecimals(1)
        self.spin_start.setSpecialValueText("início")
        self.spin_start.setValue(0)
        row_cut.addWidget(self.spin_start, 1)
        row_cut.addWidget(QLabel("até"))
        self.spin_end = QDoubleSpinBox()
        self.spin_end.setRange(0, 99999)
        self.spin_end.setDecimals(1)
        self.spin_end.setSpecialValueText("fim")
        self.spin_end.setValue(0)
        row_cut.addWidget(self.spin_end, 1)
        col2.addLayout(row_cut)

        # Opções de GIF (visíveis apenas quando formato == gif)
        self.row_gif = QHBoxLayout()
        self.gif_label = QLabel("GIF:")
        self.row_gif.addWidget(self.gif_label)
        self.spin_gif_fps = QSpinBox()
        self.spin_gif_fps.setRange(1, 60)
        self.spin_gif_fps.setValue(15)
        self.spin_gif_fps.setSuffix(" fps")
        self.row_gif.addWidget(self.spin_gif_fps)
        self.spin_gif_width = QSpinBox()
        self.spin_gif_width.setRange(64, 4096)
        self.spin_gif_width.setValue(480)
        self.spin_gif_width.setSuffix(" px")
        self.row_gif.addWidget(self.spin_gif_width)
        self.row_gif.addStretch(1)
        col2.addLayout(self.row_gif)
        self.gif_widgets = [self.gif_label, self.spin_gif_fps,
                            self.spin_gif_width]

        grid.addLayout(col1, 1)
        grid.addLayout(col2, 3)
        layout.addWidget(gb_out)

        # ---- Progresso ----
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.label_status = QLabel("Nenhum arquivo selecionado.")
        layout.addWidget(self.label_status)

        # ---- Ação ----
        self.btn_convert = QPushButton("🚀 Converter")
        self.btn_convert.setEnabled(False)
        self.btn_convert.clicked.connect(self._start)
        layout.addWidget(self.btn_convert)

    # ------------------------------------------------------------- Eventos
    def _refresh_quality_combo(self) -> None:
        """Popula o combo de qualidade com os perfis do formato atual."""
        fmt_key = self.combo_format.currentData()
        self.combo_quality.clear()
        profiles = QUALITY_PROFILES.get(fmt_key, {})
        if profiles:
            self.combo_quality.addItem("Padrão do formato", None)
            for label in profiles:
                self.combo_quality.addItem(label, label)
            self.combo_quality.setEnabled(True)
        else:
            self.combo_quality.addItem("Padrão do formato", None)
            self.combo_quality.setEnabled(False)
        # Restaura qualidade salva se ainda existir
        saved = settings.get_convert_quality()
        idx = self.combo_quality.findData(saved)
        if idx >= 0:
            self.combo_quality.setCurrentIndex(idx)
        # Opções de GIF só aparecem quando o formato é GIF
        is_gif = fmt_key == "gif"
        for w in self.gif_widgets:
            w.setVisible(is_gif)

    def _add_files(self) -> None:
        filtro = "Mídia ({})".format(
            " ".join(f"*.{e}" for e in ALL_INPUT_EXT))
        files, _ = QFileDialog.getOpenFileNames(
            self, "Selecione arquivos para converter", "", filtro)
        if not files:
            return
        for f in files:
            if not self._already_in_list(f):
                item = QListWidgetItem(f)
                item.setToolTip(f)
                self.list_files.addItem(item)
                self.jobs.append(ConversionJob(
                    input_path=f, output_path="", format_key="",
                    title=Path(f).name))
        self._refresh_state()

    def _already_in_list(self, path: str) -> bool:
        for i in range(self.list_files.count()):
            if self.list_files.item(i).text() == path:
                return True
        return False

    def _clear_files(self) -> None:
        if self._running:
            return
        self.list_files.clear()
        self.jobs.clear()
        self.progress.setValue(0)
        self._refresh_state()

    def _browse_dst(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Pasta de destino", self.edit_dst.text())
        if d:
            self.edit_dst.setText(d)

    def _refresh_state(self) -> None:
        n = self.list_files.count()
        self.btn_convert.setEnabled(n > 0 and not self._running)
        self.btn_add.setEnabled(not self._running)
        self.btn_clear.setEnabled(not self._running)
        if n:
            self.label_status.setText(f"{n} arquivo(s) na fila.")
        else:
            self.label_status.setText("Nenhum arquivo selecionado.")

    # ------------------------------------------------------------- Execução
    def _start(self) -> None:
        if self._running or not self.jobs:
            return
        if not find_ffmpeg():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "FFmpeg não encontrado",
                "Instale o FFmpeg e adicione ao PATH para usar o conversor.")
            return
        dst_dir = self.edit_dst.text().strip() or "."
        fmt_key = self.combo_format.currentData()
        quality = self.combo_quality.currentData()
        scale = self.combo_scale.currentData()

        # Persiste as preferências do usuário
        settings.set_convert_dst(self.edit_dst.text().strip() or ".")
        settings.set_convert_format(fmt_key)
        settings.set_convert_quality(quality or "")

        # Opções de corte (0 = sem corte)
        start = self.spin_start.value() if self.spin_start.value() > 0 else None
        end = self.spin_end.value() if self.spin_end.value() > 0 else None

        for job in self.jobs:
            ext = Path(job.input_path).suffix.lower().lstrip(".")
            base = Path(job.input_path).stem
            job.output_path = str(Path(dst_dir) / f"{base}.{fmt_key}")
            job.format_key = fmt_key
            job.start_time = start
            job.end_time = end
            job.quality = quality
            job.scale = scale
            job.gif_fps = self.spin_gif_fps.value()
            job.gif_width = self.spin_gif_width.value()

        self._running = True
        self.current_index = 0
        self.btn_convert.setText("⏹ Cancelar")
        self._refresh_state()
        self._run_next()

    def _run_next(self) -> None:
        if self.current_index >= len(self.jobs):
            self._finish_all()
            return
        job = self.jobs[self.current_index]
        self.label_status.setText(
            f"[{self.current_index + 1}/{len(self.jobs)}] Convertendo: "
            f"{job.title}  →  .{job.format_key}")
        t = threading.Thread(target=self._worker, args=(job,), daemon=True)
        t.start()

    def _worker(self, job: ConversionJob) -> None:
        def cb(pct, speed, eta):
            self.progress.setValue(int(pct))
        run_conversion(job, callback=cb)
        self._job_finished.emit(job.status, job.error)

    def _on_job_finished(self, status: str, error: str) -> None:
        job = self.jobs[self.current_index]
        if status == "done":
            self.label_status.setText(
                f"✓ {job.title} → {job.output_path}")
        elif status == "cancelled":
            self.label_status.setText(f"⏹ Cancelado: {job.title}")
        elif status == "error":
            self.label_status.setText(f"✗ Erro em {job.title}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erro na conversão",
                                f"{job.title}\n\n{error}")
        self.current_index += 1
        self.progress.setValue(0)
        self._run_next()

    def _finish_all(self) -> None:
        self._running = False
        self.progress.setValue(0)
        self.btn_convert.setText("🚀 Converter")
        ok = sum(1 for j in self.jobs if j.status == "done")
        self.label_status.setText(
            f"Concluído: {ok}/{len(self.jobs)} arquivo(s) convertido(s).")
        self._refresh_state()
