"""Converter universal — conversor de mídia nativo e offline + YouTube."""

from . import presets
from .ffmpeg_core import ConversionJob, find_ffmpeg, run_conversion
from .youtube import YouTubeJob, is_youtube_url, run_download, VIDEO_QUALITIES

__all__ = [
    "presets", "ConversionJob", "find_ffmpeg", "run_conversion",
    "YouTubeJob", "is_youtube_url", "run_download", "VIDEO_QUALITIES",
]
__version__ = "1.0.0"
