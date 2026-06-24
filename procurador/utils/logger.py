"""
Logger estruturado do Procurador de Câmara.

Fornece get_logger() que devolve um logger configurado com formatação Rich
(cores) e nível configurável via env (PROCURADOR_LOG_LEVEL).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Tentar Rich (preferido); cair para logging básico se indisponível
try:
    from rich.logging import RichHandler

    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


_LOG_FORMAT_SIMPLE = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_FORMAT_RICH = "%(message)s"


_CONFIGURED: set[str] = set()


def configure_logging(
    level: str = "INFO",
    log_file: str | None = None,
    quiet_modules: list[str] | None = None,
) -> None:
    """Configura o logging global uma vez.

    Args:
        level: Nível (DEBUG, INFO, WARNING, ERROR).
        log_file: Se definido, escreve também para este ficheiro.
        quiet_modules: Lista de nomes de loggers a silenciar (ex.: ['scapy']).
    """
    root = logging.getLogger()
    if root.handlers:
        return  # Já configurado

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = []

    if _HAS_RICH and sys.stderr.isatty():
        handlers.append(
            RichHandler(
                rich_tracebacks=True,
                show_path=False,
                show_time=True,
                markup=True,
            )
        )
    else:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter(_LOG_FORMAT_SIMPLE))
        handlers.append(h)

    if log_file:
        p = Path(log_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(p, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_LOG_FORMAT_SIMPLE))
        handlers.append(fh)

    logging.basicConfig(
        level=numeric_level,
        format=_LOG_FORMAT_RICH,
        datefmt="[%X]",
        handlers=handlers,
        force=True,
    )

    for m in quiet_modules or []:
        logging.getLogger(m).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Devolve um logger, configurando o root na primeira chamada.

    Args:
        name: Nome do logger (tipicamente __name__).

    Returns:
        logging.Logger configurado.
    """
    if name not in _CONFIGURED:
        level = os.environ.get("PROCURADOR_LOG_LEVEL", "INFO")
        configure_logging(level=level)
        _CONFIGURED.add(name)
    return logging.getLogger(name)
