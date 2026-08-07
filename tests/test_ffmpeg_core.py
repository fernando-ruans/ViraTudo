"""Testes do núcleo de conversão (ffmpeg_core)."""

from __future__ import annotations

import os

import pytest

from converter.ffmpeg_core import (
    ConversionJob, _build_command, find_ffmpeg, run_conversion,
)

from helpers import probe, probe_format


# ---------------------------------------------------------------- comandos
class TestBuildCommand:
    def test_audio_extract_uses_vn(self):
        job = ConversionJob(input_path="in.mp4", output_path="out.mp3",
                            format_key="mp3")
        cmd = _build_command(job, "ffmpeg")
        assert "-vn" in cmd

    def test_image_does_not_use_vn(self):
        # Regressão: bug antigo mandava -vn em imagens
        job = ConversionJob(input_path="in.png", output_path="out.jpg",
                            format_key="jpg")
        cmd = _build_command(job, "ffmpeg")
        assert "-vn" not in cmd
        assert "-c:v" in cmd and "mjpeg" in cmd

    def test_mp4_uses_libx264_or_hw(self):
        job = ConversionJob(input_path="in.mp4", output_path="out.mp4",
                            format_key="mp4")
        cmd = _build_command(job, "ffmpeg")
        # Pode usar libx264 (CPU) ou um encoder de hardware (nvenc/qsv/vaapi)
        v_enc = cmd[cmd.index("-c:v") + 1]
        assert v_enc in ("libx264",) or any(
            h in v_enc for h in ("nvenc", "qsv", "vaapi", "videotoolbox",
                                 "amf")), f"encoder inesperado: {v_enc}"
        assert "aac" in cmd

    def test_gif_uses_palette(self):
        job = ConversionJob(input_path="in.mp4", output_path="out.gif",
                            format_key="gif")
        cmd = _build_command(job, "ffmpeg")
        assert any("palettegen" in c for c in cmd)

    def test_unknown_format_raises(self):
        job = ConversionJob(input_path="in.mp4", output_path="out.xyz",
                            format_key="xyz")
        with pytest.raises(ValueError):
            _build_command(job, "ffmpeg")


# ---------------------------------------------------------------- execução
class TestRunConversion:
    def test_mp4_to_mp3(self, sample_video, tmp_path):
        out = tmp_path / "out.mp3"
        job = ConversionJob(input_path=str(sample_video),
                            output_path=str(out), format_key="mp3")
        run_conversion(job)
        assert job.status == "done", job.error
        assert out.exists() and out.stat().st_size > 1_000
        assert probe(out) == "mp3"

    def test_mp4_to_gif(self, sample_video, tmp_path):
        out = tmp_path / "out.gif"
        job = ConversionJob(input_path=str(sample_video),
                            output_path=str(out), format_key="gif")
        run_conversion(job)
        assert job.status == "done", job.error
        assert out.exists()
        assert probe(out, "v:0") == "gif"

    def test_png_to_jpg(self, sample_image, tmp_path):
        out = tmp_path / "img.jpg"
        job = ConversionJob(input_path=str(sample_image),
                            output_path=str(out), format_key="jpg")
        run_conversion(job)
        assert job.status == "done", job.error
        assert out.exists() and out.stat().st_size > 500
        assert probe(out, "v:0") == "mjpeg"

    def test_missing_input_gives_friendly_error(self, tmp_path):
        job = ConversionJob(input_path=str(tmp_path / "nao_existe.mp4"),
                            output_path=str(tmp_path / "out.mp3"),
                            format_key="mp3")
        run_conversion(job)
        assert job.status == "error"
        assert job.error  # mensagem amigável preenchida

    def test_cancel_marks_cancelled(self, sample_video, tmp_path):
        out = tmp_path / "out.mp4"
        job = ConversionJob(input_path=str(sample_video),
                            output_path=str(out), format_key="mp4")
        job.cancel()  # cancela antes de rodar
        run_conversion(job)
        assert job.status in ("cancelled", "error")
        # se cancelado, não deve deixar arquivo parcial
        assert not out.exists() or job.status == "error"

    def test_progress_callback_fires(self, sample_video, tmp_path):
        out = tmp_path / "out.mp3"
        job = ConversionJob(input_path=str(sample_video),
                            output_path=str(out), format_key="mp3")
        seen: list[float] = []
        run_conversion(job, callback=lambda p, s, e: seen.append(p))
        assert job.status == "done"
        assert seen and seen[-1] == 100.0


# ---------------------------------------------------------------- utilitários
class TestHelpers:
    def test_find_ffmpeg_returns_path(self):
        ffmpeg = find_ffmpeg()
        assert ffmpeg and os.path.exists(ffmpeg)

    def test_probe_duration(self, sample_video):
        from converter.ffmpeg_core import probe_duration
        dur = probe_duration(str(sample_video))
        assert dur and 1.5 < dur < 3.0
