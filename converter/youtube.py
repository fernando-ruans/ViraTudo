"""Download do YouTube via yt-dlp + conversão local com FFmpeg.

Baixa o melhor stream disponível e, quando o formato pedido não é o nativo
do stream, converte na hora com o FFmpeg (offline). Suporta playlist,
máquina de qualidade e extração de áudio.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# yt-dlp é importado sob demanda (lazy) para que a GUI abra mesmo se faltar
_ytdlp = None
_ytdlp_error: Optional[str] = None


def _get_ytdlp():
    global _ytdlp, _ytdlp_error
    if _ytdlp is None and _ytdlp_error is None:
        try:
            import yt_dlp  # type: ignore
            _ytdlp = yt_dlp
        except ImportError as e:
            _ytdlp_error = (
                "yt-dlp não instalado. Rode: pip install yt-dlp"
            )
    return _ytdlp


# Callback de progresso do download: (percentual, velocidade, eta, status_text)
ProgressCallback = Callable[[float, Optional[str], Optional[str], str], None]

# Qualidades disponíveis para download de vídeo
VIDEO_QUALITIES = {
    "Melhor disponível": "best",
    "2160p (4K)": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440p (2K)": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080p (Full HD)": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p (HD)": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p (SD)": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "Somente áudio": "bestaudio/best",
}


@dataclass
class YouTubeJob:
    """Um download: um único vídeo ou uma playlist inteira."""

    url: str
    output_dir: str
    quality: str = "best"           # formato de qualidade (chave do VIDEO_QUALITIES)
    output_format: str = "mp4"      # extensão desejada (mp4, mkv, webm, mp3, flac, wav...)
    is_playlist: bool = False
    audio_only: bool = False
    status: str = "pending"         # pending | running | done | cancelled | error
    progress: float = 0.0
    error: str = ""
    # ---- Opções (Fase 3) ----
    faixas: Optional[list[int]] = None   # seleção de faixas da playlist (1-indexado)
    manter_original: bool = False        # não apagar o arquivo intermediário
    legendas: bool = False               # baixar .srt junto
    downloaded_files: list[str] = field(default_factory=list)
    _dl: Optional[object] = field(default=None, repr=False)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def cancel(self) -> None:
        self._cancel.set()


def is_youtube_url(url: str) -> bool:
    """Detecta URLs do YouTube (vídeo, playlist, short)."""
    url = url.strip()
    if not url:
        return False
    return bool(re.search(
        r"(youtube\.com/(watch\?|shorts/|playlist\?|live/)|youtu\.be/)", url))


def _faixas_para_string(faixas: list[int]) -> str:
    """Converte [1,3,5,6,7] -> '1,3,5-7' (sintaxe do yt-dlp)."""
    if not faixas:
        return ""
    ordenadas = sorted(set(faixas))
    partes = []
    inicio = prev = ordenadas[0]
    for n in ordenadas[1:]:
        if n == prev + 1:
            prev = n
            continue
        partes.append(str(inicio) if inicio == prev else f"{inicio}-{prev}")
        inicio = prev = n
    partes.append(str(inicio) if inicio == prev else f"{inicio}-{prev}")
    return ",".join(partes)


def _safe_filename(name: str) -> str:
    """Sanitiza nome de arquivo para Windows/Linux."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip()
    return name[:150] or "video"


def preview_video(url: str) -> dict:
    """Busca informações do vídeo sem baixar (título, duração, resoluções).

    Usado pela GUI para mostrar a prévia ao colar a URL. Lança exceção
    com mensagem amigável se o vídeo for inválido.
    """
    ydl = _get_ytdlp()
    if ydl is None:
        raise RuntimeError(_ytdlp_error or "yt-dlp indisponível.")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {"youtube": ["player_client=default,android"]},
    }
    with ydl.YoutubeDL(opts) as ydl_inst:
        info = ydl_inst.extract_info(url, download=False)
        if not info:
            raise RuntimeError("Não foi possível obter informações do vídeo.")

        # Playlist: retorna o primeiro vídeo como referência + contagem
        if info.get("_type") == "playlist" or info.get("entries"):
            entries = info.get("entries") or []
            first = entries[0] if entries else {}
            return {
                "titulo": info.get("title") or "Playlist",
                "uploader": info.get("uploader") or "",
                "duracao": first.get("duration") if first else None,
                "is_playlist": True,
                "total_faixas": len(entries),
                "resolucoes": _formatos_do(info, first),
                "thumbnail": (first or {}).get("thumbnail") or "",
            }

        return {
            "titulo": info.get("title") or "Vídeo",
            "uploader": info.get("uploader") or "",
            "duracao": info.get("duration"),
            "is_playlist": False,
            "total_faixas": 1,
            "resolucoes": _formatos_do(info, None),
            "thumbnail": info.get("thumbnail") or "",
        }


def _formatos_do(info: dict, first: Optional[dict]) -> list[str]:
    """Lista de resoluções disponíveis a partir dos formatos do vídeo."""
    alvo = info if first is None else first
    if not alvo:
        return []
    resolucoes = set()
    for f in alvo.get("formats") or []:
        h = f.get("height")
        if h and f.get("vcodec") and f.get("vcodec") != "none":
            resolucoes.add(h)
    if not resolucoes:
        return []
    ordem = sorted(resolucoes, reverse=True)
    return [f"{h}p" for h in ordem[:6]]


def listar_playlist(url: str) -> list[dict]:
    """Lista as faixas de uma playlist: [{index, titulo, duracao}]."""
    ydl = _get_ytdlp()
    if ydl is None:
        raise RuntimeError(_ytdlp_error or "yt-dlp indisponível.")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",  # rápido: sem baixar metadados completos
        "extractor_args": {"youtube": ["player_client=default,android"]},
    }
    with ydl.YoutubeDL(opts) as ydl_inst:
        info = ydl_inst.extract_info(url, download=False)
        entries = info.get("entries") or []
        faixas = []
        for i, e in enumerate(entries, start=1):
            if not e:
                continue
            faixas.append({
                "index": i,
                "titulo": e.get("title") or f"Faixa {i}",
                "duracao": e.get("duration"),
            })
        return faixas


def _convert_to(target: str, out_fmt: str, ffmpeg: str) -> Optional[str]:
    """Converte um arquivo baixado para o formato pedido (offline)."""
    from .ffmpeg_core import ConversionJob, run_conversion

    src = Path(target)
    dst = src.with_suffix(f".{out_fmt}")
    if src.suffix.lower() == f".{out_fmt}":
        return str(src)
    job = ConversionJob(input_path=str(src), output_path=str(dst),
                        format_key=out_fmt, title=src.name)
    run_conversion(job, ffmpeg=ffmpeg)
    if job.status == "done":
        try:
            os.remove(str(src))  # remove o intermediário
        except OSError:
            pass
        return str(dst)
    return None


def coerce_job_format(job: YouTubeJob) -> None:
    """Garante coerência entre qualidade e formato de saída.

    - Qualidade 'Somente áudio' (bestaudio) + formato de vídeo -> m4a
    - Marca audio_only quando o formato de saída é de áudio
    """
    from .presets import AUDIO_FORMATS
    if "bestaudio" in job.quality and job.output_format not in AUDIO_FORMATS:
        job.output_format = "m4a"
    job.audio_only = job.output_format in AUDIO_FORMATS


def run_download(
    job: YouTubeJob,
    callback: Optional[ProgressCallback] = None,
) -> YouTubeJob:
    """Executa o download (síncrono; chamar de thread)."""
    ydl = _get_ytdlp()
    if ydl is None:
        job.status = "error"
        job.error = _ytdlp_error or "yt-dlp indisponível."
        return job

    from .ffmpeg_core import find_ffmpeg
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        job.status = "error"
        job.error = "FFmpeg não encontrado — necessário para conversão. Instale-o."
        return job

    Path(job.output_dir).mkdir(parents=True, exist_ok=True)

    # Coerção: qualidade "Somente áudio" exige formato de áudio. Se o usuário
    # pediu "somente áudio" mas deixou o formato em mp4/mkv..., corrige para m4a.
    coerce_job_format(job)

    format_sel = job.quality if not job.audio_only else "bestaudio/best"
    if job.audio_only:
        ext = "mp3" if job.output_format == "mp3" else "best"
        postproc = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": job.output_format,
            "preferredquality": "192" if job.output_format == "mp3" else "0",
        }]
    else:
        ext = job.output_format
        postproc = []

    opts = {
        "format": format_sel,
        "outtmpl": os.path.join(job.output_dir, "%(title).120s [%(id)s].%(ext)s"),
        "noplaylist": not job.is_playlist,
        "ffmpeg_location": str(Path(ffmpeg).parent),
        "postprocessors": postproc,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_make_hook(job, callback)],
        "noprogress": True,
        "retries": 3,
        # Fallback automático de clientes: o client "android" passa em
        # verificações anti-bot onde o padrão (web) falha.
        "extractor_args": {"youtube": ["player_client=default,android"]},
    }

    # Fase 3: seleção de faixas da playlist (ex.: "1,3,5-8")
    if job.faixas:
        opts["playlist_items"] = _faixas_para_string(job.faixas)

    # Fase 3: manter o arquivo original após a conversão de áudio
    if job.manter_original:
        opts["keepvideo"] = True

    # Fase 3: legendas
    if job.legendas:
        opts["writesubtitles"] = True
        opts["subtitleslangs"] = ["pt", "pt-BR", "en"]
        opts["subtitlesformat"] = "srt"
        opts["skip_download"] = False

    job.status = "running"
    try:
        with ydl.YoutubeDL(opts) as ydl_inst:
            job._dl = ydl_inst
            info = ydl_inst.extract_info(job.url, download=True)
            # Lista os arquivos efetivamente produzidos
            if info:
                entries = info.get("entries") or [info]
                for e in entries:
                    if not e:
                        continue
                    fname = _safe_filename(e.get("title", "video"))
                    fid = e.get("id", "")
                    for cand in Path(job.output_dir).iterdir():
                        if cand.stem.startswith(fname[:60]) and fid and fid in cand.name:
                            job.downloaded_files.append(str(cand))
            if not job.downloaded_files:
                # fallback: pega os arquivos mais recentes da pasta
                files = sorted(
                    Path(job.output_dir).iterdir(),
                    key=lambda p: p.stat().st_mtime, reverse=True,
                )
                job.downloaded_files = [str(f) for f in files[:10] if f.is_file()]

            # Vídeo: converte para o formato pedido quando o baixado não é o
            # nativo (ex.: pediu mkv/gif/webm mas o YouTube entregou mp4).
            if not job.audio_only and job.downloaded_files:
                convertidos = []
                for f in job.downloaded_files:
                    if Path(f).suffix.lower() == f".{job.output_format}":
                        convertidos.append(f)
                        continue
                    conv = _convert_to(f, job.output_format, ffmpeg)
                    if conv:
                        convertidos.append(conv)
                    else:
                        convertidos.append(f)  # mantém o original se falhar
                job.downloaded_files = convertidos
    except Exception as e:  # noqa: BLE001 — yt-dlp lança de tudo
        if job._cancel.is_set():
            job.status = "cancelled"
            return job
        # Se o YouTube pediu verificação anti-bot mesmo com o fallback
        # android, tenta com cookies do navegador logado do usuário.
        msg = str(e)
        if "Sign in to confirm" in msg or "bot" in msg.lower():
            retry = _retry_with_browser_cookies(job, opts, ydl)
            if retry:
                job.status = "done"
                job.progress = 100.0
                if callback:
                    callback(100.0, None, None, "Concluído")
                return job
            # _retry_with_browser_cookies preencheu job.error com uma dica
            # acionável; preserva-a em vez da mensagem genérica.
            if not job.error:
                job.error = _humanize_ytdlp_error(msg)
            job.status = "error"
            return job
        job.status = "error"
        job.error = _humanize_ytdlp_error(msg)
        return job

    if job._cancel.is_set():
        job.status = "cancelled"
        _log_download(job)
        return job

    job.status = "done"
    job.progress = 100.0
    if callback:
        callback(100.0, None, None, "Concluído")
    _log_download(job)
    return job


def _log_download(job: YouTubeJob) -> None:
    """Registra o resultado do download no log (se configurado)."""
    try:
        from .logging_setup import log_download
        log_download(job.url, job.output_format, job.status, job.error)
    except Exception:
        pass  # logging nunca deve quebrar o download


def _make_hook(job: YouTubeJob, callback: Optional[ProgressCallback]):
    """Progress hook do yt-dlp -> nosso callback unificado."""
    def hook(d: dict) -> None:
        if job._cancel.is_set():
            # yt-dlp não tem cancelamento limpo; interrompemos no extract_info
            return
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = (done / total * 100) if total else 0.0
            job.progress = pct
            speed = d.get("speed")
            speed_s = f"{speed / 1024 / 1024:.1f} MB/s" if speed else None
            eta = d.get("eta")
            eta_s = f"{eta}s" if eta is not None else None
            if callback:
                callback(pct, speed_s, eta_s, "Baixando...")
        elif status == "finished":
            if callback:
                callback(100.0, None, None, "Processando áudio...")
        elif status == "error":
            job.error = str(d.get("msg", "erro no download"))
    return hook


def _retry_with_browser_cookies(job: YouTubeJob, opts: dict, ydl) -> bool:
    """Último recurso: tenta o download usando cookies do navegador do usuário.

    Navegadores testados em ordem: chrome, edge, firefox, brave, opera.
    Retorna True se algum navegador conseguiu baixar. Em caso de falha,
    preenche job.error com o motivo mais útil encontrado.
    """
    browsers = ["chrome", "edge", "firefox", "brave", "opera"]
    last_err = ""
    for browser in browsers:
        if job._cancel.is_set():
            return False
        try:
            retry_opts = dict(opts)
            retry_opts["cookiesfrombrowser"] = (browser, None, None, None)
            with ydl.YoutubeDL(retry_opts) as ydl_inst:
                job._dl = ydl_inst
                ydl_inst.extract_info(job.url, download=True)
            # Se chegou aqui, baixou — registra os arquivos
            files = sorted(
                Path(job.output_dir).iterdir(),
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            job.downloaded_files = [str(f) for f in files[:10] if f.is_file()]
            if job.downloaded_files:
                return True
        except Exception as e:
            last_err = f"{browser}: {str(e)[:150]}"
            continue  # tenta próximo navegador

    if last_err:
        job.error = _cookies_failure_hint(last_err)
    return False


def _cookies_failure_hint(last_err: str) -> str:
    """Transforma o erro do último navegador em dica acionável."""
    lower = last_err.lower()
    if "could not copy" in lower or "database" in lower and "lock" in lower:
        return (
            "O YouTube pediu verificação anti-bot. Tentei usar os cookies do "
            "seu navegador, mas ele está aberto/bloqueado. Feche o Chrome/Edge "
            "e tente de novo — ou faça login no YouTube no navegador."
        )
    if "dapi" in lower or "decrypt" in lower:
        return (
            "O YouTube pediu verificação anti-bot e os cookies do navegador "
            "não puderam ser descriptografados (limitação do Windows). "
            "Tente de novo mais tarde ou use outro vídeo."
        )
    return (
        "O YouTube pediu verificação anti-bot e o download automático com "
        "cookies do navegador falhou (último erro: " + last_err + "). "
        "Tente de novo em alguns minutos ou use outro vídeo."
    )


def _humanize_ytdlp_error(err: str) -> str:
    if "Unsupported URL" in err:
        return "URL não suportada — só funciona com links do YouTube."
    if "Video unavailable" in err or "is unavailable" in err:
        return "Vídeo indisponível (privado, removido ou bloqueado no seu país)."
    if "playlist" in err.lower() and "not found" in err.lower():
        return "Playlist não encontrada ou vazia."
    if "Sign in to confirm" in err or "bot" in err.lower():
        return ("YouTube pediu verificação (proteção anti-bot). "
                "Tente de novo mais tarde ou use outro vídeo.")
    if "network" in err.lower() or "timed out" in err.lower():
        return "Falha de rede ao acessar o YouTube. Verifique sua internet."
    return f"Erro no download: {err[:300]}"


# ---------------------------------------------------------------- CLI (teste)
def main() -> None:
    """CLI: python -m converter.youtube <url> [formato] [pasta]"""
    import sys

    if len(sys.argv) < 2:
        print("Uso: python -m converter.youtube <url> [mp4|mp3|...] [pasta]")
        sys.exit(1)
    url = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else "mp4"
    outdir = sys.argv[3] if len(sys.argv) > 3 else "downloads"

    job = YouTubeJob(url=url, output_dir=outdir, output_format=fmt, quality="best")

    def cb(pct, speed, eta, status):
        print(f"\r{status} {pct:5.1f}%  {speed or ''} {eta or ''}   ", end="", flush=True)

    run_download(job, cb)
    print(f"\n[{job.status}] {job.error or 'OK'}")
    for f in job.downloaded_files:
        print("  ->", f)


if __name__ == "__main__":
    main()
