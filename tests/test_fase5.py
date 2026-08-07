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
