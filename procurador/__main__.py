"""
Procurador de Câmara — entry point CLI.

Uso:
    python -m procurador --country PT --pages 5
    python -m procurador --query "services.port:554" --tui
    python -m procurador --local --subnet 192.168.1.0/24
    python -m procurador --web --port 5000
    python -m procurador --tui --no-brute

Pipeline (por IP):
    Censys → RTSP no-auth → ONVIF → HTTP snap → HTTP admin → RTSP brute → alt ports → CVE
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Fix encoding for Windows terminals
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from procurador.config import get_censys_credentials, load_config, load_env

# Carregar .env antes de qualquer import que use variáveis de ambiente
load_env()

from procurador.core.brute import brute_camera
from procurador.core.cve import try_cve_exploit
from procurador.core.geoip import GeoIPResolver
from procurador.core.models import (
    Camera,
    CameraStatus,
    ScanConfig,
    ScanResult,
    SourceType,
)
from procurador.core.onvif import probe_onvif
from procurador.core.scanner import scan_camera_basic
from procurador.core.stream import capture_batch
from procurador.sources.censys import search_censys
from procurador.utils.logger import get_logger

logger = get_logger("procurador")


# =====================================================================
# CLI
# =====================================================================


def build_parser() -> argparse.ArgumentParser:
    """Constrói o parser de argumentos CLI."""
    p = argparse.ArgumentParser(
        prog="procurador",
        description="Procurador de Câmara — descoberta e auditoria de câmaras IP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Fontes
    p.add_argument(
        "--country", "-c", type=str, default="", help="País (código ISO 'PT' ou nome 'Portugal')"
    )
    p.add_argument(
        "--query",
        "-q",
        type=str,
        default="",
        help="Query Censys custom (default: services.service_name: RTSP)",
    )
    p.add_argument("--pages", type=int, default=5, help="Número de páginas Censys (default: 5)")
    p.add_argument(
        "--per-page", type=int, default=100, help="Resultados por página Censys (default: 100)"
    )

    # Local
    p.add_argument("--local", action="store_true", help="Ativar scan local (ARP + ONVIF)")
    p.add_argument(
        "--subnet",
        type=str,
        default="192.168.1.0/24",
        help="Sub-rede para scan local (default: 192.168.1.0/24)",
    )

    # Scan
    p.add_argument("--no-brute", action="store_true", help="Desativar brute force de credenciais")
    p.add_argument("--no-onvif", action="store_true", help="Desativar ONVIF discovery")
    p.add_argument("--no-cve", action="store_true", help="Desativar tentativas de CVE exploits")
    p.add_argument("--no-geoip", action="store_true", help="Desativar GeoIP")
    p.add_argument("--stream", action="store_true", help="Capturar screenshots dos streams LIVE")
    p.add_argument("--max-workers", type=int, default=50, help="Threads paralelas (default: 50)")
    p.add_argument("--timeout", type=float, default=3.0, help="Timeout por probe (default: 3s)")

    # UI
    p.add_argument("--tui", action="store_true", help="Abrir dashboard TUI (Rich) no fim")
    p.add_argument("--web", action="store_true", help="Abrir dashboard Web (Flask) no fim")
    p.add_argument("--port", type=int, default=5000, help="Porta do dashboard Web (default: 5000)")

    # Output
    p.add_argument("--no-save", action="store_true", help="Não guardar resultados em JSON")
    p.add_argument("--out", type=str, default="data", help="Diretório de output (default: data)")
    p.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nível de log (default: INFO)",
    )

    # Manual targets
    p.add_argument(
        "--target",
        "-t",
        action="append",
        default=[],
        help="IP manual para testar (repetível, formato IP ou IP:porta)",
    )

    # Daemon (Fase 3.5)
    p.add_argument("--daemon", action="store_true", help="Modo daemon (scans periódicos)")
    p.add_argument(
        "--interval", type=int, default=3600,
        help="Intervalo entre scans em segundos (default: 3600)",
    )
    p.add_argument(
        "--db", type=str, default="data/procurador.db",
        help="Caminho para base de dados SQLite (default: data/procurador.db)",
    )

    return p


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse argumentos CLI."""
    return build_parser().parse_args(argv)


# =====================================================================
# Pipeline helpers
# =====================================================================


def _discover_cameras(
    args: argparse.Namespace,
    config: ScanConfig,
) -> list[Camera]:
    """Descoberta: Censys + local + manual."""
    cameras: list[Camera] = []

    # 1. Censys
    if config.censys_enabled:
        api_id, api_secret = get_censys_credentials()
        if api_id:
            logger.info(
                f"🌐 Censys: query={config.censys_query!r} country={config.censys_country!r}"
            )
            for cam in search_censys(config, api_id, api_secret):
                cameras.append(cam)
        else:
            logger.warning("⚠️  Censys desativado (falta CENSYS_API_ID)")

    # 2. Local scan
    if args.local:
        try:
            from procurador.sources.local import scan_local_network

            local_cams = scan_local_network(args.subnet, onvif=not args.no_onvif)
            cameras.extend(local_cams)
        except ImportError:
            logger.warning("Scan local indisponível (módulo sources/local)")
        except Exception as e:
            logger.error(f"Erro scan local: {e}")

    # 3. Manual targets
    if args.target:
        from procurador.utils.helpers import parse_hostport

        for t in args.target:
            host, port = parse_hostport(t, default_port=554)
            cameras.append(
                Camera(
                    ip=host,
                    port=port,
                    source=SourceType.MANUAL,
                )
            )
            logger.info(f"➕ Target manual: {host}:{port}")

    # Deduplica por IP (manter primeiro)
    seen: set[str] = set()
    deduped: list[Camera] = []
    for c in cameras:
        if c.ip not in seen:
            seen.add(c.ip)
            deduped.append(c)

    logger.info(f"📋 {len(deduped)} câmaras únicas para scan")
    return deduped


def _scan_one(
    camera: Camera,
    config: ScanConfig,
    geoip: GeoIPResolver | None = None,
) -> Camera:
    """Pipeline completo de scan para uma câmara."""
    try:
        # 1. Probe básico (Técnicas 1, 3, 4, 6)
        scan_camera_basic(camera, config)

        # 2. ONVIF (Técnica 2)
        if not args_no_onvif(config):
            try:
                probe_onvif(
                    camera,
                    user=config.onvif_default_user,
                    password=config.onvif_default_pass,
                    timeout=config.onvif_timeout,
                )
            except Exception as e:
                logger.debug(f"onvif err {camera.ip}: {e}")

        # 3. Brute creds (Técnica 5)
        if config.brute_enabled and camera.status in (
            CameraStatus.AUTH_REQUIRED,
            CameraStatus.PENDING,
        ):
            try:
                brute_camera(
                    camera,
                    timeout=config.rtsp_probe_timeout,
                    max_attempts=config.brute_max_attempts,
                )
            except Exception as e:
                logger.debug(f"brute err {camera.ip}: {e}")

        # 4. CVE exploits (Técnica 7)
        if not args_no_cve(config):
            try:
                try_cve_exploit(camera)
            except Exception as e:
                logger.debug(f"cve err {camera.ip}: {e}")

        # 5. GeoIP
        if geoip is not None and not config.geoip_enabled:
            pass  # disabled
        elif geoip is not None and camera.geo.country_code is None:
            try:
                geo = geoip.resolve(camera.ip)
                if geo.country_code:
                    camera.geo = geo
            except Exception as e:
                logger.debug(f"geoip err {camera.ip}: {e}")

        # 6. Estado final
        if camera.status == CameraStatus.SCANNING:
            camera.status = CameraStatus.CLOSED
        if camera.status == CameraStatus.PENDING:
            camera.status = CameraStatus.CLOSED

        # Log resumo
        if camera.status == CameraStatus.LIVE:
            method = camera.access_method.value
            logger.info(f"🟢 {camera.ip}:{camera.port} LIVE via {method}")
        elif camera.status == CameraStatus.AUTH_REQUIRED:
            logger.info(f"🟡 {camera.ip}:{camera.port} AUTH")
        elif camera.status == CameraStatus.WEB_ONLY:
            logger.info(f"🌐 {camera.ip} WEB_ONLY")
        else:
            logger.debug(f"⚫ {camera.ip}:{camera.port} {camera.status.value}")

    except Exception as e:
        logger.error(f"Erro scan {camera.ip}: {e}")
        camera.status = CameraStatus.ERROR
        camera.error_message = str(e)

    return camera


def args_no_onvif(config: ScanConfig) -> bool:
    """Helper: verifica se ONVIF está desativado (hack para closures)."""
    return not config.onvif_enabled


def args_no_cve(config: ScanConfig) -> bool:
    """Helper: verifica se CVE está desativado (hack para closures)."""
    return not config.cve_enabled


def _scan_batch(
    cameras: list[Camera],
    config: ScanConfig,
    geoip: GeoIPResolver | None,
    max_workers: int,
) -> list[Camera]:
    """Scan paralelo de N câmaras."""
    if not cameras:
        return []

    logger.info(f"🔎 A scanear {len(cameras)} câmaras ({max_workers} threads)...")

    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_scan_one, cam, config, geoip): cam for cam in cameras}
        for fut in as_completed(futures):
            cam = futures[fut]
            try:
                fut.result()
            except Exception as e:
                logger.error(f"Future err {cam.ip}: {e}")
                cam.status = CameraStatus.ERROR
                cam.error_message = str(e)
            completed += 1
            if completed % 20 == 0 or completed == len(cameras):
                logger.info(f"   progresso: {completed}/{len(cameras)}")

    return cameras


# =====================================================================
# Main
# =====================================================================


def main(argv: list[str] | None = None) -> int:
    """Entry point principal."""
    args = parse_args(argv)

    # Configurar logging
    os.environ["PROCURADOR_LOG_LEVEL"] = args.log_level
    global logger
    logger = get_logger("procurador")

    # Carregar config
    config = load_config()
    # Override com CLI
    if args.country:
        config.censys_country = args.country
    if args.query:
        config.censys_query = args.query
    if args.pages:
        config.censys_max_pages = args.pages
    if args.per_page:
        config.censys_per_page = args.per_page
    if args.timeout:
        config.rtsp_probe_timeout = args.timeout
    if args.no_brute:
        config.brute_enabled = False
    if args.no_onvif:
        config.onvif_enabled = False
    if args.no_cve:
        config.cve_enabled = False
    if args.no_geoip:
        config.geoip_enabled = False
    if args.stream:
        config.stream_capture = True
    if args.subnet:
        config.local_subnet = args.subnet
    if args.local:
        config.local_enabled = True

    config.output_dir = args.out
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    # ── Modo Daemon ──────────────────────────────────────────────
    if args.daemon:
        from procurador.core.daemon import Daemon

        daemon = Daemon(
            config=config,
            interval=args.interval,
            db_path=args.db,
            max_workers=args.max_workers,
        )

        if daemon.alerts.is_configured:
            logger.info("🔔 Alertas configurados (Telegram/Discord)")
        else:
            logger.info("🔕 Alertas não configurados (set TELEGRAM_BOT_TOKEN ou DISCORD_WEBHOOK no .env)")

        try:
            daemon.run_forever()
        except KeyboardInterrupt:
            logger.info("👋 Daemon interrompido pelo utilizador")
            daemon.stop()

        return 0

    # ── Modo normal ──────────────────────────────────────────────
    # Banner
    print_banner()

    # GeoIP resolver
    geoip: GeoIPResolver | None = None
    if config.geoip_enabled:
        geoip = GeoIPResolver()

    # Scan
    scan_id = str(uuid.uuid4())[:8]
    started = time.time()
    logger.info(f"🚀 Scan iniciado (id={scan_id})")

    cameras = _discover_cameras(args, config)

    # Atualizar referências das funções helper com a config do CLI
    global args_no_onvif, args_no_cve
    args_no_onvif = lambda c: not c.onvif_enabled  # noqa: E731
    args_no_cve = lambda c: not c.cve_enabled  # noqa: E731

    cameras = _scan_batch(cameras, config, geoip, max_workers=args.max_workers)

    # Stream capture (opcional)
    if config.stream_capture:
        logger.info("📸 Captura de streams...")
        capture_batch(cameras, screenshot_dir=f"{config.output_dir}/screenshots", max_workers=4)

    finished = time.time()

    # Calcular stats
    result = ScanResult(
        scan_id=scan_id,
        config=config,
        started_at=started,
        finished_at=finished,
        cameras=cameras,
    )
    result.calculate_stats()

    # Guardar na BD SQLite também
    if not args.no_save:
        try:
            from procurador.core.database import Database
            db = Database(args.db if hasattr(args, 'db') else "data/procurador.db")
            db.save_scan(scan_id, started, config)
            for cam in cameras:
                db.save_camera(cam)
            db.finish_scan(scan_id, result)
            logger.info(f"💾 Resultados guardados em SQLite: {args.db if hasattr(args, 'db') else 'data/procurador.db'}")
        except Exception as e:
            logger.debug(f"SQLite save: {e}")

    # Guardar JSON
    if not args.no_save:
        out_path = Path(config.output_dir) / f"scan_{scan_id}_{int(started)}.json"
        try:
            result.to_json(str(out_path))
            logger.info(f"💾 Resultados guardados em: {out_path}")
        except Exception as e:
            logger.error(f"Erro a guardar JSON: {e}")

    # Sumário
    print_summary(result)

    # UI
    if args.tui:
        try:
            from procurador.ui.tui import run_tui

            run_tui(result)
        except ImportError as e:
            logger.error(f"TUI não disponível: {e}")
        except Exception as e:
            logger.error(f"Erro TUI: {e}")
    elif args.web:
        try:
            from procurador.ui.web.app import run_web

            run_web(result, port=args.port)
        except ImportError as e:
            logger.error(f"Web não disponível: {e}")
        except Exception as e:
            logger.error(f"Erro Web: {e}")

    return 0


def print_banner() -> None:
    """Imprime o banner do Procurador."""
    print()
    print("=" * 60)
    print("  🦾 PROCURADOR DE CÂMARA v1.0")
    print("  Descoberta e auditoria de câmaras IP")
    print("=" * 60)
    print()


def print_summary(result: ScanResult) -> None:
    """Imprime sumário final do scan."""
    print()
    print("=" * 60)
    print("  📊 SUMÁRIO DO SCAN")
    print("=" * 60)
    print(f"  Scan ID:    {result.scan_id}")
    elapsed = result.finished_at - result.started_at if result.finished_at else 0
    print(f"  Duração:    {elapsed:.1f}s")
    print(f"  Total IPs:  {result.total_ips}")
    print(f"  🟢 LIVE:    {result.accessible}")
    print(f"  🟡 AUTH:    {result.auth_required}")
    print(f"  🌐 WEB:     {result.web_only}")
    print(f"  🔴 FAIL:    {result.auth_failed}")
    print(f"  ⚫ CLOSED:  {result.closed}")
    print(f"  ⚠️  ERROS:  {result.errors}")
    print()
    if result.vendors:
        print("  Top fabricantes:")
        for v, n in list(result.vendors.items())[:5]:
            print(f"    {v:20s} {n}")
    if result.countries:
        print("  Top países:")
        for c, n in list(result.countries.items())[:5]:
            print(f"    {c:20s} {n}")
    if result.access_methods:
        print("  Métodos de acesso:")
        for m, n in result.access_methods.items():
            print(f"    {m:20s} {n}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    sys.exit(main())
