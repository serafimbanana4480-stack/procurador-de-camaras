"""
Integração com Shodan API.

Procura dispositivos com serviços RTSP/HTTP/ONVIF.

Uso:
    search_shodan(config, api_key) -> Generator[Camera]
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from typing import Any

import requests

from procurador.core.models import (
    Camera,
    CameraStatus,
    GeoLocation,
    NetworkInfo,
    ScanConfig,
    SourceType,
)

logger = logging.getLogger(__name__)

SHODAN_BASE = "https://api.shodan.io"


def get_shodan_key() -> str | None:
    """Obter chave Shodan do ambiente."""
    return os.environ.get("SHODAN_API_KEY") or None


def search_shodan(
    config: ScanConfig,
    api_key: str | None = None,
) -> Generator[Camera, None, None]:
    """Procura câmaras no Shodan.

    Args:
        config: ScanConfig (usa country, query).
        api_key: API key (opcional; usa env).

    Yields:
        Camera objects.
    """
    if not api_key:
        api_key = get_shodan_key()
        if not api_key:
            logger.warning("Shodan API key não configurada (SHODAN_API_KEY)")
            return

    # Construir query
    parts = ["RTSP", "port:554"]
    if config.censys_country:
        parts.append(f"country:{config.censys_country}")
    query = " ".join(parts)

    logger.info(f"Shodan: query={query!r}")

    try:
        for cam in _search_shodan_paginated(api_key, query, config):
            if cam:
                yield cam
    except requests.exceptions.RequestException as e:
        logger.error(f"Shodan error: {e}")


def _search_shodan_paginated(
    key: str,
    query: str,
    config: ScanConfig,
) -> Generator[Camera, None, None]:
    """Pesquisa Shodan com paginação."""
    page = 1
    total_results = 0

    while page <= min(config.censys_max_pages, 10):  # Shodan max 10 pages for free
        params: dict[str, Any] = {
            "key": key,
            "query": query,
            "page": page,
            "limit": min(config.censys_per_page, 100),
        }
        try:
            r = requests.get(
                f"{SHODAN_BASE}/shodan/host/search",
                params=params,
                timeout=15,
            )
        except requests.exceptions.Timeout:
            logger.warning(f"Shodan timeout (pagina {page})")
            return
        except Exception as e:
            logger.error(f"Shodan error: {e}")
            return

        if r.status_code == 200:
            data = r.json()
            matches = data.get("matches", [])
            if not matches:
                break
            for match in matches:
                camera = _parse_shodan_match(match)
                if camera:
                    total_results += 1
                    yield camera
            page += 1
        elif r.status_code == 403:
            logger.warning("Shodan: pesquisa bloqueada (conta free sem creditos)")
            return
        elif r.status_code == 401:
            logger.error("Shodan: API key invalida")
            return
        else:
            logger.debug(f"Shodan: {r.status_code} — {r.text[:100]}")
            return

    if total_results > 0:
        logger.info(f"   Shodan: {total_results} cameras ({page-1} pagina(s))")


def _parse_shodan_match(match: dict) -> Camera | None:
    """Converte match Shodan em Camera."""
    ip = match.get("ip_str")
    port = match.get("port", 554)
    if not ip:
        return None

    # Location
    loc = match.get("location", {}) or {}
    geo = GeoLocation(
        country=loc.get("country_name"),
        country_code=loc.get("country_code"),
        city=loc.get("city"),
        region=loc.get("region_code"),
        lat=loc.get("latitude"),
        lon=loc.get("longitude"),
    )

    # Data
    data_str = match.get("data", "") or ""
    match.get("transport", "")
    product = match.get("product", "") or ""
    org = match.get("org", "") or ""
    asn = match.get("asn", "") or ""
    os_info = match.get("os", "") or ""
    hostnames = match.get("hostnames", []) or []

    vendor = identify_shodan_vendor(data_str, product)

    ports_open = [port]
    if match.get("dns"):
        pass

    network = NetworkInfo(
        isp=org if "ISP" in org.upper() else None,
        org=org or None,
        asn=asn or None,
        hostname=hostnames[0] if hostnames else None,
    )

    return Camera(
        ip=ip,
        port=port,
        source=SourceType.CENSYS,  # Reutilizar CENSYS como generic external
        vendor=vendor,
        geo=geo,
        network=network,
        ports_open=ports_open,
        raw_banner=data_str[:500] if data_str else None,
        status=CameraStatus.PENDING,
        http_title=extract_shodan_title(data_str),
    )


def identify_shodan_vendor(data: str, product: str) -> str | None:
    """Identificar fabricante a partir de dados Shodan."""
    combined = (data + " " + product).lower()
    vendors = {
        "Hikvision": ["hikvision", "hik"],
        "Dahua": ["dahua", "dahu"],
        "Axis": ["axis", "axis communications"],
        "Reolink": ["reolink"],
        "TP-Link": ["tp-link", "tplink"],
        "Foscam": ["foscam"],
        "Bosch": ["bosch"],
        "Panasonic": ["panasonic"],
        "Sony": ["sony"],
        "Vivotek": ["vivotek"],
    }
    for vendor, keywords in vendors.items():
        if any(k in combined for k in keywords):
            return vendor
    if "camera" in combined or "ipcam" in combined or "ipc" in combined:
        return "Generic IP Camera"
    return None


def extract_shodan_title(data: str) -> str | None:
    """Extrair título HTTP de banner Shodan."""
    if not data:
        return None
    lines = data.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("<title>") or line.startswith("<TITLE>"):
            return line.replace("<title>", "").replace("</title>", "").strip()
    for tag in ["Server: ", "WWW-Authenticate: Digest "]:
        for line in lines:
            if line.startswith(tag):
                val = line[len(tag):].strip()
                if val:
                    return val
    return None


def shodan_host_lookup(ip: str, api_key: str | None = None) -> dict | None:
    """Lookup de um IP especifico no Shodan (gratuito)."""
    if not api_key:
        api_key = get_shodan_key()
        if not api_key:
            return None
    try:
        r = requests.get(
            f"{SHODAN_BASE}/shodan/host/{ip}",
            params={"key": api_key},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f"Shodan lookup {ip}: {e}")
    return None
