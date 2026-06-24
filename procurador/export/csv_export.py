"""
Export CSV — tabela simples com colunas-chave.

Compatível com Excel, LibreOffice, pandas.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from procurador.core.models import Camera, ScanResult

# Colunas do CSV
COLUMNS: list[str] = [
    "ip",
    "port",
    "status",
    "vendor",
    "model",
    "country",
    "country_code",
    "city",
    "lat",
    "lon",
    "rtsp_url",
    "rtsp_path",
    "auth_user",
    "auth_pass",
    "auth_method",
    "access_method",
    "onvif_supported",
    "cve_exploited",
    "resolution",
    "codec",
    "http_url",
    "screenshot_path",
    "source",
    "first_seen",
    "tags",
    "error_message",
]


def _camera_to_row(cam: Camera) -> dict[str, Any]:
    """Converte uma Camera numa row dict para CSV."""
    return {
        "ip": cam.ip,
        "port": cam.port,
        "status": cam.status.value,
        "vendor": cam.vendor or "",
        "model": cam.model or "",
        "country": cam.geo.country or "",
        "country_code": cam.geo.country_code or "",
        "city": cam.geo.city or "",
        "lat": cam.geo.lat if cam.geo.lat is not None else "",
        "lon": cam.geo.lon if cam.geo.lon is not None else "",
        "rtsp_url": cam.rtsp_url or "",
        "rtsp_path": cam.rtsp_path or "",
        "auth_user": cam.auth_user or "",
        "auth_pass": cam.auth_pass or "",
        "auth_method": cam.auth_method or "",
        "access_method": cam.access_method.value if cam.access_method else "",
        "onvif_supported": "yes" if cam.onvif_supported else "no",
        "cve_exploited": cam.cve_exploited or "",
        "resolution": cam.resolution,
        "codec": cam.stream.codec if cam.stream else "",
        "http_url": cam.http_url or "",
        "screenshot_path": cam.screenshot_path or "",
        "source": cam.source.value,
        "first_seen": cam.first_seen,
        "tags": ";".join(cam.tags) if cam.tags else "",
        "error_message": cam.error_message or "",
    }


def export_csv(
    result: ScanResult,
    output_path: str,
    include_all: bool = True,
) -> str:
    """Exporta câmaras para CSV.

    Args:
        result: ScanResult.
        output_path: Caminho de output.
        include_all: Se True, inclui câmaras não-acessiveis.

    Returns:
        Caminho escrito.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    cameras = result.cameras
    if not include_all:
        cameras = [c for c in cameras if c.is_accessible]

    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for cam in cameras:
            writer.writerow(_camera_to_row(cam))

    return str(p)
