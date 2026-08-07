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
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)

from converter import ConversionJob, find_ffmpeg, run_conversion
from converter.presets import (
    ALL_INPUT_EXT, INPUT_AUDIO, INPUT_IMAGE, INPUT_VIDEO, OUTPUT_FORMATS,
)


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
        col1.addWidget(self.combo_format)

        col2 = QVBoxLayout()
        col2.addWidget(QLabel("Pasta de destino:"))
        row_dst = QHBoxLayout()
        self.edit_dst = QLineEdit(str(Path.home() / "Conversor"))
        row_dst.addWidget(self.edit_dst)
        self.btn_browse = QPushButton("...")
        self.btn_browse.setFixedWidth(36)
        self.btn_browse.clicked.connect(self._browse_dst)
        row_dst.addWidget(self.btn_browse)
        col2.addLayout(row_dst)

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

        for job in self.jobs:
            ext = Path(job.input_path).suffix.lower().lstrip(".")
            base = Path(job.input_path).stem
            job.output_path = str(Path(dst_dir) / f"{base}.{fmt_key}")

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
