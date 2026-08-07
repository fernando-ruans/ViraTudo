#!/usr/bin/env python3
"""Conversor Universal — entry point.

Uso:
    python app.py                # abre a interface gráfica
    python app.py --version      # mostra a versão e sai
    python app.py --cli in.mp4 mp3 [saida]   # conversão via terminal
    python app.py --yt <url> [mp3] [pasta]   # download do YouTube via terminal
"""

from __future__ import annotations

import sys


def main() -> int:
    from converter import __version__
    from converter.logging_setup import setup_logging

    setup_logging()  # logs em ~/ViraTudo/logs/app.log

    args = sys.argv[1:]

    if args and args[0] == "--version":
        print(f"ViraTudo v{__version__}")
        return 0

    if args and args[0] == "--cli":
        from converter.ffmpeg_core import main as cli_main
        sys.argv = [sys.argv[0]] + args[1:]
        cli_main()
        return 0

    if args and args[0] == "--yt":
        from converter.youtube import main as yt_main
        sys.argv = [sys.argv[0]] + args[1:]
        yt_main()
        return 0

    # GUI
    from ui.main_window import run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
