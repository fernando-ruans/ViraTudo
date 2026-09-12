"""Aba de conversão de arquivos locais (offline).

Fluxo: selecionar arquivo(s) -> escolher formato de saída -> pasta de destino
-> converter. Múltiplos arquivos entram numa fila e rodam em sequência,
cada um na sua thread, com barra de progresso.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from converter import ConversionJob, find_ffmpeg, run_conversion
from converter.ffmpeg_core import encoders_disponiveis, validar_conversao
from converter.presets import (
    ALL_INPUT_EXT, INPUT_AUDIO, INPUT_IMAGE, INPUT_VIDEO, OUTPUT_FORMATS,
    QUALITY_PROFILES, SCALE_OPTIONS, VIDEO_FORMATS, classificar_entrada,
)
from ui import settings


class DropListWidget(QListWidget):
    """QListWidget que aceita arquivos arrastados do Explorer/Nautilus."""

    files_dropped = Signal(list)  # list[str]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p:
                paths.append(p)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class ConvertTab(QWidget):
    """Aba 'Converter Arquivos'."""

    _job_finished = Signal(int, str, str)  # index, status, mensagem
    _size_ready = Signal(object)  # resultado da estimativa (int bytes ou None)
    _progress = Signal(int)  # percentual médio dos jobs ativos

    def __init__(self, parent=None):
        super().__init__(parent)
        self.jobs: list[ConversionJob] = []
        self.current_index = 0
        self._running = False
        self._closing = False
        self._done_count = 0
        self._erros: list[tuple[str, str]] = []
        self._executor: ThreadPoolExecutor | None = None
        self._status_override = ""
        self._size_gen = 0  # geração da estimativa (evita resultado velho)
        self._build_ui()
        self._job_finished.connect(self._on_job_finished)
        self._size_ready.connect(self._on_size_ready)
        self._progress.connect(self._on_progress)
        # Qualidade dinâmica conforme o formato selecionado
        self.combo_format.currentIndexChanged.connect(
            self._refresh_quality_combo)
        self.combo_format.currentIndexChanged.connect(
            self._update_img_dur_visibility)
        self.combo_format.currentIndexChanged.connect(
            lambda *_: self._update_size_estimate())
        self.combo_quality.currentIndexChanged.connect(
            lambda *_: self._update_size_estimate())
        self.combo_scale.currentIndexChanged.connect(
            lambda *_: self._update_size_estimate())
        self._refresh_quality_combo()
        # Pré-carrega a detecção de encoders de hardware em background
        # (evita travamento de ~15s na primeira conversão)
        threading.Thread(target=encoders_disponiveis, daemon=True).start()

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

        self.list_files = DropListWidget()
        self.list_files.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        self.list_files.setMinimumHeight(120)
        self.list_files.files_dropped.connect(self._add_paths)
        self.list_files.setToolTip(
            "Arraste arquivos aqui ou use o botão acima.")
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

        # Duração p/ imagem -> vídeo (visível quando entrada é imagem e
        # o formato de saída é vídeo/GIF)
        self.row_dur = QHBoxLayout()
        self.dur_label = QLabel("🖼️ Duração do vídeo:")
        self.row_dur.addWidget(self.dur_label)
        self.spin_dur = QDoubleSpinBox()
        self.spin_dur.setRange(0.5, 600.0)
        self.spin_dur.setValue(5.0)
        self.spin_dur.setSuffix(" s")
        self.row_dur.addWidget(self.spin_dur)
        self.row_dur.addStretch(1)
        col2.addLayout(self.row_dur)
        self.dur_widgets = [self.dur_label, self.spin_dur]
        for w in self.dur_widgets:
            w.setVisible(False)

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
        self.btn_convert.clicked.connect(self._toggle_run)
        layout.addWidget(self.btn_convert)

        # ---- Estimativa de tamanho ----
        self.label_size = QLabel("")
        self.label_size.setStyleSheet("color: gray;")
        layout.addWidget(self.label_size)

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

    def _update_img_dur_visibility(self) -> None:
        """Mostra o campo de duração quando imagem -> vídeo/GIF."""
        fmt_key = self.combo_format.currentData()
        fmt = OUTPUT_FORMATS.get(fmt_key, {})
        is_video_out = bool(fmt.get("video")) or fmt_key == "gif"
        tem_imagem = any(
            classificar_entrada(j.input_path) == "image" for j in self.jobs)
        show = is_video_out and tem_imagem
        for w in self.dur_widgets:
            w.setVisible(show)

    def _add_files(self) -> None:
        filtro = "Mídia ({})".format(
            " ".join(f"*.{e}" for e in ALL_INPUT_EXT))
        files, _ = QFileDialog.getOpenFileNames(
            self, "Selecione arquivos para converter", "", filtro)
        if files:
            self._add_paths(files)

    def _add_paths(self, paths: list[str]) -> None:
        """Adiciona caminhos à fila (diálogo ou drag & drop)."""
        if self._running:
            # Durante a conversão a fila está congelada (os jobs já foram
            # submetidos ao executor); ignora para não travar o fechamento.
            return
        ignorados = 0
        for f in paths:
            if not os.path.isfile(f):
                ignorados += 1  # pastas e caminhos inexistentes não entram
                continue
            if not self._already_in_list(f):
                item = QListWidgetItem(f)
                item.setToolTip(f)
                self.list_files.addItem(item)
                self.jobs.append(ConversionJob(
                    input_path=f, output_path="", format_key="",
                    title=Path(f).name))
        if ignorados:
            self._status_override = (
                f"{ignorados} item(ns) ignorado(s) (só arquivos entram na fila).")
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
        self._size_gen += 1  # invalida estimativas pendentes em background
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
        if self._status_override:
            self.label_status.setText(self._status_override)
            self._status_override = ""
        elif n:
            self.label_status.setText(f"{n} arquivo(s) na fila.")
            self._update_img_dur_visibility()
            self._update_size_estimate()
        else:
            self.label_status.setText("Nenhum arquivo selecionado.")
            self.label_size.setText("")
            self._update_img_dur_visibility()

    def _update_size_estimate(self) -> None:
        """Estima o tamanho do 1º arquivo em background (não trava a GUI)."""
        if not self.jobs:
            self.label_size.setText("")
            return
        self._size_gen += 1
        gen = self._size_gen
        self.label_size.setText("⏳ Calculando tamanho estimado...")
        # Captura os valores na thread da GUI (ler widgets de outra thread
        # é thread-unsafe no Qt)
        fmt_key = self.combo_format.currentData()
        quality = self.combo_quality.currentData()
        path = self.jobs[0].input_path
        threading.Thread(
            target=self._size_worker, args=(gen, path, fmt_key, quality),
            daemon=True).start()

    def _size_worker(self, gen: int, path: str, fmt_key: str,
                     quality) -> None:
        from converter.ffmpeg_core import estimar_tamanho
        try:
            size = estimar_tamanho(path, fmt_key, quality)
        except Exception:
            size = None
        if not self._closing and gen == self._size_gen:  # descarta resultado antigo
            self._size_ready.emit(size)

    def _on_size_ready(self, size) -> None:
        if size:
            self.label_size.setText(
                f"📦 Saída estimada (1º arquivo): {size / 1024 / 1024:.1f} MB")
        else:
            self.label_size.setText("")

    # ------------------------------------------------------------- Execução
    def _toggle_run(self) -> None:
        """Converte se parado; cancela se rodando."""
        if self._running:
            self._cancel_all()
        else:
            self._start()

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

        # Valida combinações impossíveis (áudio->vídeo, imagem->áudio, etc.)
        problemas = []
        for job in self.jobs:
            ok, msg = validar_conversao(job.input_path, fmt_key)
            if not ok:
                problemas.append(f"• {Path(job.input_path).name}: {msg}")
        if problemas:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Combinação não suportada",
                "Estes arquivos não podem ser convertidos para "
                f"'{fmt_key}':\n\n" + "\n".join(problemas) +
                "\n\nEscolha outro formato de saída.")
            return

        # Persiste as preferências do usuário
        settings.set_convert_dst(self.edit_dst.text().strip() or ".")
        settings.set_convert_format(fmt_key)
        settings.set_convert_quality(quality or "")

        # Opções de corte (0 = sem corte)
        start = self.spin_start.value() if self.spin_start.value() > 0 else None
        end = self.spin_end.value() if self.spin_end.value() > 0 else None
        if start is not None and end is not None and start >= end:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Corte inválido",
                f"O início ({start:g}s) precisa ser menor que o fim ({end:g}s).\n"
                "Ajuste os valores de corte antes de converter.")
            return

        for job in self.jobs:
            ext = Path(job.input_path).suffix.lower().lstrip(".")
            base = Path(job.input_path).stem
            out = Path(dst_dir) / f"{base}.{fmt_key}"
            # Evita sobrescrever a entrada (ex.: mp4 -> mp4 recodificado)
            if os.path.abspath(out) == os.path.abspath(job.input_path):
                out = Path(dst_dir) / f"{base}_convertido.{fmt_key}"
            job.output_path = str(out)
            job.format_key = fmt_key
            job.start_time = start
            job.end_time = end
            job.quality = quality
            job.scale = scale
            job.gif_fps = self.spin_gif_fps.value()
            job.gif_width = self.spin_gif_width.value()
            # Imagem -> vídeo: usa a duração configurada
            if classificar_entrada(job.input_path) == "image" and (
                    fmt_key in VIDEO_FORMATS or fmt_key == "gif"):
                job.duration = self.spin_dur.value()

        self._running = True
        self._done_count = 0
        self._erros = []
        self.btn_convert.setText("⏹ Cancelar")
        self._refresh_state()

        # Fila paralela: N conversões simultâneas (padrão conservador = 2)
        n_workers = settings.get_parallel_jobs()
        self._executor = ThreadPoolExecutor(max_workers=n_workers,
                                            thread_name_prefix="viratudo")
        for i, job in enumerate(self.jobs):
            self._executor.submit(self._worker, i, job)
        self.label_status.setText(
            f"⏳ Preparando {len(self.jobs)} arquivo(s) "
            f"({n_workers} em paralelo)...")

    def _cancel_all(self) -> None:
        """Cancela todos os jobs (ativos e pendentes)."""
        for job in self.jobs:
            if job.status in ("pending", "running"):
                job.cancel()
        self.label_status.setText("Cancelando...")

    def begin_close(self) -> None:
        """Prepara a aba para o fechamento da janela (cancela jobs ativos).

        As threads de background checam `_closing` antes de emitir signals,
        evitando acessar widgets Qt já destruídos durante o shutdown.
        """
        self._closing = True
        if self._running:
            for job in self.jobs:
                if job.status in ("pending", "running"):
                    job.cancel()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    def _worker(self, index: int, job: ConversionJob) -> None:
        # O callback roda na thread do executor; NUNCA toca em widgets aqui —
        # emite o signal e a UI atualiza na main thread.
        def cb(pct, speed, eta):
            # Progresso: média dos percentuais dos jobs ativos
            if not self._closing and job.status == "running":
                active = [j for j in self.jobs
                          if j.status in ("pending", "running")]
                total = sum(j.progress for j in active if j.status == "running")
                self._progress.emit(int(total / max(len(active), 1)))
        run_conversion(job, callback=cb)
        if not self._closing:
            self._job_finished.emit(index, job.status, job.error)

    def _on_progress(self, pct: int) -> None:
        """Atualiza a barra de progresso (sempre na thread da GUI)."""
        self.progress.setValue(pct)

    def _on_job_finished(self, index: int, status: str, error: str) -> None:
        job = self.jobs[index]
        self._done_count += 1
        if status == "done":
            self.label_status.setText(
                f"[{self._done_count}/{len(self.jobs)}] ✓ {job.title} → "
                f"{Path(job.output_path).name}")
        elif status == "cancelled":
            self.label_status.setText(f"⏹ Cancelado: {job.title}")
        elif status == "error":
            self.label_status.setText(f"✗ Erro em {job.title}")
            # Acumula para um único aviso-resumo no fim (evita N modais).
            self._erros.append((job.title, error))
        if self._done_count >= len(self.jobs):
            self._finish_all()

    def _finish_all(self) -> None:
        self._running = False
        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None
        self.progress.setValue(100 if any(
            j.status == "done" for j in self.jobs) else 0)
        self.btn_convert.setText("🚀 Converter")
        ok = sum(1 for j in self.jobs if j.status == "done")
        falhas = sum(1 for j in self.jobs if j.status == "error")
        self._status_override = (
            f"Concluído: {ok} convertido(s), {falhas} com erro, "
            f"{len(self.jobs) - ok - falhas} cancelado(s).")
        self._refresh_state()
        if self._erros:
            from PySide6.QtWidgets import QMessageBox
            detalhe = "\n".join(
                f"• {titulo}: {erro}" for titulo, erro in self._erros[:10])
            if len(self._erros) > 10:
                detalhe += f"\n… e mais {len(self._erros) - 10} erro(s)."
            QMessageBox.warning(
                self, "Erros na conversão",
                f"{len(self._erros)} arquivo(s) falharam:\n\n{detalhe}")
            self._erros = []
        self._offer_open_folder()

    def _offer_open_folder(self) -> None:
        """Pergunta se o usuário quer abrir a pasta de destino."""
        from PySide6.QtWidgets import QMessageBox
        folder = self.edit_dst.text().strip()
        if not folder or not os.path.isdir(folder):
            return
        if not any(j.status == "done" for j in self.jobs):
            return
        ret = QMessageBox.question(
            self, "Conversão concluída",
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
