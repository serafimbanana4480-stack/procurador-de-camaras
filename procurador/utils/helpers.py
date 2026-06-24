"""
Utilitários do Procurador de Câmara.

- retry() — decorator para retry com backoff exponencial
- rate_limit() — decorator para throttling
- timeout() — decorator para timeout via signal (não funciona em Windows para threads)
- safe_run() — corre função com captura de exceções
- extract_title() — extrai <title> de HTML
- chunked() — divide lista em batches
"""

from __future__ import annotations

import functools
import random
import re
import time
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from procurador.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


# =====================================================================
# Decorators
# =====================================================================


def retry(
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    tries: int = 3,
    delay: float = 0.5,
    backoff: float = 2.0,
    max_delay: float = 10.0,
    jitter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: retry com backoff exponencial.

    Args:
        exceptions: Tupla de exceções que justificam retry.
        tries: Número total de tentativas.
        delay: Delay inicial (segundos).
        backoff: Multiplicador entre tentativas.
        max_delay: Limite superior do delay.
        jitter: Adicionar random jitter (0-0.5s) para evitar thundering herd.
    """

    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exc: BaseException | None = None
            for attempt in range(1, tries + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == tries:
                        logger.debug(f"{fn.__name__} falhou após {tries} tentativas: {e}")
                        break
                    sleep_for = current_delay + (random.random() * 0.5 if jitter else 0)
                    logger.debug(
                        f"{fn.__name__} tentativa {attempt}/{tries} falhou: {e}. "
                        f"Aguardar {sleep_for:.2f}s"
                    )
                    time.sleep(sleep_for)
                    current_delay = min(current_delay * backoff, max_delay)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return deco


def rate_limit(
    calls: int = 1,
    period: float = 1.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: limita chamadas por período (token bucket simplificado).

    Args:
        calls: Máximo de chamadas por período.
        period: Janela de tempo em segundos.
    """
    interval = period / calls if calls > 0 else 0
    last_call: list[float] = [0.0]

    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            now = time.monotonic()
            wait = interval - (now - last_call[0])
            if wait > 0:
                time.sleep(wait)
            last_call[0] = time.monotonic()
            return fn(*args, **kwargs)

        return wrapper

    return deco


# =====================================================================
# Helpers funcionais
# =====================================================================


def safe_run(
    fn: Callable[..., T],
    *args: Any,
    default: T | None = None,
    log_errors: bool = True,
    **kwargs: Any,
) -> T | None:
    """Corre uma função e captura todas as exceções.

    Args:
        fn: Função a executar.
        *args, **kwargs: Argumentos.
        default: Valor a devolver em caso de erro.
        log_errors: Se True, regista o erro via logger.

    Returns:
        Resultado da função ou default.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.debug(f"safe_run({fn.__name__}) falhou: {e}")
        return default


_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE | re.DOTALL)


def extract_title(html: str) -> str | None:
    """Extrai <title> de um HTML. Devolve None se não encontrar."""
    if not html:
        return None
    m = _TITLE_RE.search(html)
    if not m:
        return None
    title = m.group(1).strip()
    return title[:200] if title else None


def chunked(items: list[T], size: int) -> Iterable[list[T]]:
    """Divide uma lista em batches de tamanho `size`.

    Args:
        items: Lista de entrada.
        size: Tamanho de cada batch (>0).

    Yields:
        Listas de até `size` elementos.
    """
    if size <= 0:
        size = 1
    for i in range(0, len(items), size):
        yield items[i : i + size]


def parse_hostport(s: str, default_port: int = 554) -> tuple[str, int]:
    """Parseia 'ip:port' ou só 'ip'.

    Args:
        s: String de input.
        default_port: Porto por omissão se não especificado.

    Returns:
        Tupla (ip, port).
    """
    s = s.strip()
    if ":" in s:
        host, _, port_str = s.rpartition(":")
        try:
            return host, int(port_str)
        except ValueError:
            return host, default_port
    return s, default_port


def is_valid_ip(s: str) -> bool:
    """Verifica se uma string é um IP válido (v4)."""
    import ipaddress

    try:
        ipaddress.IPv4Address(s)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False
