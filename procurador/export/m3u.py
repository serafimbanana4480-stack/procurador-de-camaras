"""
Export M3U — playlist VLC/FFmpeg de streams LIVE.

Formato M3U com paths RTSP, com metadata adicional em #EXTINF.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from procurador.core.models import Camera, CameraStatus, ScanResult

M3U_HEADER = "#EXTM3U\n"


def _to_extinf(cam: Camera) -> str:
    """Converte uma Camera numa linha #EXTINF."""
    parts = []
    if cam.vendor:
        parts.append(f"[{cam.vendor}]")
    if cam.geo.country:
        parts.append(cam.geo.country)
    if cam.geo.city:
        parts.append(cam.geo.city)
    if cam.resolution and cam.resolution != "N/A":
        parts.append(f"({cam.resolution})")
    if cam.auth_user and cam.auth_pass:
        parts.append(f"creds={cam.auth_user}:{cam.auth_pass}")

    label = " ".join(parts) if parts else "Camera"
    duration = -1  # -1 = live
    return f"#EXTINF:{duration},{label}"


def export_m3u(
    result: ScanResult,
    output_path: str,
    include_web: bool = False,
) -> str:
    """Exporta playlist M3U com câmaras LIVE.

    Args:
        result: ScanResult.
        output_path: Caminho de saída.
        include_web: Se True, inclui também câmaras WEB_ONLY com snapshot.

    Returns:
        Caminho escrito.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [M3U_HEADER]

    # Stats no header (comentário)
    lines.append(f"# Procurador de Câmara — scan {result.scan_id}")
    lines.append(
        f"# {result.accessible} LIVE / {result.auth_required} AUTH / {result.web_only} WEB"
    )
    if result.started_at:
        lines.append(f"# {datetime.fromtimestamp(result.started_at).isoformat()}")
    lines.append("")

    count = 0
    for cam in result.cameras:
        if cam.status == CameraStatus.LIVE and cam.rtsp_url:
            lines.append(_to_extinf(cam))
            lines.append(cam.rtsp_url)
            lines.append("")
            count += 1
        elif include_web and cam.status == CameraStatus.WEB_ONLY and cam.http_snapshot_url:
            # Para WEB_ONLY, usar snapshot URL (não RTSP)
            lines.append(f"#EXTINF:-1,Snapshot [{cam.vendor or 'Unknown'}] {cam.ip}")
            lines.append(cam.http_snapshot_url)
            lines.append("")
            count += 1

    with p.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(p)
