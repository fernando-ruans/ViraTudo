"""Fixtures compartilhadas dos testes do ViraTudo."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def ffmpeg() -> str:
    """Localiza o ffmpeg; pula os testes se não existir."""
    exe = shutil.which("ffmpeg")
    if not exe:
        pytest.skip("FFmpeg não encontrado no PATH")
    return exe


@pytest.fixture()
def sample_video(tmp_path: Path, ffmpeg: str) -> Path:
    """Gera um MP4 de teste (2s, com áudio) e retorna o caminho."""
    src = tmp_path / "sample.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)],
        check=True, capture_output=True)
    assert src.exists() and src.stat().st_size > 10_000
    return src


@pytest.fixture()
def sample_image(tmp_path: Path, ffmpeg: str) -> Path:
    """Gera um PNG de teste (100x75)."""
    src = tmp_path / "img.png"
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc2=size=100x75:duration=0.1",
         "-frames:v", "1", str(src)],
        check=True, capture_output=True)
    assert src.exists()
    return src
