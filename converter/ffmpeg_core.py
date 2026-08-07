"""Wrapper do FFmpeg: conversão local/offline com progresso em tempo real.

Estratégia: roda `ffmpeg -progress pipe:1` e parseia as linhas `out_time_ms`
para calcular a porcentagem. Suporta cancelamento e retorna erros legíveis.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .presets import OUTPUT_FORMATS, classificar_entrada

# Callback de progresso: recebe (percentual 0-100, velocidade, tempo restante estimado)
ProgressCallback = Callable[[float, Optional[str], Optional[str]], None]


@dataclass
class ConversionJob:
    """Um trabalho de conversão único, com estado e cancelamento."""

    input_path: str
    output_path: str
    format_key: str
    title: str = ""
    status: str = "pending"  # pending | running | done | cancelled | error
    progress: float = 0.0
    error: str = ""
    # ---- Opções avançadas (Fase 1) ----
    start_time: Optional[float] = None   # corte: início em segundos
    end_time: Optional[float] = None     # corte: fim em segundos
    quality: Optional[str] = None        # perfil de qualidade (ver presets)
    scale: Optional[str] = None          # resolução, ex. "1280:720"
    gif_fps: int = 15                    # GIF: quadros por segundo
    gif_width: int = 480                 # GIF: largura (altura proporcional)
    duration: Optional[float] = None     # imagem -> vídeo: duração em segundos
    _proc: Optional[subprocess.Popen] = field(default=None, repr=False)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def cancel(self) -> None:
        self._cancel.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass


def find_ffmpeg() -> Optional[str]:
    """Localiza o binário ffmpeg (PATH ou caminhos comuns)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


# Cache dos encoders de hardware detectados
_HW_ENCODERS: Optional[set[str]] = None


def _dispositivo_hw_ok(encoder: str) -> bool:
    """Verifica se o dispositivo de hardware do encoder realmente existe.

    O `ffmpeg -encoders` lista encoders compilados, mas isso NAO significa
    que o hardware esta presente (ex.: WSL sem GPU lista h264_vaapi/nvenc
    mas o encode falha em runtime). Checamos os dispositivos:
    - vaapi  -> /dev/dri/renderD* (Linux)
    - nvenc  -> driver NVIDIA (nvidia-smi ou /dev/nvidia*)
    - qsv    -> /dev/dri/renderD* (iGPU Intel expoe VAAPI; QSV exige driver)
    - amf    -> Windows com GPU AMD (sem checagem confiavel, o smoke test valida)
    - videotoolbox -> macOS
    """
    import sys
    if sys.platform == "darwin":
        return True  # videotoolbox e nativo no macOS
    if "vaapi" in encoder or "qsv" in encoder:
        return any(os.path.exists(p) for p in (
            "/dev/dri/renderD128", "/dev/dri/renderD129", "/dev/dri/renderD130"))
    if "nvenc" in encoder:
        import shutil as _sh
        if _sh.which("nvidia-smi"):
            return True
        return any(os.path.exists(p) for p in ("/dev/nvidia0", "/dev/nvidiactl"))
    return True  # amf/videotoolbox: deixa o smoke test decidir


def _smoke_test_encoder(encoder: str, ffmpeg: str) -> bool:
    """Encode de 1 frame para confirmar que o encoder HW funciona de verdade.

    Encoders listados mas sem hardware falham com 'Unknown error occurred'
    ou 'Nothing was written into output file' — o smoke test pega isso na
    primeira chamada e o resultado fica em cache.
    """
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "smoke.mp4")
            r = subprocess.run(
                [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
                 "-frames:v", "1", "-c:v", encoder, out],
                capture_output=True, text=True, timeout=20)
            return r.returncode == 0 and os.path.exists(out) \
                and os.path.getsize(out) > 0
    except Exception:
        return False


def encoders_disponiveis(ffmpeg: Optional[str] = None) -> set[str]:
    """Detecta encoders de aceleracao por hardware realmente utilizaveis.

    Retorna um set com nomes como 'h264_nvenc', 'hevc_nvenc', 'h264_qsv',
    'h264_vaapi', 'h264_videotoolbox'. Faz cache do resultado. Cada encoder
    e validado com um encode de 1 frame (smoke test) — encoders listados
    mas sem hardware presente (ex.: WSL sem GPU) sao descartados.
    """
    global _HW_ENCODERS
    if _HW_ENCODERS is not None:
        return _HW_ENCODERS

    ffmpeg = ffmpeg or find_ffmpeg()
    _HW_ENCODERS = set()
    if not ffmpeg:
        return _HW_ENCODERS

    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        alvos = ("nvenc", "qsv", "vaapi", "videotoolbox", "amf")
        for line in out.splitlines():
            for alvo in alvos:
                if alvo in line and "V....." in line:
                    partes = line.split()
                    if partes:
                        nome = partes[1]
                        if nome.startswith(("h264_", "hevc_", "av1_")):
                            if _dispositivo_hw_ok(nome) and \
                                    _smoke_test_encoder(nome, ffmpeg):
                                _HW_ENCODERS.add(nome)
    except Exception:
        pass
    return _HW_ENCODERS


def melhor_encoder_video(format_key: str, ffmpeg: Optional[str] = None) -> Optional[str]:
    """Escolhe o melhor encoder de hardware para um formato de vídeo.

    Retorna None se não houver aceleração disponível (usa CPU).
    """
    hw = encoders_disponiveis(ffmpeg)
    if not hw:
        return None
    # Preferência por formato
    for nome in (f"h264_{e}" for e in ("nvenc", "qsv", "vaapi",
                                       "videotoolbox", "amf")):
        if nome in hw:
            return nome
    return None


def probe_duration(path: str) -> Optional[float]:
    """Duração em segundos via ffprobe (para cálculo de progresso)."""
    ffprobe = shutil.which("ffprobe") or (find_ffmpeg() or "").replace("ffmpeg", "ffprobe")
    if not ffprobe or not os.path.exists(ffprobe):
        return None
    try:
        out = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_format", path],
            capture_output=True, text=True, timeout=15,
        ).stdout
        data = json.loads(out)
        return float(data.get("format", {}).get("duration", 0) or 0) or None
    except Exception:
        return None


def estimar_tamanho(
    input_path: str,
    format_key: str,
    quality: Optional[str] = None,
) -> Optional[int]:
    """Estima o tamanho do arquivo de saída em bytes (heurística).

    - Áudio: duração × bitrate / 8
    - Vídeo: duração × (bitrate de vídeo heurístico + bitrate de áudio) / 8
    - Imagem: heurística por codec e área

    Retorna None se não conseguir estimar (ex.: entrada inexistente).
    """
    from .presets import OUTPUT_FORMATS, QUALITY_PROFILES

    dur = probe_duration(input_path)
    fmt = OUTPUT_FORMATS.get(format_key)
    if not fmt or dur is None:
        return None

    # Bitrate de áudio (kbps) — do perfil de qualidade ou default do codec
    audio_kbps = 192.0
    profile = (QUALITY_PROFILES.get(format_key) or {}).get(quality or "") or []
    for i, arg in enumerate(profile):
        if arg == "-b:a" and i + 1 < len(profile):
            val = profile[i + 1]
            audio_kbps = float(val.rstrip("k"))
        elif arg == "-q:a" and i + 1 < len(profile):
            audio_kbps = 128 + float(profile[i + 1]) * 24

    if fmt.get("image"):
        # Heurística por codec: png ~2.5x, jpg ~0.8x, webp ~0.5x do "peso" da área
        try:
            import os
            src_size = os.path.getsize(input_path)
            factor = {"png": 2.2, "jpg": 0.85, "webp": 0.55,
                      "bmp": 8.0, "tiff": 3.0}.get(format_key, 1.0)
            return int(src_size * factor)
        except OSError:
            return None

    if fmt.get("video"):
        # Heurística de vídeo: resolução/CRF -> bitrate aproximado
        try:
            import subprocess
            ffprobe = shutil.which("ffprobe")
            out = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of",
                 "csv=p=0", input_path],
                capture_output=True, text=True, timeout=10).stdout
            w, h = (int(x) for x in out.strip().split(",")) if out.strip() else (1280, 720)
            area = w * h
            crf = 20
            for i, arg in enumerate(profile):
                if arg == "-crf" and i + 1 < len(profile):
                    crf = int(profile[i + 1])
            # Aproximação: kbps ≈ área / (CRF - 8) * 0.9
            video_kbps = max(300.0, area / max(crf - 8, 1) * 0.9)
        except Exception:
            video_kbps = 2500.0
        total_kbps = video_kbps + audio_kbps
        return int(dur * total_kbps * 1024 / 8)

    # Áudio puro
    return int(dur * audio_kbps * 1024 / 8)


def validar_conversao(input_path: str, format_key: str) -> tuple[bool, str]:
    """Valida se a combinação entrada -> formato de saída faz sentido.

    Retorna (ok, mensagem_de_erro). Combinações impossíveis (áudio -> vídeo,
    imagem -> áudio) são bloqueadas com mensagem amigável em vez de deixar o
    FFmpeg falhar de forma confusa.
    """
    fmt = OUTPUT_FORMATS.get(format_key)
    if not fmt:
        return False, f"Formato de saída desconhecido: {format_key}"
    tipo = classificar_entrada(input_path)
    if tipo is None:
        return True, ""  # extensão desconhecida: deixa o FFmpeg tentar
    saida_video = bool(fmt.get("video")) or format_key == "gif"
    saida_audio = bool(fmt.get("audio"))
    saida_imagem = bool(fmt.get("image"))
    if tipo == "audio":
        if saida_video:
            return False, "Áudio não contém vídeo para converter."
        if saida_imagem:
            return False, "Áudio não pode ser convertido em imagem."
        return True, ""
    if tipo == "image":
        # Bloqueia apenas formato SOMENTE áudio (ex.: mp3). mp4/mkv etc.
        # têm vídeo e áudio: a imagem vira vídeo e o áudio simplesmente
        # não existe — conversão válida.
        if saida_audio and not saida_video:
            return False, "Imagem não contém áudio para extrair."
        if saida_imagem:
            return True, ""  # imagem -> imagem
        return True, ""  # imagem -> vídeo (com duração definida)
    return True, ""  # vídeo -> qualquer coisa


def _build_command(job: ConversionJob, ffmpeg: str) -> list[str]:
    fmt = OUTPUT_FORMATS.get(job.format_key)
    if not fmt:
        raise ValueError(f"Formato de saída desconhecido: {job.format_key}")

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1"]

    tipo_entrada = classificar_entrada(job.input_path)
    eh_imagem_para_video = (
        tipo_entrada == "image"
        and (fmt.get("video") or job.format_key == "gif")
    )

    # Imagem -> vídeo: repete o frame com -loop 1 e limita a duração.
    # IMPORTANTE: com -loop 1 o -t DEVE vir antes do -i (limita a duração
    # do input em loop). Se vier depois (opção de output), o filtro de
    # paleta do GIF fica em loop infinito e o ffmpeg nunca termina.
    if eh_imagem_para_video:
        cmd += ["-loop", "1", "-t", f"{job.duration or 5.0:.3f}"]

    # Corte: -ss antes de -i faz seek rápido (não decodifica o trecho antes)
    if job.start_time and not eh_imagem_para_video:
        cmd += ["-ss", f"{job.start_time:.3f}"]

    cmd += ["-i", job.input_path]

    # Corte: -t limita a duração (fim - início) após ler a entrada.
    # Usar -to com seek de entrada é relativo ao ponto de seek; -t é
    # determinístico: duração = end - start.
    if eh_imagem_para_video:
        pass  # duração já aplicada como opção de input acima
    elif job.start_time is not None and job.end_time is not None:
        cmd += ["-t", f"{max(job.end_time - job.start_time, 0.0):.3f}"]
    elif job.end_time:
        cmd += ["-t", f"{job.end_time:.3f}"]

    # Para GIF, o filtro de paleta dá resultado muito melhor que conversão direta
    if job.format_key == "gif":
        vf = (f"fps={job.gif_fps},scale={job.gif_width}:-1:flags=lanczos,"
              "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse")
        cmd += ["-vf", vf, job.output_path]
        return cmd

    if fmt.get("image"):
        # Imagem: usa o codec de imagem declarado no preset
        cmd += ["-c:v", fmt["vcodec"]]
        if fmt.get("qscale"):
            cmd += ["-q:v", fmt["qscale"]]
    elif fmt["video"]:
        # Aceleração por hardware quando disponível (mp4/mkv/mov -> h264)
        hw_encoder = None
        if job.format_key in ("mp4", "mkv", "mov") and not job.quality:
            hw_encoder = melhor_encoder_video(job.format_key)
        if hw_encoder:
            cmd += ["-c:v", hw_encoder]
            if "nvenc" in hw_encoder:
                cmd += ["-preset", "p4", "-cq", "20"]
            elif "qsv" in hw_encoder:
                cmd += ["-preset", "veryfast", "-global_quality", "20"]
            elif "vaapi" in hw_encoder:
                cmd += ["-global_quality", "20"]
            elif "videotoolbox" in hw_encoder:
                cmd += ["-q:v", "65"]
            elif "amf" in hw_encoder:
                cmd += ["-quality", "balanced", "-rc", "cqp", "-qp_i", "20"]
        else:
            cmd += ["-c:v", fmt["video"]]
            if fmt.get("qscale"):
                cmd += ["-q:v", fmt["qscale"]]
            if job.format_key == "webm":
                cmd += ["-b:v", "0", "-crf", "30"]  # VP9 precisa de -b:v 0 pra CRF valer
            elif job.format_key in ("mp4", "mkv", "mov"):
                cmd += ["-crf", "20", "-preset", "veryfast"]
    else:
        cmd += ["-vn"]

    if fmt["audio"]:
        cmd += ["-c:a", fmt["audio"]]
        if fmt["audio"] == "libmp3lame":
            cmd += ["-b:a", "192k"]
        elif fmt["audio"] == "aac":
            cmd += ["-b:a", "192k"]
        elif fmt["audio"] == "libopus":
            cmd += ["-b:a", "128k"]
        elif fmt["audio"] == "libvorbis":
            cmd += ["-q:a", "5"]

    # Perfil de qualidade explícito (sobrescreve os defaults acima)
    if job.quality:
        from .presets import QUALITY_PROFILES
        profile = QUALITY_PROFILES.get(job.format_key, {}).get(job.quality)
        if profile:
            cmd += profile

    # Redimensionamento (vídeo ou imagem)
    if job.scale:
        cmd += ["-vf", f"scale={job.scale}"]

    # Ajustes de container
    if job.format_key == "mp4":
        cmd += ["-movflags", "+faststart"]
    if job.format_key == "webm" and fmt["video"]:
        cmd += ["-deadline", "good", "-cpu-used", "4"]

    cmd += ["-progress", "pipe:1", job.output_path]
    return cmd


def run_conversion(
    job: ConversionJob,
    callback: Optional[ProgressCallback] = None,
    ffmpeg: Optional[str] = None,
) -> ConversionJob:
    """Executa a conversão de forma síncrona (thread da GUI chama isto)."""
    ffmpeg = ffmpeg or find_ffmpeg()
    if not ffmpeg:
        job.status = "error"
        job.error = "FFmpeg não encontrado. Instale-o ou adicione ao PATH."
        return job

    Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)

    # Descobre a duração para progresso acurado; fallback: estima pelo tamanho do arquivo
    duration = probe_duration(job.input_path)
    est_by_size = None
    if not duration:
        try:
            est_by_size = os.path.getsize(job.input_path) / (1024 * 1024)  # MB -> estimativa
        except OSError:
            pass

    cmd = _build_command(job, ffmpeg)
    job.status = "running"

    try:
        job._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except FileNotFoundError:
        job.status = "error"
        job.error = f"Não foi possível executar o FFmpeg em: {ffmpeg}"
        return job

    last_ms = 0.0
    start = time.time()
    stderr_chunks: list[str] = []

    def _read_stderr():
        assert job._proc and job._proc.stderr
        for line in job._proc.stderr:
            stderr_chunks.append(line)

    t_err = threading.Thread(target=_read_stderr, daemon=True)
    t_err.start()

    assert job._proc.stdout
    for line in job._proc.stdout:
        if job._cancel.is_set():
            break
        line = line.strip()
        if line.startswith("out_time_ms="):
            try:
                last_ms = float(line.split("=", 1)[1])
            except ValueError:
                pass
            if duration:
                pct = min(99.0, last_ms / 1_000_000 / duration * 100)
            elif est_by_size:
                # Heurística pobre mas melhor que nada: assume 2x o tamanho em MB por segundo
                elapsed = max(time.time() - start, 0.001)
                pct = min(99.0, elapsed / max(est_by_size * 2.0, 1.0) * 100)
            else:
                pct = 50.0  # sem duração conhecida, mostra "trabalhando..."
            job.progress = pct
            speed = _format_speed(job, start)
            eta = _format_eta(job, duration, start)
            if callback:
                callback(pct, speed, eta)

    job._proc.wait()
    t_err.join(timeout=2)

    if job._cancel.is_set():
        job.status = "cancelled"
        _safe_remove(job.output_path)
        _log_job(job)
        return job

    if job._proc.returncode != 0:
        job.status = "error"
        err = "".join(stderr_chunks).strip()
        job.error = _humanize_ffmpeg_error(err, job.format_key)
        _safe_remove(job.output_path)
        _log_job(job)
        return job

    job.status = "done"
    job.progress = 100.0
    if callback:
        callback(100.0, None, None)
    _log_job(job)
    return job


def _log_job(job: ConversionJob) -> None:
    """Registra o resultado da conversão no log (se configurado)."""
    try:
        from .logging_setup import log_conversion
        log_conversion(job.input_path, job.format_key, job.status, job.error)
    except Exception:
        pass  # logging nunca deve quebrar a conversão


def _format_speed(job: ConversionJob, start: float) -> Optional[str]:
    if not job.progress or job.progress <= 0:
        return None
    elapsed = max(time.time() - start, 0.001)
    # Estimativa grosseira: progresso%/tempo * tamanho do arquivo de entrada
    try:
        size_mb = os.path.getsize(job.input_path) / (1024 * 1024)
        done_mb = size_mb * job.progress / 100.0
        return f"{done_mb / elapsed:.1f} MB/s"
    except OSError:
        return None


def _format_eta(job: ConversionJob, duration: Optional[float], start: float) -> Optional[str]:
    if not duration or job.progress <= 0:
        return None
    elapsed = max(time.time() - start, 0.001)
    eta_s = (elapsed / job.progress) * (100 - job.progress)
    if eta_s <= 0:
        return "concluindo..."
    if eta_s < 60:
        return f"{eta_s:.0f}s restantes"
    return f"{eta_s / 60:.1f}min restantes"


def _safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _humanize_ffmpeg_error(err: str, fmt_key: str) -> str:
    if not err:
        return "Erro desconhecido do FFmpeg (sem detalhes)."
    lower = err.lower()
    if "no such file" in lower:
        return "Arquivo de entrada não encontrado ou inacessível."
    if "invalid data" in lower or "could not find codec" in lower:
        return "Arquivo de entrada corrompido ou com codec não suportado."
    if "unknown encoder" in lower or "encoder" in lower and "not found" in lower:
        return f"Encoder não disponível no seu FFmpeg para o formato '{fmt_key}'."
    if "permission denied" in lower:
        return "Permissão negada ao escrever o arquivo de saída."
    if "no space" in lower:
        return "Sem espaço em disco para o arquivo de saída."
    # Mostra as últimas 2 linhas do erro, que costumam ter a causa real
    lines = [l for l in err.splitlines() if l.strip()]
    detail = " | ".join(lines[-2:])[:300]
    return f"Erro do FFmpeg: {detail}"


# ---------------------------------------------------------------- CLI (teste)
def main() -> None:
    """CLI simples: python -m converter.ffmpeg_core entrada.mp4 mp3 [saida] [--start S] [--end E] [--quality Q] [--scale WxH]"""
    import sys

    args = sys.argv[1:]
    if len(args) < 2:
        print("Uso: python -m converter.ffmpeg_core <entrada> <formato> [saida] "
              "[--start SEG] [--end SEG] [--quality NOME] [--scale WxH]")
        sys.exit(1)

    src = args[0]
    fmt_key = args[1]
    dst = args[2] if len(args) > 2 and not args[2].startswith("--") else str(
        Path(src).with_suffix(f".{fmt_key}"))

    job = ConversionJob(input_path=src, output_path=dst, format_key=fmt_key,
                        title=Path(src).name)

    i = 3
    while i < len(args):
        if args[i] == "--start" and i + 1 < len(args):
            job.start_time = float(args[i + 1])
            i += 2
        elif args[i] == "--end" and i + 1 < len(args):
            job.end_time = float(args[i + 1])
            i += 2
        elif args[i] == "--quality" and i + 1 < len(args):
            job.quality = args[i + 1]
            i += 2
        elif args[i] == "--scale" and i + 1 < len(args):
            job.scale = args[i + 1]
            i += 2
        else:
            i += 1

    def cb(pct, speed, eta):
        print(f"\r{pct:5.1f}%  {speed or ''}  {eta or ''}   ", end="", flush=True)

    run_conversion(job, cb)
    print(f"\n[{job.status}] {job.error or dst}")


if __name__ == "__main__":
    main()
