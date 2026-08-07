"""Testes de logging e aceleração por hardware (Fase 4)."""

from __future__ import annotations

import logging

from converter.ffmpeg_core import (
    _HW_ENCODERS, encoders_disponiveis, melhor_encoder_video,
)


class TestLogging:
    def test_logging_setup_creates_file(self, tmp_path, monkeypatch):
        import converter.logging_setup as ls

        # Redireciona o diretório de logs para tmp_path
        monkeypatch.setattr(ls, "LOG_DIR", tmp_path)
        monkeypatch.setattr(ls, "LOG_FILE", tmp_path / "app.log")
        monkeypatch.setattr(ls, "_configured", False)

        logger = ls.setup_logging()
        assert logger.name == "viratudo"

        ls.log_conversion("in.mp4", "mp3", "done")
        ls.log_download("https://youtu.be/x", "mp3", "done")

        content = (tmp_path / "app.log").read_text(encoding="utf-8")
        assert "conversão" in content
        assert "download" in content
        assert "in.mp4" in content

    def test_logging_does_not_crash_without_setup(self):
        # Logar antes do setup não deve lançar (usa logger sem handler)
        from converter.ffmpeg_core import _log_job
        from converter import ConversionJob
        job = ConversionJob(input_path="x.mp4", output_path="x.mp3",
                            format_key="mp3", status="done")
        _log_job(job)  # não deve lançar exceção


class TestHardwareEncoders:
    def test_detection_returns_set(self):
        hw = encoders_disponiveis()
        assert isinstance(hw, set)
        for nome in hw:
            assert nome.startswith(("h264_", "hevc_", "av1_"))

    def test_best_encoder_is_known_or_none(self):
        enc = melhor_encoder_video("mp4")
        if enc:
            assert enc in encoders_disponiveis()

    def test_no_hw_returns_none(self, monkeypatch):
        monkeypatch.setattr("converter.ffmpeg_core._HW_ENCODERS", set())
        assert melhor_encoder_video("mp4") is None

    def test_audio_format_has_no_video_encoder(self):
        # Converter para mp3 nunca deve tentar encoder de vídeo
        from converter.ffmpeg_core import ConversionJob, _build_command
        job = ConversionJob(input_path="in.mp4", output_path="out.mp3",
                            format_key="mp3")
        cmd = _build_command(job, "ffmpeg")
        assert "-c:v" not in cmd
