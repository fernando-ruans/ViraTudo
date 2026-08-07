"""Persistência de configurações do usuário (QSettings).

Wrapper fino com getters/setters tipados por seção. Os valores são salvos
no registro do Windows ou ~/.config no Linux — padrão Qt.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

ORG = "ViraTudo"
APP = "ViraTudo"


def _settings() -> QSettings:
    return QSettings(ORG, APP)


# ---------------------------------------------------------------- converter
def get_convert_dst() -> str:
    return _settings().value("convert/ultima_pasta",
                             str(Path.home() / "Conversor"))


def set_convert_dst(path: str) -> None:
    _settings().setValue("convert/ultima_pasta", path)


def get_convert_format() -> str:
    return _settings().value("convert/formato", "mp4")


def set_convert_format(fmt: str) -> None:
    _settings().setValue("convert/formato", fmt)


def get_convert_quality() -> str:
    return _settings().value("convert/qualidade", "")


def set_convert_quality(q: str) -> None:
    _settings().setValue("convert/qualidade", q)


# ---------------------------------------------------------------- youtube
def get_yt_dst() -> str:
    return _settings().value("youtube/ultima_pasta",
                             str(Path.home() / "Downloads" / "YouTube"))


def set_yt_dst(path: str) -> None:
    _settings().setValue("youtube/ultima_pasta", path)


def get_yt_format() -> str:
    return _settings().value("youtube/formato", "mp4")


def set_yt_format(fmt: str) -> None:
    _settings().setValue("youtube/formato", fmt)


def get_yt_quality() -> str:
    return _settings().value("youtube/qualidade", "best")


def set_yt_quality(q: str) -> None:
    _settings().setValue("youtube/qualidade", q)


# ---------------------------------------------------------------- app
def get_theme() -> str:
    return _settings().value("app/tema", "auto")


def set_theme(t: str) -> None:
    _settings().setValue("app/tema", t)


def get_parallel_jobs() -> int:
    try:
        return int(_settings().value("app/jobs_paralelos", 2))
    except (TypeError, ValueError):
        return 2


def set_parallel_jobs(n: int) -> None:
    _settings().setValue("app/jobs_paralelos", n)
