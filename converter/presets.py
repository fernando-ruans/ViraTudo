"""Formatos suportados pelo conversor.

Cada entrada: extensão -> (descrição, codec de vídeo, codec de áudio, container).
None em vídeo = só áudio. Containers e codecs escolhidos pela compatibilidade
universal (reproduz em qualquer player, navegador, celular).
"""

# Formatos de SAÍDA (conversão)
# fmt: off
OUTPUT_FORMATS = {
    # ---- Vídeo ----
    "mp4":  {"label": "MP4 (vídeo H.264 + áudio AAC) — máxima compatibilidade",
             "video": "libx264", "audio": "aac",     "ext": "mp4",
             "vcodec": "h264", "acodec": "aac"},
    "mkv":  {"label": "MKV (vídeo H.264 + áudio AAC) — legendas/faixas múltiplas",
             "video": "libx264", "audio": "aac",     "ext": "mkv",
             "vcodec": "h264", "acodec": "aac"},
    "webm": {"label": "WebM (vídeo VP9 + áudio Opus) — leve p/ web",
             "video": "libvpx-vp9", "audio": "libopus", "ext": "webm",
             "vcodec": "vp9", "acodec": "opus"},
    "avi":  {"label": "AVI (vídeo MPEG-4 + áudio MP3) — antigo, quase tudo abre",
             "video": "mpeg4", "audio": "libmp3lame", "ext": "avi",
             "vcodec": "mpeg4", "acodec": "mp3"},
    "mov":  {"label": "MOV (QuickTime) — edição no Mac/Adobe",
             "video": "libx264", "audio": "aac",     "ext": "mov",
             "vcodec": "h264", "acodec": "aac"},
    "mpg":  {"label": "MPEG (VCD/DVD players antigos)",
             "video": "mpeg2video", "audio": "mp2", "ext": "mpg",
             "vcodec": "mpeg2", "acodec": "mp2"},
    "gif":  {"label": "GIF animado (sem som, pesado)",
             "video": None, "audio": None, "ext": "gif",
             "vcodec": "gif", "acodec": None},
    # ---- Áudio ----
    "mp3":  {"label": "MP3 (qualidade 192 kbps)",
             "video": None, "audio": "libmp3lame", "ext": "mp3",
             "vcodec": None, "acodec": "mp3"},
    "flac": {"label": "FLAC (sem perdas)",
             "video": None, "audio": "flac", "ext": "flac",
             "vcodec": None, "acodec": "flac"},
    "wav":  {"label": "WAV (PCM 16-bit, sem compressão)",
             "video": None, "audio": "pcm_s16le", "ext": "wav",
             "vcodec": None, "acodec": "pcm_s16le"},
    "ogg":  {"label": "OGG (Vorbis q5)",
             "video": None, "audio": "libvorbis", "ext": "ogg",
             "vcodec": None, "acodec": "vorbis"},
    "opus": {"label": "Opus (melhor qualidade/tamanho p/ fala e música)",
             "video": None, "audio": "libopus", "ext": "opus",
             "vcodec": None, "acodec": "opus"},
    "m4a":  {"label": "M4A (AAC) — formato iTunes/iPhone",
             "video": None, "audio": "aac", "ext": "m4a",
             "vcodec": None, "acodec": "aac"},
    # ---- Imagem (via FFmpeg) ----
    "png":  {"label": "PNG (sem perdas, transparência)",
             "video": None, "audio": None, "ext": "png",
             "vcodec": "png", "acodec": None, "image": True},
    "jpg":  {"label": "JPG (qualidade 92, sem transparência)",
             "video": None, "audio": None, "ext": "jpg",
             "vcodec": "mjpeg", "acodec": None, "image": True, "qscale": "2"},
    "webp": {"label": "WebP (moderno, leve)",
             "video": None, "audio": None, "ext": "webp",
             "vcodec": "libwebp", "acodec": None, "image": True},
    "bmp":  {"label": "BMP (sem compressão, gigante)",
             "video": None, "audio": None, "ext": "bmp",
             "vcodec": "bmp", "acodec": None, "image": True},
    "tiff": {"label": "TIFF (scans/impressão)",
             "video": None, "audio": None, "ext": "tiff",
             "vcodec": "tiff", "acodec": None, "image": True},
}
# fmt: on

# Extensões de ENTRADA reconhecidas (para filtro de arquivos e detecção)
INPUT_VIDEO = ("mp4", "mkv", "webm", "avi", "mov", "wmv", "flv", "mpg", "mpeg",
               "m4v", "ts", "3gp", "ogv", "vob")
INPUT_AUDIO = ("mp3", "wav", "flac", "ogg", "opus", "m4a", "aac", "wma", "ac3",
               "aiff", "alac", "amr", "au", "caf", "dts", "ra", "ape", "mka")
INPUT_IMAGE = ("png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif", "svg",
               "heic", "ico", "psd", "raw", "avif")

ALL_INPUT_EXT = sorted(set(INPUT_VIDEO + INPUT_AUDIO + INPUT_IMAGE))

# Formatos de SAÍDA por categoria (derivados de OUTPUT_FORMATS)
AUDIO_FORMATS = {k for k, v in OUTPUT_FORMATS.items()
                 if v.get("audio") and not v.get("video") and not v.get("image")}
VIDEO_FORMATS = {k for k, v in OUTPUT_FORMATS.items()
                 if v.get("video") or k == "gif"}
IMAGE_FORMATS = {k for k, v in OUTPUT_FORMATS.items() if v.get("image")}


def classificar_entrada(path: str) -> str | None:
    """Classifica um arquivo de entrada: 'video', 'audio', 'image' ou None."""
    from pathlib import Path
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in INPUT_VIDEO:
        return "video"
    if ext in INPUT_AUDIO:
        return "audio"
    if ext in INPUT_IMAGE:
        return "image"
    return None


# Perfis de qualidade por formato: chave visível -> lista de args FFmpeg
QUALITY_PROFILES = {
    "mp3": {
        "128 kbps (menor)": ["-b:a", "128k"],
        "192 kbps (padrão)": ["-b:a", "192k"],
        "320 kbps (maior)": ["-b:a", "320k"],
    },
    "m4a": {
        "128 kbps": ["-b:a", "128k"],
        "192 kbps (padrão)": ["-b:a", "192k"],
        "256 kbps": ["-b:a", "256k"],
    },
    "ogg": {
        "q3 (menor)": ["-q:a", "3"],
        "q5 (padrão)": ["-q:a", "5"],
        "q7 (maior)": ["-q:a", "7"],
    },
    "opus": {
        "96 kbps": ["-b:a", "96k"],
        "128 kbps (padrão)": ["-b:a", "128k"],
        "192 kbps": ["-b:a", "192k"],
    },
    "wav": {
        "PCM 16-bit (padrão)": ["-c:a", "pcm_s16le"],
        "PCM 24-bit": ["-c:a", "pcm_s24le"],
    },
    "flac": {
        "Sem perdas (padrão)": ["-compression_level", "5"],
        "Sem perdas, máx. compressão": ["-compression_level", "12"],
    },
    "mp4": {
        "CRF 28 (menor tamanho)": ["-crf", "28"],
        "CRF 20 (padrão)": ["-crf", "20"],
        "CRF 16 (maior qualidade)": ["-crf", "16"],
    },
    "mkv": {
        "CRF 28 (menor tamanho)": ["-crf", "28"],
        "CRF 20 (padrão)": ["-crf", "20"],
        "CRF 16 (maior qualidade)": ["-crf", "16"],
    },
    "mov": {
        "CRF 28 (menor tamanho)": ["-crf", "28"],
        "CRF 20 (padrão)": ["-crf", "20"],
        "CRF 16 (maior qualidade)": ["-crf", "16"],
    },
    "webm": {
        "CRF 40 (menor tamanho)": ["-crf", "40"],
        "CRF 30 (padrão)": ["-crf", "30"],
        "CRF 20 (maior qualidade)": ["-crf", "20"],
    },
    "jpg": {
        "q2 (alta)": ["-q:v", "2"],
        "q5 (média)": ["-q:v", "5"],
        "q8 (baixa, menor)": ["-q:v", "8"],
    },
    "png": {
        "Sem perdas (padrão)": ["-compression_level", "6"],
    },
}

# Resoluções de redimensionamento comuns (vídeo e imagem)
SCALE_OPTIONS = {
    "Original (sem alterar)": None,
    "3840x2160 (4K)": "3840:2160",
    "1920x1080 (Full HD)": "1920:1080",
    "1280x720 (HD)": "1280:720",
    "854x480 (SD)": "854:480",
    "640x360": "640:360",
}


def describe(format_key: str) -> str:
    """Descrição amigável de um formato de saída."""
    fmt = OUTPUT_FORMATS.get(format_key)
    return fmt["label"] if fmt else format_key
