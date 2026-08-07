"""Testes do módulo YouTube (sem rede — só lógica pura)."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest import mock

import pytest
from yt_dlp.utils import DownloadCancelled

from converter.youtube import (
    VIDEO_QUALITIES, YouTubeJob, _cookies_failure_hint, _faixas_para_string,
    _humanize_ytdlp_error, _make_hook, _safe_filename, is_youtube_url,
    run_download,
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


class TestFaixasParaString:
    def test_sequential_ranges(self):
        assert _faixas_para_string([1, 2, 3, 4, 5]) == "1-5"

    def test_mixed(self):
        assert _faixas_para_string([1, 3, 5, 6, 7]) == "1,3,5-7"

    def test_single(self):
        assert _faixas_para_string([4]) == "4"

    def test_unsorted_and_duplicates(self):
        assert _faixas_para_string([7, 3, 3, 1, 2]) == "1-3,7"

    def test_empty(self):
        assert _faixas_para_string([]) == ""


class _FakeYDL:
    """Fake YoutubeDL que captura as opts e simula um vídeo baixado."""

    captured: dict = {}
    captured_all: list = []

    def __init__(self, opts: dict):
        self.opts = opts
        _FakeYDL.captured = opts
        _FakeYDL.captured_all.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url: str, download: bool = True):
        return {"title": "teste", "id": "abc", "entries": None}


class TestRunDownloadAudioOgg:
    """OGG deve mapear para o codec 'vorbis' do yt-dlp (senão: KeyError)."""

    def _run(self, tmp_path: Path, output_format: str) -> dict:
        _FakeYDL.captured = {}
        fake_module = mock.Mock(YoutubeDL=_FakeYDL)
        with mock.patch("converter.youtube._get_ytdlp", return_value=fake_module), \
                mock.patch("converter.ffmpeg_core.find_ffmpeg",
                           return_value="ffmpeg"):
            job = YouTubeJob(
                url="https://youtu.be/abc", output_dir=str(tmp_path),
                quality=VIDEO_QUALITIES["Somente áudio"],
                output_format=output_format)
            run_download(job, callback=None)
        return _FakeYDL.captured

    def test_ogg_maps_to_vorbis(self, tmp_path):
        opts = self._run(tmp_path, "ogg")
        pp = opts["postprocessors"][0]
        assert pp["preferredcodec"] == "vorbis"

    def test_mp3_keeps_itself(self, tmp_path):
        opts = self._run(tmp_path, "mp3")
        pp = opts["postprocessors"][0]
        assert pp["preferredcodec"] == "mp3"
        assert pp["preferredquality"] == "192"

    def test_audio_only_uses_bestaudio(self, tmp_path):
        opts = self._run(tmp_path, "ogg")
        assert opts["format"] == "bestaudio/best"


class TestCancelamentoHook:
    """Cancelar deve abortar o download de verdade (DownloadCancelled)."""

    def test_hook_raises_when_cancelled(self):
        job = YouTubeJob(url="x", output_dir=".", quality="best")
        job.cancel()
        hook = _make_hook(job, None)
        with pytest.raises(DownloadCancelled):
            hook({"status": "downloading"})

    def test_hook_silent_when_active(self):
        job = YouTubeJob(url="x", output_dir=".", quality="best")
        calls = []
        hook = _make_hook(job, lambda p, s, e, st: calls.append(st))
        hook({"status": "finished"})
        assert calls == ["Processando áudio..."]

    def test_run_download_marks_cancelled_on_abort(self, tmp_path):
        class _FakeYDLCancelled(_FakeYDL):
            def extract_info(self, url, download=True):
                raise DownloadCancelled()

        fake_module = mock.Mock(YoutubeDL=_FakeYDLCancelled)
        with mock.patch("converter.youtube._get_ytdlp", return_value=fake_module), \
                mock.patch("converter.ffmpeg_core.find_ffmpeg",
                           return_value="ffmpeg"):
            job = YouTubeJob(
                url="https://youtu.be/abc", output_dir=str(tmp_path),
                quality="best", output_format="mp4")
            job.cancel()
            run_download(job, callback=None)
        assert job.status == "cancelled"


class TestRunDownloadLegendas:
    """Legendas rodam num passo separado e best-effort (não matam o download)."""

    def _capture(self, tmp_path, legendas: bool) -> dict:
        _FakeYDL.captured = {}
        _FakeYDL.captured_all = []
        fake_module = mock.Mock(YoutubeDL=_FakeYDL)
        with mock.patch("converter.youtube._get_ytdlp", return_value=fake_module), \
                mock.patch("converter.ffmpeg_core.find_ffmpeg",
                           return_value="ffmpeg"):
            job = YouTubeJob(
                url="https://youtu.be/abc", output_dir=str(tmp_path),
                quality="best", output_format="mp4", legendas=legendas)
            run_download(job, callback=None)
        return _FakeYDL.captured, job

    def test_legendas_em_passo_separado(self, tmp_path):
        opts, job = self._capture(tmp_path, legendas=True)
        assert job.status == "done"
        # 1ª instância = download principal, SEM legendas
        principal = _FakeYDL.captured_all[0]
        assert "writesubtitles" not in principal
        assert "writeautomaticsub" not in principal
        # 2ª instância = passo de legendas, com skip_download
        subs = _FakeYDL.captured_all[1]
        assert subs["skip_download"] is True
        assert subs["writesubtitles"] is True
        assert subs["writeautomaticsub"] is True
        assert subs["subtitlesformat"] == "srt"
        assert subs["subtitleslangs"] == ["pt.*", "en.*"]
        assert job.aviso == ""

    def test_legendas_desligadas_sem_passo_extra(self, tmp_path):
        opts, job = self._capture(tmp_path, legendas=False)
        assert job.status == "done"
        assert len(_FakeYDL.captured_all) == 1
        assert "writeautomaticsub" not in opts

    def test_falha_nas_legendas_nao_derruba_download(self, tmp_path):
        from yt_dlp.utils import DownloadError

        class _FakeYDLSubFails:
            def __init__(self, opts):
                self.is_sub = "writeautomaticsub" in opts

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def extract_info(self, url, download=True):
                if self.is_sub:
                    raise DownloadError(
                        "Unable to download video subtitles for 'en': "
                        "HTTP Error 429: Too Many Requests")
                return {"title": "teste", "id": "abc", "entries": None}

        fake_module = mock.Mock(YoutubeDL=_FakeYDLSubFails)
        with mock.patch("converter.youtube._get_ytdlp", return_value=fake_module), \
                mock.patch("converter.ffmpeg_core.find_ffmpeg",
                           return_value="ffmpeg"):
            job = YouTubeJob(
                url="https://youtu.be/abc", output_dir=str(tmp_path),
                quality="best", output_format="mp4", legendas=True)
            run_download(job, callback=None)
        assert job.status == "done"
        assert "429" in job.aviso
        assert not job.error


class TestConversaoPulaLegendas:
    """O loop de conversão não deve converter arquivos .srt/.vtt."""

    def test_srt_nao_vai_para_convert_to(self, tmp_path):
        (tmp_path / "Teste Video [abc].webm").write_bytes(b"\x00" * 100)
        (tmp_path / "Teste Video [abc].pt.srt").write_bytes(b"1\n00:00:00,0 --> 00:00:01,0\nola\n")

        class _FakeYDLSub(_FakeYDL):
            def extract_info(self, url, download=True):
                return {"title": "Teste Video", "id": "abc", "entries": None}

        fake_module = mock.Mock(YoutubeDL=_FakeYDLSub)
        chamadas = []

        def _fake_convert(target, out_fmt, ffmpeg, manter_original=False,
                          callback=None):
            chamadas.append(target)
            return target.replace(".webm", ".mp4")

        with mock.patch("converter.youtube._get_ytdlp", return_value=fake_module), \
                mock.patch("converter.ffmpeg_core.find_ffmpeg",
                           return_value="ffmpeg"), \
                mock.patch("converter.youtube._convert_to",
                           side_effect=_fake_convert):
            job = YouTubeJob(
                url="https://youtu.be/abc", output_dir=str(tmp_path),
                quality="best", output_format="mp4")
            run_download(job, callback=None)

        assert len(chamadas) == 1, chamadas
        assert chamadas[0].endswith(".webm"), chamadas
        assert job.downloaded_files and any(
            f.endswith(".srt") for f in job.downloaded_files), \
            "legenda deveria permanecer na lista de arquivos"


class TestConversaoReportaProgresso:
    """O progresso da conversão deve chegar ao callback do download."""

    def test_convert_to_encaminha_com_status_convertendo(self, tmp_path):
        from converter.youtube import _convert_to

        src = tmp_path / "video.webm"
        src.write_bytes(b"\x00" * 100)

        eventos = []
        convert_callback = None

        def _fake_run(job, ffmpeg=None, callback=None):
            nonlocal convert_callback
            convert_callback = callback
            job.status = "done"
            return job

        with mock.patch("converter.ffmpeg_core.run_conversion",
                        side_effect=_fake_run):
            result = _convert_to(
                str(src), "mp4", "ffmpeg",
                callback=lambda p, s, e, st: eventos.append((p, s, e, st)))

        assert result.endswith(".mp4")
        assert convert_callback is not None
        # Simula o progresso do ffmpeg -> deve vir com status "Convertendo..."
        convert_callback(42.0, "5.1 MB/s", "30s")
        assert eventos == [(42.0, "5.1 MB/s", "30s", "Convertendo...")], eventos

    def test_run_download_repassa_callback_a_conversao(self, tmp_path):
        (tmp_path / "Teste Video [abc].webm").write_bytes(b"\x00" * 100)

        class _FakeYDLConv(_FakeYDL):
            def extract_info(self, url, download=True):
                return {"title": "Teste Video", "id": "abc", "entries": None}

        fake_module = mock.Mock(YoutubeDL=_FakeYDLConv)
        cb_recebido = []

        def _fake_convert(target, out_fmt, ffmpeg, manter_original=False,
                          callback=None):
            cb_recebido.append(callback)
            return target.replace(".webm", ".mp4")

        with mock.patch("converter.youtube._get_ytdlp", return_value=fake_module), \
                mock.patch("converter.ffmpeg_core.find_ffmpeg",
                           return_value="ffmpeg"), \
                mock.patch("converter.youtube._convert_to",
                           side_effect=_fake_convert):
            job = YouTubeJob(
                url="https://youtu.be/abc", output_dir=str(tmp_path),
                quality="best", output_format="mp4")
            run_download(job, callback=lambda *a: None)

        assert len(cb_recebido) == 1 and cb_recebido[0] is not None


class TestDownloadDireto:
    """Baixar direto (formato nativo) monta o formato certo e não converte."""

    def _capture(self, tmp_path, job_kwargs, cria_webm=True):
        _FakeYDL.captured = {}
        if cria_webm:
            (tmp_path / "teste [abc].webm").write_bytes(b"\x00" * 100)

        class _FakeYDLDir(_FakeYDL):
            def extract_info(self, url, download=True):
                return {"title": "teste", "id": "abc", "entries": None}

        fake_module = mock.Mock(YoutubeDL=_FakeYDLDir)
        chamadas = []

        def _fake_convert(target, out_fmt, ffmpeg, manter_original=False,
                          callback=None):
            chamadas.append(target)
            return target

        base = {
            "quality": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "output_format": "mp4",
        }
        base.update(job_kwargs)

        with mock.patch("converter.youtube._get_ytdlp", return_value=fake_module), \
                mock.patch("converter.ffmpeg_core.find_ffmpeg",
                           return_value="ffmpeg"), \
                mock.patch("converter.youtube._convert_to",
                           side_effect=_fake_convert):
            job = YouTubeJob(
                url="https://youtu.be/abc", output_dir=str(tmp_path), **base)
            run_download(job, callback=None)
        return _FakeYDL.captured, job, chamadas

    def test_direto_mp4_monta_formato_com_ext_e_merge(self, tmp_path):
        opts, job, chamadas = self._capture(tmp_path, {"direto": True})
        assert job.status == "done"
        assert "bestvideo[height<=1080][ext=mp4]" in opts["format"]
        assert opts["merge_output_format"] == "mp4"
        assert not chamadas, "direto não deve converter"

    def test_direto_webm_sem_altura(self, tmp_path):
        opts, job, chamadas = self._capture(
            tmp_path, {"direto": True, "quality": "best",
                       "output_format": "webm"})
        assert "[ext=webm]" in opts["format"]
        assert opts["merge_output_format"] == "webm"
        assert not chamadas

    def test_sem_direto_usa_preset_e_converte(self, tmp_path):
        opts, job, chamadas = self._capture(tmp_path, {"direto": False})
        assert "merge_output_format" not in opts
        assert chamadas, "sem direto deve converter"
