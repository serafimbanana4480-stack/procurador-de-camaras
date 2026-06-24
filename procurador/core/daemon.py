"""
Modo daemon do Procurador de Câmara.

Corre scans periódicos em background, guarda resultados em SQLite,
e envia alertas quando descobre câmaras novas ou LIVE.

Uso:
    python -m procurador --daemon --interval 3600 --country PT
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Event

from procurador.config import get_censys_credentials, load_config
from procurador.core.alerts import Alert, AlertManager
from procurador.core.database import Database
from procurador.core.geoip import GeoIPResolver
from procurador.core.models import (
    Camera,
    CameraStatus,
    ScanConfig,
    ScanResult,
    SourceType,
)
from procurador.core.scanner import scan_camera_basic
from procurador.sources.censys import search_censys
from procurador.utils.logger import get_logger

logger = get_logger(__name__)


class Daemon:
    """Runner de scans periódicos com persistência e alertas."""

    def __init__(
        self,
        config: ScanConfig,
        interval: int = 3600,
        db_path: str = "data/procurador.db",
        telegram_token: str | None = None,
        telegram_chat_id: str | None = None,
        discord_webhook: str | None = None,
        max_workers: int = 50,
    ):
        self.config = config
        self.interval = interval
        self.db = Database(db_path)
        self.alerts = AlertManager(telegram_token, telegram_chat_id, discord_webhook)
        self.max_workers = max_workers
        self._stop_event = Event()
        self._scan_count = 0

        # GeoIP resolver (com cache SQLite)
        self.geoip = GeoIPResolver(db=self.db) if config.geoip_enabled else None

        # Signals para graceful shutdown
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame) -> None:
        """Handler de signals para paragem graciosa."""
        logger.info(f"📥 Recebido sinal {signum}, a parar...")
        self.stop()

    def stop(self) -> None:
        """Parar o daemon."""
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        """Daemon está a correr."""
        return not self._stop_event.is_set()

    def run_once(self) -> ScanResult:
        """Executar um ciclo de scan completo."""
        scan_id = str(uuid.uuid4())[:8]
        started = time.time()
        logger.info(f"🚀 Ciclo #{self._scan_count + 1} (id={scan_id})")

        # Inserir scan na BD
        scan_rowid = self.db.save_scan(scan_id, started, self.config)

        # Descobrir câmaras
        cameras = self._discover_cameras()

        if not cameras:
            logger.info("Nenhuma câmara encontrada neste ciclo")
            result = ScanResult(scan_id=scan_id, config=self.config)
            result.started_at = started
            result.finished_at = time.time()
            self.db.finish_scan(scan_id, result)
            return result

        # Escanear
        logger.info(f"🔎 A scanear {len(cameras)} câmaras...")
        completed = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(self._scan_one, cam): cam for cam in cameras}
            for fut in futures:
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"Erro scan: {e}")
                completed += 1
                if completed % 20 == 0:
                    logger.info(f"   progresso: {completed}/{len(cameras)}")

        finished = time.time()

        # Calcular resultados
        result = ScanResult(
            scan_id=scan_id,
            config=self.config,
            started_at=started,
            finished_at=finished,
            cameras=cameras,
        )
        result.calculate_stats()

        # Guardar na BD
        self._save_results(result)
        self.db.finish_scan(scan_id, result)

        # Alertas
        self._check_alerts(result)

        # Guardar JSON também
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / f"scan_{scan_id}_{int(started)}.json"
        try:
            result.to_json(str(json_path))
            logger.info(f"💾 Resultados: {json_path}")
        except Exception as e:
            logger.error(f"Erro ao guardar JSON: {e}")

        self._scan_count += 1
        return result

    def run_forever(self) -> None:
        """Correr daemon em loop infinito."""
        logger.info(f"🔄 Daemon iniciado (intervalo={self.interval}s)")
        logger.info(f"   Alertas: {'✅' if self.alerts.is_configured else '❌'}")

        if self.alerts.is_configured:
            self.alerts.send(Alert(
                camera_ip="system",
                scan_id="",
                alert_type="status_change",
                message=f"Daemon iniciado — intervalo={self.interval}s",
            ))

        while self.is_running:
            try:
                result = self.run_once()
                self._log_summary(result)
            except Exception as e:
                logger.error(f"❌ Erro no ciclo: {e}", exc_info=True)

            # Esperar pelo próximo ciclo (ou ser interrompido)
            if self.is_running:
                logger.info(f"💤 A esperar {self.interval}s até ao próximo ciclo...")
                self._stop_event.wait(self.interval)

        logger.info("🛑 Daemon parado")

    # ── Métodos internos ──────────────────────────────────────────

    def _discover_cameras(self) -> list[Camera]:
        """Descobrir câmaras (Censys + local)."""
        cameras: list[Camera] = []

        # Censys
        if self.config.censys_enabled:
            api_id, api_secret = get_censys_credentials()
            if api_id:
                for cam in search_censys(self.config, api_id, api_secret):
                    cameras.append(cam)
            else:
                logger.warning("Censys desativado (falta API key)")

        # Local
        if self.config.local_enabled:
            try:
                from procurador.sources.local import scan_local_network
                local_cams = scan_local_network(
                    self.config.local_subnet,
                    onvif=self.config.onvif_enabled,
                )
                cameras.extend(local_cams)
            except Exception as e:
                logger.error(f"Erro scan local: {e}")

        return cameras

    def _scan_one(self, camera: Camera) -> Camera:
        """Pipeline completo de scan para uma câmara."""
        try:
            scan_camera_basic(camera, self.config)

            if camera.status in (CameraStatus.AUTH_REQUIRED, CameraStatus.PENDING):
                if self.config.brute_enabled:
                    from procurador.core.brute import brute_camera
                    brute_camera(
                        camera,
                        timeout=self.config.rtsp_probe_timeout,
                        max_attempts=self.config.brute_max_attempts,
                    )

            if self.config.onvif_enabled:
                from procurador.core.onvif import probe_onvif
                probe_onvif(
                    camera,
                    user=self.config.onvif_default_user,
                    password=self.config.onvif_default_pass,
                    timeout=self.config.onvif_timeout,
                )

            if self.config.cve_enabled:
                from procurador.core.cve import try_cve_exploit
                try_cve_exploit(camera)

            # GeoIP
            if self.geoip is not None and camera.geo.country_code is None:
                try:
                    geo = self.geoip.resolve(camera.ip)
                    if geo and geo.country_code:
                        camera.geo = geo
                except Exception as e:
                    logger.debug(f"geoip err {camera.ip}: {e}")

            # Estado final
            if camera.status == CameraStatus.SCANNING:
                camera.status = CameraStatus.CLOSED
            if camera.status == CameraStatus.PENDING:
                camera.status = CameraStatus.CLOSED

        except Exception as e:
            logger.error(f"Erro scan {camera.ip}: {e}")
            camera.status = CameraStatus.ERROR
            camera.error_message = str(e)

        return camera

    def _save_results(self, result: ScanResult) -> None:
        """Guardar câmaras na BD."""
        for cam in result.cameras:
            try:
                self.db.save_camera(cam)
            except Exception as e:
                logger.debug(f"Erro ao guardar {cam.ip}: {e}")

    def _check_alerts(self, result: ScanResult) -> None:
        """Verificar e enviar alertas."""
        if not self.alerts.is_configured:
            return

        alerts_to_send: list[Alert] = []

        for cam in result.cameras:
            if cam.status == CameraStatus.LIVE:
                # Verificar se é nova ou já existia
                existing = self.db.get_camera(cam.ip, cam.port)
                if existing is None:
                    # Câmara nova e LIVE → alerta prioritário
                    alerts_to_send.append(Alert(
                        camera_ip=cam.ip,
                        scan_id=result.scan_id,
                        alert_type="new_live",
                        message=f"Câmara LIVE descoberta! {cam.vendor or 'desconhecida'} em {cam.ip}:{cam.port}",
                        metadata={
                            "vendor": cam.vendor or "",
                            "country": cam.geo.country or "",
                            "rtsp_url": cam.rtsp_url or "",
                        },
                    ))
                else:
                    # Já existia, mas ainda assim LIVE
                    if existing.get("status") != "live":
                        alerts_to_send.append(Alert(
                            camera_ip=cam.ip,
                            scan_id=result.scan_id,
                            alert_type="status_change",
                            message=f"Câmara agora LIVE: {cam.vendor or 'desconhecida'} em {cam.ip}:{cam.port}",
                            metadata={
                                "vendor": cam.vendor or "",
                                "country": cam.geo.country or "",
                            },
                        ))

        if alerts_to_send:
            sent = self.alerts.send_batch(alerts_to_send)
            logger.info(f"🔔 {sent}/{len(alerts_to_send)} alertas enviados")

    def _log_summary(self, result: ScanResult) -> None:
        """Log do sumário do scan."""
        logger.info(
            f"📊 Ciclo completo: "
            f"🟢{result.accessible} 🟡{result.auth_required} "
            f"🌐{result.web_only} ⚫{result.closed} ⚠️{result.errors} "
            f"| {len(result.cameras)} IPs em {(result.finished_at or result.started_at) - result.started_at:.1f}s"
        )
