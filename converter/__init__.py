"""Converter universal — conversor de mídia nativo e offline + YouTube."""

from . import presets
from .ffmpeg_core import (
    ConversionJob, find_ffmpeg, run_conversion, validar_conversao,
)
from .presets import classificar_entrada
from .youtube import (
    YouTubeJob,
    _faixas_para_string,
    is_youtube_url,
    listar_playlist,
    preview_video,
    run_download,
    VIDEO_QUALITIES,
)

__all__ = [
    "presets", "ConversionJob", "find_ffmpeg", "run_conversion",
    "validar_conversao", "classificar_entrada",
    "YouTubeJob", "is_youtube_url", "run_download", "VIDEO_QUALITIES",
    "preview_video", "listar_playlist", "_faixas_para_string",
]
__version__ = "1.2.0"
