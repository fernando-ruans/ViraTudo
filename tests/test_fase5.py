"""Testes da Fase 5: combinações válidas de conversão, imagem -> vídeo,
coerção YouTube (qualidade x formato) e prévia com thumbnail."""

from __future__ import annotations

import subprocess
from pathlib import Path

from converter.ffmpeg_core import (
    ConversionJob, _build_command, run_conversion, validar_conversao,
)
from converter.presets import AUDIO_FORMATS, classificar_entrada
from converter.youtube import (
    VIDEO_QUALITIES, YouTubeJob, coerce_job_format, is_audio_only_quality,
)

from helpers import probe_format


class TestClassificarEntrada:
    def test_video(self):
        assert classificar_entrada("a.mp4") == "video"
        assert classificar_entrada("b.MKV") == "video"

    def test_audio(self):
        assert classificar_entrada("a.mp3") == "audio"
        assert classificar_entrada("b.flac") == "audio"

    def test_image(self):
        assert classificar_entrada("a.png") == "image"
        assert classificar_entrada("b.JPEG") == "image"

    def test_unknown(self):
        assert classificar_entrada("a.xyz") is None
        assert classificar_entrada("sem_extensao") is None


class TestValidarConversao:
    def test_audio_para_video_invalido(self):
        ok, msg = validar_conversao("som.mp3", "mp4")
        assert not ok and "áudio" in msg.lower()

    def test_audio_para_imagem_invalido(self):
        ok, _ = validar_conversao("som.mp3", "png")
        assert not ok

    def test_imagem_para_audio_invalido(self):
        ok, msg = validar_conversao("foto.png", "mp3")
        assert not ok and "imagem" in msg.lower()

    def test_imagem_para_video_ok(self):
        ok, _ = validar_conversao("foto.png", "mp4")
        assert ok

    def test_imagem_para_gif_ok(self):
        ok, _ = validar_conversao("foto.png", "gif")
        assert ok

    def test_imagem_para_imagem_ok(self):
        ok, _ = validar_conversao("foto.png", "jpg")
        assert ok

    def test_video_para_audio_ok(self):
        ok, _ = validar_conversao("v.mp4", "mp3")
        assert ok

    def test_video_para_video_ok(self):
        ok, _ = validar_conversao("v.mp4", "mkv")
        assert ok

    def test_extensao_desconhecida_deixa_passar(self):
        ok, _ = validar_conversao("arquivo.xyz", "mp4")
        assert ok


class TestImagemParaVideo:
    def test_build_command_tem_loop_e_duracao(self):
        job = ConversionJob(input_path="foto.png", output_path="out.mp4",
                            format_key="mp4", duration=5.0)
        cmd = _build_command(job, "ffmpeg")
        assert "-loop" in cmd and "1" in cmd
        assert "-t" in cmd and "5.000" in cmd

    def test_build_command_sem_loop_para_video(self):
        job = ConversionJob(input_path="in.mp4", output_path="out.mp4",
                            format_key="mp4")
        cmd = _build_command(job, "ffmpeg")
        assert "-loop" not in cmd

    def test_conversao_imagem_para_mp4(self, sample_image, tmp_path):
        out = tmp_path / "foto.mp4"
        job = ConversionJob(input_path=str(sample_image),
                            output_path=str(out), format_key="mp4",
                            duration=2.0)
        run_conversion(job)
        assert job.status == "done", job.error
        assert out.exists() and out.stat().st_size > 1_000
        dur = float(probe_format(out, "duration"))
        assert 1.5 < dur < 3.0, f"duração inesperada: {dur}"

    def test_conversao_imagem_para_gif(self, sample_image, tmp_path):
        out = tmp_path / "foto.gif"
        job = ConversionJob(input_path=str(sample_image),
                            output_path=str(out), format_key="gif",
                            duration=1.0, gif_fps=10, gif_width=100)
        run_conversion(job)
        assert job.status == "done", job.error
        assert out.exists() and out.stat().st_size > 200


class TestCoerceJobFormat:
    def test_somente_audio_com_mp4_vira_m4a(self):
        job = YouTubeJob(url="https://youtu.be/x", output_dir=".",
                         quality="bestaudio/best", output_format="mp4")
        coerce_job_format(job)
        assert job.output_format == "m4a"
        assert job.audio_only

    def test_somente_audio_com_mp3_mantem(self):
        job = YouTubeJob(url="https://youtu.be/x", output_dir=".",
                         quality="bestaudio/best", output_format="mp3")
        coerce_job_format(job)
        assert job.output_format == "mp3"
        assert job.audio_only

    def test_qualidade_video_com_mp4_mantem(self):
        job = YouTubeJob(url="https://youtu.be/x", output_dir=".",
                         quality="best", output_format="mp4")
        coerce_job_format(job)
        assert job.output_format == "mp4"
        assert not job.audio_only

    def test_preset_video_1080p_com_mp4_mantem_video(self):
        # Regressão: o seletor 'bestvideo+bestaudio' CONTÉM 'bestaudio' e era
        # classificado como somente áudio, baixando só o áudio.
        job = YouTubeJob(
            url="https://youtu.be/x", output_dir=".",
            quality="bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            output_format="mp4")
        coerce_job_format(job)
        assert job.output_format == "mp4"
        assert not job.audio_only

    def test_preset_video_360p_com_mkv_mantem_video(self):
        job = YouTubeJob(
            url="https://youtu.be/x", output_dir=".",
            quality="bestvideo[height<=360]+bestaudio/best[height<=360]",
            output_format="mkv")
        coerce_job_format(job)
        assert job.output_format == "mkv"
        assert not job.audio_only

    def test_todos_presets_de_video_nao_sao_audio_only(self):
        for quality in VIDEO_QUALITIES.values():
            if is_audio_only_quality(quality):
                continue
            job = YouTubeJob(url="https://youtu.be/x", output_dir=".",
                             quality=quality, output_format="mp4")
            coerce_job_format(job)
            assert job.output_format == "mp4", f"{quality} virou áudio"
            assert not job.audio_only, f"{quality} marcado como áudio"

    def test_audio_formats_sao_coerentes(self):
        # Todos os formatos de áudio do presets devem marcar audio_only
        for fmt in AUDIO_FORMATS:
            job = YouTubeJob(url="https://youtu.be/x", output_dir=".",
                             quality="best", output_format=fmt)
            coerce_job_format(job)
            assert job.audio_only, f"{fmt} deveria ser audio_only"


class TestYouTubeTabUI:
    """Testes offscreen da aba YouTube (sem rede)."""

    def _tab(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.youtube_tab import YouTubeTab
        return YouTubeTab()

    def test_sync_somente_audio_forca_formato_audio(self):
        tab = self._tab()
        idx = tab.combo_quality.findData("bestaudio/best")
        tab.combo_quality.setCurrentIndex(idx)
        tab._sync_quality_format()
        assert tab.combo_format.currentData() in (
            "mp3", "m4a", "flac", "wav", "ogg", "opus")

    def test_sync_formato_audio_forca_somente_audio(self):
        tab = self._tab()
        idx = tab.combo_format.findData("mp3")
        tab.combo_format.setCurrentIndex(idx)
        tab._sync_quality_format()
        assert "bestaudio" in (tab.combo_quality.currentData() or "")

    def test_sync_formato_video_com_qualidade_video_mantem(self):
        tab = self._tab()
        tab.combo_quality.setCurrentIndex(
            tab.combo_quality.findData("best"))
        tab.combo_format.setCurrentIndex(
            tab.combo_format.findData("mp4"))
        tab._sync_quality_format()
        assert tab.combo_format.currentData() == "mp4"
        assert "bestaudio" not in (tab.combo_quality.currentData() or "")

    def test_sync_preset_video_1080p_nao_redireciona_para_mp3(self):
        # Regressão: selecionar qualidade de vídeo não pode virar áudio.
        tab = self._tab()
        tab.combo_format.setCurrentIndex(
            tab.combo_format.findData("mp4"))
        idx = tab.combo_quality.findData(
            "bestvideo[height<=1080]+bestaudio/best[height<=1080]")
        tab.combo_quality.setCurrentIndex(idx)
        tab._sync_quality_format()
        assert tab.combo_format.currentData() == "mp4", \
            tab.combo_format.currentData()
        assert not is_audio_only_quality(
            tab.combo_quality.currentData() or "")

    def test_sync_preset_video_720p_com_formato_audio_vira_mp4(self):
        # Qualidade de vídeo + formato de áudio -> formato vira vídeo (mp4).
        tab = self._tab()
        tab.combo_format.setCurrentIndex(
            tab.combo_format.findData("mp3"))
        idx = tab.combo_quality.findData(
            "bestvideo[height<=720]+bestaudio/best[height<=720]")
        tab.combo_quality.setCurrentIndex(idx)
        tab._sync_quality_format()
        assert tab.combo_format.currentData() == "mp4"

    def test_thumb_label_existe_e_escondido(self):
        tab = self._tab()
        assert hasattr(tab, "label_thumb")
        assert not tab.label_thumb.isVisible()

    def _png_bytes(self) -> bytes:
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QImage, QColor
        img = QImage(64, 64, QImage.Format.Format_RGB32)
        img.fill(QColor(10, 20, 30))
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        return bytes(buf.data())

    def _fake_reply(self, dados: bytes, erro=0):
        from unittest import mock as _m
        from PySide6.QtNetwork import QNetworkReply
        reply = _m.Mock()
        reply.error.return_value = QNetworkReply.NetworkError(erro)
        reply.readAll.return_value = dados
        return reply

    def test_thumb_atual_exibida(self):
        from PySide6.QtNetwork import QNetworkReply
        tab = self._tab()
        reply = self._fake_reply(
            self._png_bytes(), QNetworkReply.NetworkError.NoError)
        tab._thumb_reply = reply
        tab._on_thumb_downloaded(reply)
        assert tab._thumb_reply is None  # reply consumido
        pix = tab.label_thumb.pixmap()
        assert pix is not None and not pix.isNull()

    def test_thumb_antiga_ignorada(self):
        from unittest import mock as _m
        tab = self._tab()
        reply = self._fake_reply(self._png_bytes())
        tab._thumb_reply = _m.Mock()  # outra requisição pendente
        tab._on_thumb_downloaded(reply)
        assert not tab.label_thumb.isVisible()

    def test_preview_antiga_ignorada(self):
        tab = self._tab()
        tab.edit_url.setText("https://youtu.be/BBBB")
        tab._on_preview_ready({"titulo": "Video A", "is_playlist": False},
                              "https://youtu.be/AAAA")
        assert tab.label_preview.text() == ""
        assert tab._preview_info is None

    def test_preview_atual_aplicada(self):
        tab = self._tab()
        tab.edit_url.setText("https://youtu.be/BBBB")
        tab._on_preview_ready({"titulo": "Video B", "is_playlist": False},
                              "https://youtu.be/BBBB")
        assert "Video B" in tab.label_preview.text()

    def test_select_tracks_url_invalida(self):
        from unittest import mock as _m
        tab = self._tab()
        tab.edit_url.setText("nao é uma url")
        with _m.patch("ui.youtube_tab.QMessageBox"):
            tab._select_tracks()
        assert "Carregando" not in tab.label_preview.text()

    def test_dialogo_avisa_limite_100(self):
        from unittest import mock as _m
        from PySide6.QtWidgets import QDialog, QLabel
        tab = self._tab()
        faixas = [{"index": i, "titulo": f"V{i}"} for i in range(1, 151)]

        notas = []

        def _fake_exec(self, *a):
            for child in self.findChildren(QLabel):
                if "100 de 150" in child.text():
                    notas.append(True)
            return QDialog.DialogCode.Rejected

        with _m.patch.object(QDialog, "exec", _fake_exec):
            tab._open_tracks_dialog(faixas)
        assert notas, "deveria avisar do limite de 100"
        assert tab._faixas_selecionadas is None

    def test_dialogo_sem_nota_quando_50(self):
        from unittest import mock as _m
        from PySide6.QtWidgets import QDialog, QLabel
        tab = self._tab()
        faixas = [{"index": i, "titulo": f"V{i}"} for i in range(1, 51)]

        notas = []

        def _fake_exec(self, *a):
            for child in self.findChildren(QLabel):
                if "100 de" in child.text():
                    notas.append(True)
            return QDialog.DialogCode.Rejected

        with _m.patch.object(QDialog, "exec", _fake_exec):
            tab._open_tracks_dialog(faixas)
        assert not notas

    def test_faixas_limpas_ao_trocar_url(self):
        tab = self._tab()
        tab._faixas_selecionadas = [1, 2, 3]
        tab.edit_url.setText("texto qualquer novo")
        tab._fetch_preview()
        assert tab._faixas_selecionadas is None

    def test_start_sem_playlist_nao_passa_faixas(self):
        from unittest import mock as _m
        tab = self._tab()
        tab._faixas_selecionadas = [1, 2]
        tab.chk_playlist.setChecked(False)
        tab.edit_url.setText("https://youtu.be/abc")
        tab.combo_quality.setCurrentIndex(
            tab.combo_quality.findData("best"))
        tab.combo_format.setCurrentIndex(
            tab.combo_format.findData("mp4"))
        with _m.patch.object(tab, "_worker", lambda job: None), \
                _m.patch("ui.youtube_tab.QMessageBox"):
            tab._start()
        assert tab.job is not None
        assert tab.job.faixas is None

    def test_direto_restringe_formatos_a_mp4_webm(self):
        tab = self._tab()
        tab.combo_format.setCurrentIndex(tab.combo_format.findData("mkv"))
        tab.chk_direto.setChecked(True)
        # Formato sai de mkv e vai para mp4 (nativo)
        assert tab.combo_format.currentData() == "mp4"
        for key in ("mkv", "gif"):
            idx = tab.combo_format.findData(key)
            assert not tab.combo_format.model().item(idx).isEnabled(), key

    def test_direto_repassa_flag_ao_job(self):
        tab = self._tab()
        tab.chk_direto.setChecked(True)
        tab.edit_url.setText("https://youtu.be/abc")
        tab.edit_dst.setText(str(tab.edit_dst.text()))
        tab.combo_quality.setCurrentIndex(
            tab.combo_quality.findData("best"))
        tab.combo_format.setCurrentIndex(
            tab.combo_format.findData("mp4"))
        tab._sync_quality_format()
        tab.job = None
        # Verifica o que _start montaria (mock p/ não disparar rede)
        from unittest import mock as _m
        with _m.patch.object(tab, "_worker", lambda job: None), \
                _m.patch("ui.youtube_tab.QMessageBox"):
            tab._start()
        assert tab.job is not None
        assert tab.job.direto is True


class TestConvertTabUI:
    """Testes offscreen da aba Converter (sem ffmpeg real)."""

    def _tab(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.convert_tab import ConvertTab
        return ConvertTab()

    def test_add_paths_ignorado_durante_conversao(self, tmp_path):
        tab = self._tab()
        alvo = tmp_path / "a.mp4"
        alvo.write_bytes(b"\x00")
        tab._running = True
        tab._add_paths([str(alvo)])
        assert not tab.jobs
        assert tab.list_files.count() == 0

    def test_add_paths_ignora_diretorios(self, tmp_path):
        tab = self._tab()
        alvo = tmp_path / "a.mp4"
        alvo.write_bytes(b"\x00")
        tab._add_paths([str(tmp_path), str(alvo)])
        assert tab.list_files.count() == 1
        assert "ignorado" in tab.label_status.text().lower()

    def test_start_bloqueia_corte_invalido(self, tmp_path):
        from unittest import mock as _m
        tab = self._tab()
        alvo = tmp_path / "a.mp4"
        alvo.write_bytes(b"\x00")
        tab._add_paths([str(alvo)])
        tab.spin_start.setValue(10)
        tab.spin_end.setValue(5)
        with _m.patch("PySide6.QtWidgets.QMessageBox.warning") as aviso:
            tab._start()
        assert aviso.called
        assert not tab._running

    def test_finish_all_desliga_executor(self):
        from concurrent.futures import ThreadPoolExecutor
        from unittest import mock as _m
        from converter import ConversionJob
        tab = self._tab()
        tab.jobs = [ConversionJob(input_path="a.mp4", output_path="a.mp3",
                                  format_key="mp3", title="a.mp4")]
        tab.jobs[0].status = "done"
        tab._running = True
        tab._done_count = 1
        tab._executor = ThreadPoolExecutor(max_workers=1)
        with _m.patch.object(tab, "_offer_open_folder", lambda: None):
            tab._finish_all()
        assert tab._executor is None
        assert not tab._running


class TestSettings:
    def test_parallel_jobs_clamp(self):
        from unittest import mock as _m
        from ui import settings as _s
        for valor, esperado in [(0, 1), (-3, 1), (100, 8), ("x", 2),
                                (None, 2), (4, 4)]:
            fake = _m.Mock()
            fake.value.return_value = valor
            with _m.patch.object(_s, "_settings", return_value=fake):
                assert _s.get_parallel_jobs() == esperado, valor
