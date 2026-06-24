"""
Export HTML — relatório standalone com screenshots e stats.

Usa Tailwind via CDN para styling moderno. Abre diretamente no browser.
"""

from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path
from typing import Any

from procurador.core.models import ScanResult

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Procurador de Câmara — Relatório {scan_id}</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body {{ background: #0a0a0a; color: #e5e5e5; font-family: 'Segoe UI', monospace; }}
  .card {{ background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 1rem; }}
  .status-live {{ color: #22c55e; font-weight: bold; }}
  .status-auth {{ color: #eab308; font-weight: bold; }}
  .status-closed {{ color: #6b7280; }}
  .status-error {{ color: #ef4444; font-weight: bold; }}
  .status-web {{ color: #d946ef; font-weight: bold; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #1f2937; color: #06b6d4; padding: 8px; text-align: left; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #333; }}
  tr:hover {{ background: #1f2937; }}
  a {{ color: #06b6d4; }}
  .screenshot {{ max-width: 320px; max-height: 240px; border: 1px solid #333; border-radius: 4px; }}
  code {{ background: #1f2937; padding: 2px 6px; border-radius: 4px; }}
  pre {{ background: #0a0a0a; padding: 8px; border-radius: 4px; overflow-x: auto; }}
  .bar {{ background: #06b6d4; height: 8px; border-radius: 4px; }}
  .bar-bg {{ background: #333; border-radius: 4px; overflow: hidden; height: 8px; }}
</style>
</head>
<body class="p-6">

<header class="mb-6">
  <h1 class="text-3xl font-bold text-cyan-400">🦾 Procurador de Câmara</h1>
  <p class="text-gray-400">Relatório do scan <code>{scan_id}</code> &middot; {started} &middot; Duração: {duration}s</p>
</header>

<section class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
  <div class="card"><div class="text-2xl font-bold text-cyan-400">{total_ips}</div><div class="text-gray-400">Total IPs</div></div>
  <div class="card"><div class="text-2xl font-bold text-green-500">{accessible}</div><div class="text-gray-400">🟢 LIVE</div></div>
  <div class="card"><div class="text-2xl font-bold text-yellow-500">{auth_required}</div><div class="text-gray-400">🟡 AUTH</div></div>
  <div class="card"><div class="text-2xl font-bold text-fuchsia-500">{web_only}</div><div class="text-gray-400">🌐 WEB</div></div>
  <div class="card"><div class="text-2xl font-bold text-red-500">{auth_failed}</div><div class="text-gray-400">🔴 FAIL</div></div>
  <div class="card"><div class="text-2xl font-bold text-gray-500">{closed}</div><div class="text-gray-400">⚫ CLOSED</div></div>
  <div class="card"><div class="text-2xl font-bold text-red-500">{errors}</div><div class="text-gray-400">⚠️ ERROS</div></div>
  <div class="card"><div class="text-2xl font-bold text-magenta-400">{live_streams}</div><div class="text-gray-400">📺 Streams</div></div>
</section>

<section class="grid md:grid-cols-2 gap-4 mb-6">
  <div class="card">
    <h2 class="text-xl font-bold mb-2 text-cyan-400">🏭 Top Fabricantes</h2>
    {vendors_html}
  </div>
  <div class="card">
    <h2 class="text-xl font-bold mb-2 text-cyan-400">🌍 Top Países</h2>
    {countries_html}
  </div>
</section>

<section class="card mb-6">
  <h2 class="text-xl font-bold mb-4 text-cyan-400">📷 Câmaras ({cameras_count} total, {live_cameras_count} LIVE)</h2>
  <div class="overflow-x-auto">
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>IP:Porta</th>
        <th>Vendor</th>
        <th>País</th>
        <th>Cidade</th>
        <th>Resolução</th>
        <th>Auth</th>
        <th>Método</th>
        <th>ONVIF</th>
        <th>CVE</th>
        <th>Screenshot</th>
      </tr>
    </thead>
    <tbody>
      {cameras_html}
    </tbody>
  </table>
  </div>
</section>

<footer class="text-center text-gray-600 text-sm mt-8">
  <p>Gerado por Procurador de Câmara v1.0 · {exported_at}</p>
  <p>⚠️ Aviso legal: usar apenas em redes e dispositivos com autorização.</p>
</footer>

</body>
</html>
"""


def _bar(item: tuple[str, int], max_v: int) -> str:
    """Renderiza uma barra de progresso HTML."""
    label, count = item
    pct = (count / max_v) * 100 if max_v > 0 else 0
    return f"""
<div class="mb-1">
  <div class="flex justify-between text-sm">
    <span>{html.escape(str(label))}</span>
    <span class="text-cyan-400">{count}</span>
  </div>
  <div class="bar-bg"><div class="bar" style="width: {pct:.0f}%;"></div></div>
</div>
"""


def _camera_row(cam_dict: dict[str, Any], screenshot_data: str | None) -> str:
    """Renderiza uma linha da tabela de câmaras."""
    status = cam_dict.get("status", "closed")
    status_class = {
        "live": "status-live",
        "auth": "status-auth",
        "closed": "status-closed",
        "error": "status-error",
        "web": "status-web",
    }.get(status, "")
    status_icon = {
        "live": "🟢",
        "auth": "🟡",
        "closed": "⚫",
        "error": "⚠️",
        "web": "🌐",
    }.get(status, "?")

    auth = "—"
    if cam_dict.get("auth_user"):
        auth = f"{cam_dict['auth_user']}:{cam_dict.get('auth_pass', '')}"[:20]
    elif cam_dict.get("access_method") == "rtsp_no_auth":
        auth = "no-auth"

    cve = cam_dict.get("cve_exploited") or ""
    onvif = "✓" if cam_dict.get("onvif_supported") else ""

    # Screenshot: tag <img> com data URI base64 ou path
    img_tag = ""
    if screenshot_data:
        img_tag = f'<img class="screenshot" src="data:image/jpeg;base64,{screenshot_data}" alt="screenshot">'
    else:
        img_tag = '<span class="text-gray-600">—</span>'

    return f"""
<tr>
  <td class="{status_class}">{status_icon}</td>
  <td><code>{html.escape(f"{cam_dict.get('ip', '')}:{cam_dict.get('port', '')}")}</code></td>
  <td>{html.escape(str(cam_dict.get("vendor") or "—"))}</td>
  <td>{html.escape(str(cam_dict.get("geo", {}).get("country") or "—"))}</td>
  <td>{html.escape(str(cam_dict.get("geo", {}).get("city") or "—"))}</td>
  <td>{html.escape(str(cam_dict.get("resolution") or "N/A"))}</td>
  <td><code>{html.escape(auth)}</code></td>
  <td>{html.escape(str(cam_dict.get("access_method") or "—"))}</td>
  <td>{onvif}</td>
  <td><code>{html.escape(cve)}</code></td>
  <td>{img_tag}</td>
</tr>
"""


def _load_screenshot_b64(path: str | None) -> str | None:
    """Carrega screenshot como base64 (ou None)."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        with p.open("rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None


def export_html(
    result: ScanResult,
    output_path: str,
    include_screenshots: bool = True,
    include_all: bool = False,
) -> str:
    """Exporta relatório HTML.

    Args:
        result: ScanResult.
        output_path: Caminho de output.
        include_screenshots: Se True, embute screenshots como base64.
        include_all: Se True, inclui câmaras não-acessiveis.

    Returns:
        Caminho escrito.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Stats
    stats = {
        "total_ips": result.total_ips,
        "accessible": result.accessible,
        "auth_required": result.auth_required,
        "web_only": result.web_only,
        "auth_failed": result.auth_failed,
        "closed": result.closed,
        "errors": result.errors,
        "live_streams": result.live_streams,
    }

    started = (
        datetime.fromtimestamp(result.started_at).strftime("%Y-%m-%d %H:%M:%S")
        if result.started_at
        else "?"
    )
    duration = (
        f"{result.finished_at - result.started_at:.1f}"
        if result.finished_at and result.started_at
        else "?"
    )

    # Top vendors
    max_vendor = max(result.vendors.values()) if result.vendors else 1
    vendors_html = "".join(_bar(v, max_vendor) for v in list(result.vendors.items())[:10])
    if not vendors_html:
        vendors_html = "<p class='text-gray-500'>Sem dados</p>"

    # Top countries
    max_country = max(result.countries.values()) if result.countries else 1
    countries_html = "".join(_bar(c, max_country) for c in list(result.countries.items())[:10])
    if not countries_html:
        countries_html = "<p class='text-gray-500'>Sem dados</p>"

    # Cameras
    cameras = result.cameras
    if not include_all:
        cameras = [c for c in cameras if c.is_accessible]

    live_cams = [c for c in result.cameras if c.status.value == "live"]
    cam_dicts = [c.to_dict() for c in cameras]

    rows = []
    for cd in cam_dicts:
        ss = _load_screenshot_b64(cd.get("screenshot_path")) if include_screenshots else None
        rows.append(_camera_row(cd, ss))
    cameras_html = "".join(rows)
    if not cameras_html:
        cameras_html = (
            "<tr><td colspan='11' class='text-center text-gray-500'>Sem câmaras</td></tr>"
        )

    # Render
    html_content = HTML_TEMPLATE.format(
        scan_id=html.escape(result.scan_id),
        started=started,
        duration=duration,
        **stats,
        vendors_html=vendors_html,
        countries_html=countries_html,
        cameras_html=cameras_html,
        cameras_count=len(cameras),
        live_cameras_count=len(live_cams),
        exported_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    with p.open("w", encoding="utf-8") as f:
        f.write(html_content)

    return str(p)
