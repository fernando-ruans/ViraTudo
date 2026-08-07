"""Helpers de teste: consultas ffprobe."""

from __future__ import annotations

import subprocess
from pathlib import Path


def probe(path: Path, stream: str = "a:0", field: str = "codec_name") -> str:
    """Consulta uma propriedade de stream com ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", f"stream={field}", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return out.stdout.strip()


def probe_format(path: Path, field: str) -> str:
    """Consulta uma propriedade do container (formato) com ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", f"format={field}",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return out.stdout.strip()
