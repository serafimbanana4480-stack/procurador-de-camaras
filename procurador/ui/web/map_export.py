"""
Mapa Folium com MarkerCluster e HeatMap.

Gera um mapa interativo com as câmaras encontradas.
"""

from __future__ import annotations

import logging

from procurador.core.models import CameraStatus, ScanResult

logger = logging.getLogger(__name__)


def generate_map_html(result: ScanResult) -> str:
    """Gera HTML do mapa Folium.

    Args:
        result: ScanResult.

    Returns:
        HTML string com o mapa embed.
    """
    try:
        import folium
        from folium.plugins import HeatMap, MarkerCluster
    except ImportError:
        return "<p>folium não instalado</p>"

    # Câmaras com coordenadas
    cams_with_geo = [c for c in result.cameras if c.geo.lat is not None and c.geo.lon is not None]

    if not cams_with_geo:
        # Mapa vazio centrado no mundo
        m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter")
        return _wrap_html(m, "0 câmaras com geolocalização")

    # Centro do mapa
    center_lat = sum(c.geo.lat for c in cams_with_geo) / len(cams_with_geo)
    center_lon = sum(c.geo.lon for c in cams_with_geo) / len(cams_with_geo)

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=2,
        tiles="CartoDB dark_matter",
    )

    # Marker cluster
    cluster = MarkerCluster().add_to(m)
    color_map = {
        CameraStatus.LIVE: "green",
        CameraStatus.AUTH_REQUIRED: "orange",
        CameraStatus.WEB_ONLY: "purple",
        CameraStatus.CLOSED: "gray",
        CameraStatus.ERROR: "red",
    }
    icon_map = {
        CameraStatus.LIVE: "ok-sign",
        CameraStatus.AUTH_REQUIRED: "lock",
        CameraStatus.WEB_ONLY: "globe",
        CameraStatus.CLOSED: "minus-sign",
        CameraStatus.ERROR: "exclamation-sign",
    }

    for cam in cams_with_geo:
        # Popup com info
        popup_html = f"""
        <b>{cam.ip}:{cam.port}</b><br>
        <b>Vendor:</b> {cam.vendor or "?"}<br>
        <b>Status:</b> {cam.status.value}<br>
        <b>País:</b> {cam.geo.country or "?"} ({cam.geo.country_code or "?"})<br>
        <b>Cidade:</b> {cam.geo.city or "?"}<br>
        <b>Auth:</b> {cam.auth_user or "—"}<br>
        <b>Método:</b> {cam.access_method.value if cam.access_method else "—"}
        """
        if cam.rtsp_url:
            popup_html += f"<br><b>RTSP:</b> <code>{cam.rtsp_url[:60]}</code>"

        folium.Marker(
            location=[cam.geo.lat, cam.geo.lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{cam.ip} ({cam.status.value})",
            icon=folium.Icon(
                color=color_map.get(cam.status, "blue"),
                icon=icon_map.get(cam.status, "info-sign"),
            ),
        ).add_to(cluster)

    # HeatMap
    heat_data = [[c.geo.lat, c.geo.lon] for c in cams_with_geo]
    HeatMap(heat_data, radius=15).add_to(m)

    return _wrap_html(m, f"{len(cams_with_geo)} câmaras com geolocalização")


def _wrap_html(m, info: str) -> str:
    """Wrap do mapa num HTML completo."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Procurador — Mapa</title>
<style>body {{ margin: 0; padding: 0; }} .info {{ position: fixed; top: 10px; right: 10px; background: rgba(0,0,0,0.7); color: #fff; padding: 8px 12px; border-radius: 4px; z-index: 1000; font-family: monospace; }}</style>
</head>
<body>
<div class="info">🦾 {info}</div>
{m.get_root().render()}
</body>
</html>"""
