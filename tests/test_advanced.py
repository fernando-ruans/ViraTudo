"""Testes das funcionalidades avançadas da Fase 1: corte, qualidade,
escala, GIF configurável e concatenação."""

from __future__ import annotations

import subprocess

from converter.concat import _probe_codecs, _write_list_file, concat_files
from converter.ffmpeg_core import ConversionJob, run_conversion
from converter.presets import QUALITY_PROFILES, SCALE_OPTIONS

from helpers import probe, probe_format


class TestTrim:
    def test_cut_shortens_duration(self, sample_video, tmp_path):
        out = tmp_path / "cut.mp4"
        job = ConversionJob(input_path=str(sample_video),
                            output_path=str(out), format_key="mp4",
                            start_time=0.5, end_time=1.5)
        run_conversion(job)
        assert job.status == "done", job.error
        dur = float(probe_format(out, "duration"))
        assert 0.6 < dur < 1.4, f"duração inesperada: {dur}"

    def test_build_command_has_ss_and_to(self):
        job = ConversionJob(input_path="in.mp4", output_path="out.mp4",
                            format_key="mp4", start_time=1.5, end_time=3.0)
        from converter.ffmpeg_core import _build_command
        cmd = _build_command(job, "ffmpeg")
        assert "-ss" in cmd and "1.500" in cmd
        assert "-t" in cmd and "1.500" in cmd  # 3.0 - 1.5 = 1.5s de duração


class TestQuality:
    def test_mp3_320k_bitrate(self, sample_video, tmp_path):
        out = tmp_path / "out.mp3"
        job = ConversionJob(input_path=str(sample_video),
                            output_path=str(out), format_key="mp3",
                            quality="320 kbps (maior)")
        run_conversion(job)
        assert job.status == "done", job.error
        bitrate = probe(out, "a:0", "bit_rate")
        assert bitrate and int(bitrate) > 250_000

    def test_quality_profiles_exist_for_audio_and_video(self):
        for fmt in ("mp3", "mp4", "webm", "jpg"):
            assert fmt in QUALITY_PROFILES
            assert len(QUALITY_PROFILES[fmt]) >= 2

    def test_build_command_includes_quality_args(self):
        from converter.ffmpeg_core import _build_command
        job = ConversionJob(input_path="in.mp4", output_path="out.mp3",
                            format_key="mp3", quality="128 kbps (menor)")
        cmd = _build_command(job, "ffmpeg")
        assert "128k" in cmd


class TestScale:
    def test_video_resize(self, sample_video, tmp_path):
        out = tmp_path / "small.mp4"
        job = ConversionJob(input_path=str(sample_video),
                            output_path=str(out), format_key="mp4",
                            scale="160:120")
        run_conversion(job)
        assert job.status == "done", job.error
        dims = probe(out, "v:0", "width,height")
        assert dims == "160,120", f"dimensões inesperadas: {dims}"

    def test_image_resize(self, sample_image, tmp_path):
        out = tmp_path / "small.jpg"
        job = ConversionJob(input_path=str(sample_image),
                            output_path=str(out), format_key="jpg",
                            scale="50:37")
        run_conversion(job)
        assert job.status == "done", job.error
        dims = probe(out, "v:0", "width,height")
        assert dims == "50,37", f"dimensões inesperadas: {dims}"

    def test_scale_options_include_original(self):
        assert SCALE_OPTIONS["Original (sem alterar)"] is None
        assert SCALE_OPTIONS["1920x1080 (Full HD)"] == "1920:1080"


class TestGifOptions:
    def test_gif_fps_configurable(self, sample_video, tmp_path):
        out = tmp_path / "slow.gif"
        job = ConversionJob(input_path=str(sample_video),
                            output_path=str(out), format_key="gif",
                            gif_fps=10, gif_width=200)
        run_conversion(job)
        assert job.status == "done", job.error
        assert probe(out, "v:0") == "gif"

    def test_build_command_uses_fps_and_width(self):
        from converter.ffmpeg_core import _build_command
        job = ConversionJob(input_path="in.mp4", output_path="out.gif",
                            format_key="gif", gif_fps=8, gif_width=320)
        cmd = _build_command(job, "ffmpeg")
        vf = next(c for c in cmd if c.startswith("fps="))
        assert "fps=8" in vf and "scale=320:-1" in vf


class TestConcat:
    def test_write_list_file_escapes(self, tmp_path):
        lista = tmp_path / "lista.txt"
        _write_list_file([r"C:\pasta com espaço\a.mp4", "b.mp4"], lista)
        content = lista.read_text(encoding="utf-8")
        assert "file '" in content
        assert "a.mp4" in content

    def test_concat_two_videos(self, sample_video, tmp_path):
        # Cria um segundo vídeo de 1s
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=1",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
             "-c:v", "libx264", "-c:a", "aac", "-shortest",
             str(tmp_path / "seg.mp4")],
            check=True, capture_output=True)

        out = tmp_path / "joined.mp4"
        job = concat_files([str(sample_video), str(tmp_path / "seg.mp4")],
                           str(out))
        assert job.status == "done", job.error
        assert out.exists()
        dur = float(probe_format(out, "duration"))
        assert 2.5 < dur < 4.0, f"duração do concat inesperada: {dur}"

    def test_concat_requires_two_files(self, tmp_path):
        job = concat_files([str(tmp_path / "a.mp4")],
                           str(tmp_path / "out.mp4"))
        assert job.status == "error"

    def test_probe_codecs(self, sample_video):
        v, a = _probe_codecs(str(sample_video))
        assert v == "h264"
        assert a == "aac"
