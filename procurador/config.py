"""
Configuração do Procurador de Câmara.

Carrega:
- Variáveis de ambiente (.env)
- Ficheiro TOML (opcional)
- Defaults via ScanConfig

Uso:
    config = load_config()
    print(config.censys_api_id)
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import tomllib

from procurador.core.models import ScanConfig

logger = logging.getLogger(__name__)

# Paths padrão
DEFAULT_CONFIG_PATH = "procurador.toml"
ENV_PATH = ".env"


# =====================================================================
# Env loading (sem dependência de python-dotenv)
# =====================================================================


def load_env(env_path: str = ENV_PATH) -> None:
    """Carrega variáveis de .env para o ambiente, se existir.

    Formato esperado: KEY=value (uma por linha; # comentários).
    Não faz override se a variável já existir no ambiente.
    """
    p = Path(env_path)
    if not p.exists():
        return

    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception as e:
        logger.debug(f"Erro a ler {env_path}: {e}")


# =====================================================================
# TOML loading
# =====================================================================


def load_toml(path: str = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Carrega configuração TOML. Devolve {} se não existir."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with p.open("rb") as f:
            return tomllib.load(f)
    except Exception as e:
        logger.warning(f"Erro a ler TOML {path}: {e}")
        return {}


# =====================================================================
# Public API
# =====================================================================


def load_config(
    toml_path: str = DEFAULT_CONFIG_PATH,
    env_path: str = ENV_PATH,
) -> ScanConfig:
    """Carrega ScanConfig a partir de .env, TOML e defaults.

    Ordem de precedência (maior → menor):
    1. Variáveis de ambiente (CENSYS_API_ID, IPINFO_TOKEN, ...)
    2. Ficheiro TOML
    3. Defaults (ScanConfig)
    """
    load_env(env_path)
    toml_data = load_toml(toml_path)

    # Defaults
    cfg_dict: dict[str, Any] = asdict(ScanConfig())

    # Override com TOML (seção [scan])
    if "scan" in toml_data:
        for key, val in toml_data["scan"].items():
            if key in cfg_dict:
                cfg_dict[key] = val
            else:
                logger.debug(f"TOML key ignorada: scan.{key}")

    # Override com ENV (apenas chaves que existem no config)
    env_map = {
        "CENSYS_QUERY": "censys_query",
        "CENSYS_COUNTRY": "censys_country",
        "CENSYS_MAX_PAGES": "censys_max_pages",
        "RTSP_PROBE_TIMEOUT": "rtsp_probe_timeout",
        "RTSP_PROBE_CONCURRENT": "rtsp_probe_concurrent",
        "BRUTE_ENABLED": "brute_enabled",
        "STREAM_CAPTURE": "stream_capture",
        "ONVIF_ENABLED": "onvif_enabled",
        "GEOIP_ENABLED": "geoip_enabled",
        "IPINFO_TOKEN": "ipinfo_token",
        "LOCAL_SUBNET": "local_subnet",
        "LOCAL_ENABLED": "local_enabled",
        "STEALTH": "stealth",
    }
    for env_key, cfg_key in env_map.items():
        env_val = os.environ.get(env_key)
        if env_val is not None and cfg_key in cfg_dict:
            current = cfg_dict[cfg_key]
            if isinstance(current, bool):
                cfg_dict[cfg_key] = env_val.lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                try:
                    cfg_dict[cfg_key] = int(env_val)
                except ValueError:
                    pass
            elif isinstance(current, float):
                try:
                    cfg_dict[cfg_key] = float(env_val)
                except ValueError:
                    pass
            elif isinstance(current, list):
                cfg_dict[cfg_key] = [
                    int(x) for x in env_val.split(",") if x.strip().isdigit()
                ] or current
            else:
                cfg_dict[cfg_key] = env_val

    return ScanConfig(**cfg_dict)


# =====================================================================
# API key helpers
# =====================================================================


def get_censys_credentials() -> tuple[str | None, str | None]:
    """Devolve (api_id, api_secret) a partir do ambiente.

    Suporta 4 formatos (por ordem de precedência):
    1. Personal Access Token (recomendado):
       CENSYS_PERSONAL_ACCESS_TOKEN="<token>" → (token, None)
    2. Personal Access Token (alternativo):
       CENSYS_API_KEY="<token>" → (token, None)
    3. API ID / Secret (v1/v2 clássico):
       CENSYS_API_ID="xxx" + CENSYS_SECRET="yyy" → ("xxx", "yyy")
    4. Combinado antigo (id:secret):
       CENSYS_API_KEY="id:secret" → ("id", "secret")

    PAT (None secret) vs clássico ("" secret) são distintos:
    - secret=None → Personal Access Token (SDK v0.14+)
    - secret=""   → API ID com secret vazio (clássico obsoleto)
    """
    # 1. CENSYS_PERSONAL_ACCESS_TOKEN (prioritário)
    pat = os.environ.get("CENSYS_PERSONAL_ACCESS_TOKEN")
    if pat:
        return pat, None

    # 2. CENSYS_API_KEY (PAT ou combinado antigo)
    api_key = os.environ.get("CENSYS_API_KEY")
    if api_key:
        if ":" in api_key:
            # Formato combinado antigo: "id:secret"
            parts = api_key.split(":", 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        # PAT: token inteiro como api_id, api_secret=None
        return api_key, None

    # 3. API ID + Secret clássico
    api_id = os.environ.get("CENSYS_API_ID")
    api_secret = os.environ.get("CENSYS_SECRET") or os.environ.get("CENSYS_API_SECRET")
    if api_secret:
        api_secret = api_secret.strip()

    if api_secret:
        return api_id, api_secret
    return api_id, None


def get_ipinfo_token() -> str | None:
    """Devolve o token do ipinfo.io (ou None)."""
    return os.environ.get("IPINFO_TOKEN") or None
