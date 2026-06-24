"""
Web dashboard Flask do Procurador de Câmara.

Rotas:
- /              — Dashboard principal
- /api/cameras   — JSON com todas as câmaras
- /api/stats     — JSON com stats
- /api/vendors   — JSON com contagem por fabricante
- /camera/<ip>   — Detalhe de uma câmara
- /map           — Mapa Folium
- /export/<fmt>  — Download de export (json, csv, html, m3u)
- /screenshot/<ip> — Imagem screenshot (path traversal-safe)
"""

from __future__ import annotations

import logging
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    render_template,
    send_file,
)

from procurador.core.models import ScanResult
from procurador.export.csv_export import export_csv
from procurador.export.html_report import export_html
from procurador.export.json_export import export_json
from procurador.export.m3u import export_m3u

logger = logging.getLogger(__name__)


# =====================================================================
# App factory
# =====================================================================


def create_app(scan_result: ScanResult | None = None) -> Flask:
    """Cria a aplicação Flask.

    Args:
        scan_result: ScanResult a mostrar. Se None, tenta carregar do último JSON em data/.

    Returns:
        Flask app.
    """
    # Localizar templates — funciona tanto em dev como em pacote
    template_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir) if static_dir.exists() else None,
    )

    # Carregar ScanResult
    if scan_result is None:
        scan_result = _load_latest_scan(data_dir="data")
    app.config["scan_result"] = scan_result
    app.config["scan_result_dict"] = scan_result.to_dict() if scan_result else None

    # Registas routes
    _register_routes(app)

    return app


def _load_latest_scan(data_dir: str = "data") -> ScanResult | None:
    """Carrega o scan JSON mais recente do diretório data/."""
    p = Path(data_dir)
    if not p.exists():
        return None
    scans = sorted(p.glob("scan_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not scans:
        return None
    try:
        import json

        with scans[0].open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Reconstruir ScanResult mínimo
        from procurador.core.models import ScanConfig

        cfg_dict = data.get("config", {})
        cfg = ScanConfig(
            **{k: v for k, v in cfg_dict.items() if k in ScanConfig.__dataclass_fields__}
        )
        return ScanResult(
            scan_id=data.get("scan_id", "unknown"),
            config=cfg,
            cameras=[],  # Não reconstruímos câmaras (lazy)
        )
    except Exception as e:
        logger.warning(f"Erro a carregar scan mais recente: {e}")
        return None


# =====================================================================
# Routes
# =====================================================================


def _register_routes(app: Flask) -> None:

    @app.route("/")
    def index() -> str:
        """Dashboard principal."""
        sr = app.config.get("scan_result")
        return render_template(
            "dashboard.html",
            result=sr,
            result_dict=app.config.get("scan_result_dict") or {},
        )

    @app.route("/api/cameras")
    def api_cameras() -> Response:
        """JSON com lista de câmaras."""
        sr = app.config.get("scan_result")
        if sr is None:
            return jsonify({"cameras": [], "total": 0})
        cams = [c.to_dict() for c in sr.cameras]
        return jsonify({"cameras": cams, "total": len(cams)})

    @app.route("/api/stats")
    def api_stats() -> Response:
        """JSON com stats."""
        sr = app.config.get("scan_result")
        if sr is None:
            return jsonify({})
        if not sr.cameras:
            sr.calculate_stats()
        return jsonify(
            {
                "total_ips": sr.total_ips,
                "accessible": sr.accessible,
                "auth_required": sr.auth_required,
                "web_only": sr.web_only,
                "auth_failed": sr.auth_failed,
                "closed": sr.closed,
                "errors": sr.errors,
                "live_streams": sr.live_streams,
                "vendors": sr.vendors,
                "countries": sr.countries,
                "access_methods": sr.access_methods,
            }
        )

    @app.route("/camera/<ip>")
    def camera_detail(ip: str) -> str:
        """Página de detalhe de uma câmara."""
        sr = app.config.get("scan_result")
        if sr is None:
            abort(404)
        cam = next((c for c in sr.cameras if c.ip == ip), None)
        if cam is None:
            abort(404)
        return render_template("camera_detail.html", cam=cam.to_dict())

    @app.route("/screenshot/<ip>")
    def screenshot(ip: str) -> Response:
        """Serve o screenshot de uma câmara (path traversal safe)."""
        sr = app.config.get("scan_result")
        if sr is None:
            abort(404)
        cam = next((c for c in sr.cameras if c.ip == ip), None)
        if cam is None or not cam.screenshot_path:
            abort(404)

        # Validar que o path está dentro de data/screenshots
        workspace_root = Path(__file__).resolve().parent.parent.parent.parent
        sp = Path(cam.screenshot_path).resolve()
        screenshot_root = (workspace_root / "data" / "screenshots").resolve()
        try:
            sp.relative_to(screenshot_root)
        except ValueError:
            logger.warning(f"Path traversal attempt: {sp}")
            abort(403)

        if not sp.exists():
            abort(404)
        return send_file(str(sp), mimetype="image/jpeg")

    @app.route("/map")
    def map_view() -> str:
        """Mapa Folium."""
        from procurador.ui.web.map_export import generate_map_html

        sr = app.config.get("scan_result")
        if sr is None:
            html_content = "<p>Sem dados</p>"
        else:
            html_content = generate_map_html(sr)
        return html_content

    @app.route("/export/<fmt>")
    def export(fmt: str) -> Response:
        """Download de export. Formatos: json, csv, html, m3u."""
        sr = app.config.get("scan_result")
        if sr is None:
            abort(404)

        # Usar path absoluto baseado no workspace
        workspace_root = Path(__file__).resolve().parent.parent.parent.parent
        out_dir = workspace_root / "data" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        path: Path | None = None

        if fmt == "json":
            path = Path(export_json(sr, str(out_dir / "export.json"), include_all=True))
        elif fmt == "csv":
            path = Path(export_csv(sr, str(out_dir / "export.csv"), include_all=True))
        elif fmt == "html":
            path = Path(export_html(sr, str(out_dir / "export.html"), include_screenshots=False))
        elif fmt == "m3u":
            path = Path(export_m3u(sr, str(out_dir / "export.m3u"), include_web=True))
        else:
            abort(404)

        try:
            return send_file(str(path), as_attachment=True, download_name=path.name)
        except Exception as e:
            logger.error(f"Erro export {fmt}: {e}")
            abort(500)


# =====================================================================
# Run
# =====================================================================


def run_web(
    result: ScanResult,
    host: str = "127.0.0.1",
    port: int = 5000,
    debug: bool = False,
) -> None:
    """Inicia o servidor web.

    Args:
        result: ScanResult.
        host: Host para bind.
        port: Porta.
        debug: Modo debug.
    """
    import webbrowser

    app = create_app(result)
    url = f"http://{host}:{port}"
    logger.info(f"🌐 Web dashboard: {url}")
    print(f"\n  🌐 Dashboard Web disponível em: {url}\n")
    if not debug:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    app.run(host=host, port=port, debug=debug, use_reloader=False)
