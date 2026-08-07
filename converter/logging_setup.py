"""Configuração de logging do ViraTudo.

Logs vão para ~/ViraTudo/logs/app.log com rotação de 1 MB.
Nível INFO no arquivo; erros com traceback completo.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path.home() / "ViraTudo" / "logs"
LOG_FILE = LOG_DIR / "app.log"

_configured = False


def setup_logging() -> logging.Logger:
    """Configura o logger raiz uma única vez. Retorna o logger 'viratudo'."""
    global _configured
    logger = logging.getLogger("viratudo")
    if _configured:
        return logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)

    # Rotação: 1 MB por arquivo, mantém 3 arquivos antigos
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)

    _configured = True
    logger.info("=== ViraTudo iniciado ===")
    return logger


def log_conversion(entrada: str, formato: str, status: str, erro: str = "") -> None:
    """Registra uma conversão no log."""
    logger = logging.getLogger("viratudo")
    msg = f"conversão | in={entrada} | fmt={formato} | status={status}"
    if erro:
        msg += f" | erro={erro[:200]}"
    logger.info(msg)


def log_download(url: str, formato: str, status: str, erro: str = "") -> None:
    """Registra um download do YouTube no log."""
    logger = logging.getLogger("viratudo")
    msg = f"download | url={url} | fmt={formato} | status={status}"
    if erro:
        msg += f" | erro={erro[:200]}"
    logger.info(msg)
