"""Concatenação de múltiplos arquivos de mídia (junção).

Usa o concat demuxer do FFmpeg: tenta `-c copy` (rápido, sem perda) e
cai para re-codificação se os codecs forem incompatíveis.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .ffmpeg_core import find_ffmpeg

ProgressCallback = Callable[[float, str], None]


@dataclass
class ConcatJob:
    """Trabalho de concatenação."""

    inputs: list[str]
    output_path: str
    format_key: str = "mp4"
    status: str = "pending"
    error: str = ""
    progress: float = 0.0
    _cancel: object = field(default=None, repr=False)


def _write_list_file(inputs: list[str], path: Path) -> None:
    """Escreve o arquivo de lista do concat demuxer."""
    lines = []
    for p in inputs:
        # Escapa aspas simples e barras (sintaxe do demuxer)
        safe = str(p).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{safe}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _probe_codecs(path: str) -> tuple[Optional[str], Optional[str]]:
    """Retorna (codec_video, codec_audio) de um arquivo."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None, None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_type,codec_name", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=15).stdout
        v = a = None
        for line in out.strip().splitlines():
            parts = line.split(",")
            # ffprobe ordena as chaves: codec_name,codec_type
            if len(parts) == 2:
                codec_name, codec_type = parts[0], parts[1]
                if codec_type == "video" and not v:
                    v = codec_name
                elif codec_type == "audio" and not a:
                    a = codec_name
        return v, a
    except Exception:
        return None, None


def concat_files(
    inputs: list[str],
    output_path: str,
    format_key: str = "mp4",
    callback: Optional[ProgressCallback] = None,
    ffmpeg: Optional[str] = None,
) -> ConcatJob:
    """Junta arquivos de entrada num único arquivo de saída."""
    job = ConcatJob(inputs=inputs, output_path=output_path,
                    format_key=format_key)
    if len(inputs) < 2:
        job.status = "error"
        job.error = "Concatenação precisa de pelo menos 2 arquivos."
        return job

    ffmpeg = ffmpeg or find_ffmpeg()
    if not ffmpeg:
        job.status = "error"
        job.error = "FFmpeg não encontrado."
        return job

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Verifica se todos têm os mesmos codecs (para -c copy)
    codecs = [_probe_codecs(p) for p in inputs]
    same_codecs = len(set(codecs)) == 1 and all(
        v or a for v, a in codecs)

    with tempfile.TemporaryDirectory(prefix="viratudo_concat_") as tmp:
        lista = Path(tmp) / "lista.txt"
        _write_list_file(inputs, lista)

        if same_codecs:
            cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                   "-f", "concat", "-safe", "0", "-i", str(lista),
                   "-c", "copy", output_path]
        else:
            cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                   "-f", "concat", "-safe", "0", "-i", str(lista),
                   "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                   "-c:a", "aac", "-b:a", "192k",
                   "-movflags", "+faststart", output_path]

        job.status = "running"
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace")
        if callback:
            callback(50.0, "Concatenando...")
        _stdout, stderr = proc.communicate(timeout=600)
        if callback:
            callback(100.0, "Finalizando...")

    if proc.returncode != 0:
        job.status = "error"
        job.error = f"Erro na concatenação: {stderr.strip()[-200:]}"
        try:
            os.remove(output_path)
        except OSError:
            pass
        return job

    job.status = "done"
    return job


# ---------------------------------------------------------------- CLI (teste)
def main() -> None:
    """CLI: python -m converter.concat out.mp4 in1.mp4 in2.mp4 ..."""
    import sys

    if len(sys.argv) < 4:
        print("Uso: python -m converter.concat <saida> <entrada1> <entrada2> ...")
        sys.exit(1)
    out = sys.argv[1]
    inputs = sys.argv[2:]
    job = concat_files(inputs, out)
    print(f"[{job.status}] {job.error or out}")


if __name__ == "__main__":
    main()
