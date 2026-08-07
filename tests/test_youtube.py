"""Testes do módulo YouTube (sem rede — só lógica pura)."""

from __future__ import annotations

from converter.youtube import (
    VIDEO_QUALITIES, _cookies_failure_hint, _humanize_ytdlp_error,
    _safe_filename, is_youtube_url,
)


class TestURLDetection:
    def test_accepts_watch_url(self):
        assert is_youtube_url("https://www.youtube.com/watch?v=jNQXAC9IVRw")

    def test_accepts_short_url(self):
        assert is_youtube_url("https://youtu.be/abc123XYZ")

    def test_accepts_shorts(self):
        assert is_youtube_url("https://youtube.com/shorts/xyz789")

    def test_accepts_playlist(self):
        assert is_youtube_url("https://www.youtube.com/playlist?list=PLx123")

    def test_accepts_live(self):
        assert is_youtube_url("https://www.youtube.com/live/abc123")

    def test_rejects_other_sites(self):
        for url in ("https://vimeo.com/123", "https://google.com",
                    "https://youtube.com", ""):
            assert not is_youtube_url(url)


class TestQualityPresets:
    def test_has_all_major_qualities(self):
        for label in ("Melhor disponível", "1080p (Full HD)", "720p (HD)",
                      "360p", "Somente áudio"):
            assert label in VIDEO_QUALITIES

    def test_at_least_8_qualities(self):
        assert len(VIDEO_QUALITIES) >= 8


class TestErrorHumanization:
    def test_bot_check_message(self):
        err = "ERROR: [youtube] x: Sign in to confirm you're not a bot."
        msg = _humanize_ytdlp_error(err)
        assert "verificação" in msg or "anti-bot" in msg

    def test_unavailable_video(self):
        msg = _humanize_ytdlp_error("ERROR: Video unavailable")
        assert "indisponível" in msg

    def test_unsupported_url(self):
        msg = _humanize_ytdlp_error("Unsupported URL: https://x.com")
        assert "URL não suportada" in msg

    def test_network_error(self):
        msg = _humanize_ytdlp_error("ERROR: timed out")
        assert "rede" in msg

    def test_cookies_hint_browser_open(self):
        hint = _cookies_failure_hint(
            "chrome: ERROR: Could not copy Chrome cookie database")
        assert "navegador" in hint

    def test_cookies_hint_dpapi(self):
        hint = _cookies_failure_hint(
            "edge: ERROR: Failed to decrypt with DPAPI")
        assert "descriptografados" in hint


class TestSafeFilename:
    def test_strips_windows_invalid_chars(self):
        assert _safe_filename('a/b\\c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"

    def test_empty_becomes_video(self):
        assert _safe_filename("   ") == "video"

    def test_limits_length(self):
        assert len(_safe_filename("x" * 500)) <= 150
