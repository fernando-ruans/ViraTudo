"""Testes dos presets de formatos."""

from __future__ import annotations

from converter.presets import (
    ALL_INPUT_EXT, INPUT_AUDIO, INPUT_IMAGE, INPUT_VIDEO, OUTPUT_FORMATS,
    describe,
)


class TestPresets:
    def test_all_formats_have_required_keys(self):
        for key, fmt in OUTPUT_FORMATS.items():
            assert "label" in fmt, f"{key} sem label"
            assert "ext" in fmt, f"{key} sem ext"
            assert fmt["ext"] == key, f"{key}: ext != key"
            assert "video" in fmt and "audio" in fmt, f"{key} sem codecs"

    def test_at_least_15_formats(self):
        assert len(OUTPUT_FORMATS) >= 15

    def test_all_input_extensions_are_unique(self):
        assert len(ALL_INPUT_EXT) == len(set(ALL_INPUT_EXT))

    def test_input_extensions_complete(self):
        # Cobre os três grupos principais
        assert "mp4" in INPUT_VIDEO and "mkv" in INPUT_VIDEO
        assert "mp3" in INPUT_AUDIO and "flac" in INPUT_AUDIO
        assert "png" in INPUT_IMAGE and "jpg" in INPUT_IMAGE

    def test_audio_formats_have_no_video_codec(self):
        for key in ("mp3", "flac", "wav", "ogg", "opus", "m4a"):
            assert OUTPUT_FORMATS[key]["video"] is None, f"{key} tem vídeo?"
            assert OUTPUT_FORMATS[key]["audio"], f"{key} sem codec de áudio"

    def test_video_formats_have_both(self):
        for key in ("mp4", "mkv", "webm"):
            assert OUTPUT_FORMATS[key]["video"], f"{key} sem vídeo"
            assert OUTPUT_FORMATS[key]["audio"], f"{key} sem áudio"

    def test_describe_returns_friendly_label(self):
        assert "MP4" in describe("mp4")
        assert describe("nao_existe") == "nao_existe"
