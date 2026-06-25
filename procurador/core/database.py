"""
Persistência SQLite para o Procurador de Câmara.

Armazena câmaras, histórico de scans, e alertas.
Suporta cache de GeoIP e wordlists.

Schema:
  - cameras      — tabela principal de dispositivos
  - scans        — histórico de execuções
  - alerts       — notificações pendentes
  - geoip_cache  — cache de geolocalização
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from procurador.core.models import (
    Camera,
    ScanConfig,
    ScanResult,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/procurador.db"


# =====================================================================
# Schema SQL
# =====================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cameras (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ip              TEXT NOT NULL,
    port            INTEGER NOT NULL DEFAULT 554,
    source          TEXT NOT NULL DEFAULT 'censys',
    first_seen      REAL NOT NULL DEFAULT (julianday('now') * 86400),
    last_seen       REAL NOT NULL DEFAULT (julianday('now') * 86400),
    scan_count      INTEGER NOT NULL DEFAULT 1,
    vendor          TEXT,
    model           TEXT,
    firmware        TEXT,
    mac_address     TEXT,
    hostname        TEXT,
    ports_open      TEXT,
    rtsp_path       TEXT,
    rtsp_url        TEXT,
    http_status     INTEGER,
    http_title      TEXT,
    http_server     TEXT,
    http_url        TEXT,
    onvif_supported INTEGER DEFAULT 0,
    onvif_url       TEXT,
    ptz_supported   INTEGER DEFAULT 0,
    auth_required   INTEGER DEFAULT 1,
    auth_success    INTEGER DEFAULT 0,
    auth_user       TEXT,
    auth_pass       TEXT,
    auth_method     TEXT,
    codec           TEXT,
    width           INTEGER DEFAULT 0,
    height          INTEGER DEFAULT 0,
    fps             REAL DEFAULT 0.0,
    screenshot_path TEXT,
    country         TEXT,
    country_code    TEXT,
    city            TEXT,
    region          TEXT,
    lat             REAL,
    lon             REAL,
    isp             TEXT,
    org             TEXT,
    asn             TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    access_method   TEXT DEFAULT 'unknown',
    error_message   TEXT,
    raw_banner      TEXT,
    tags            TEXT,
    json_data       TEXT,
    UNIQUE(ip, port)
);

CREATE TABLE IF NOT EXISTS scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         TEXT NOT NULL UNIQUE,
    started_at      REAL NOT NULL,
    finished_at     REAL,
    source          TEXT NOT NULL DEFAULT 'censys',
    query           TEXT,
    country         TEXT,
    total_ips       INTEGER DEFAULT 0,
    live_count      INTEGER DEFAULT 0,
    auth_count      INTEGER DEFAULT 0,
    closed_count    INTEGER DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    new_cameras     INTEGER DEFAULT 0,
    config_json     TEXT,
    duration_secs   REAL,
    created_at      REAL NOT NULL DEFAULT (julianday('now') * 86400)
);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_ip       TEXT NOT NULL,
    scan_id         TEXT,
    alert_type      TEXT NOT NULL,
    message         TEXT NOT NULL,
    sent            INTEGER DEFAULT 0,
    sent_at         REAL,
    created_at      REAL NOT NULL DEFAULT (julianday('now') * 86400)
);

CREATE TABLE IF NOT EXISTS geoip_cache (
    ip              TEXT PRIMARY KEY,
    country         TEXT,
    country_code    TEXT,
    city            TEXT,
    region          TEXT,
    lat             REAL,
    lon             REAL,
    isp             TEXT,
    org             TEXT,
    asn             TEXT,
    expires_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cameras_ip ON cameras(ip);
CREATE INDEX IF NOT EXISTS idx_cameras_status ON cameras(status);
CREATE INDEX IF NOT EXISTS idx_cameras_vendor ON cameras(vendor);
CREATE INDEX IF NOT EXISTS idx_cameras_country ON cameras(country_code);
CREATE INDEX IF NOT EXISTS idx_cameras_last_seen ON cameras(last_seen);
CREATE INDEX IF NOT EXISTS idx_scans_started ON scans(started_at);
CREATE INDEX IF NOT EXISTS idx_alerts_unsent ON alerts(sent, created_at);
CREATE INDEX IF NOT EXISTS idx_geoip_expires ON geoip_cache(expires_at);
"""


# =====================================================================
# Database
# =====================================================================


class Database:
    """Gerir base de dados SQLite do Procurador."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        """Criar tabelas se não existirem."""
        conn = self._get_conn()
        conn.executescript(SCHEMA_SQL)
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Câmaras ──────────────────────────────────────────────────────

    def save_camera(self, camera: Camera) -> int:
        """Inserir ou atualizar uma câmara. Devolve rowid."""
        conn = self._get_conn()
        now = time.time()

        # Verificar se já existe
        existing = conn.execute(
            "SELECT id, scan_count FROM cameras WHERE ip = ? AND port = ?",
            (camera.ip, camera.port),
        ).fetchone()

        data = {
            "ip": camera.ip,
            "port": camera.port,
            "source": camera.source.value,
            "last_seen": now,
            "vendor": camera.vendor,
            "model": camera.model,
            "firmware": camera.firmware,
            "mac_address": camera.mac_address,
            "ports_open": json.dumps(camera.ports_open) if camera.ports_open else None,
            "rtsp_path": camera.rtsp_path,
            "rtsp_url": camera.rtsp_url,
            "http_status": camera.http_status,
            "http_title": camera.http_title,
            "http_server": camera.http_server,
            "http_url": camera.http_url,
            "onvif_supported": 1 if camera.onvif_supported else 0,
            "onvif_url": camera.onvif_url,
            "ptz_supported": 1 if camera.ptz_supported else 0,
            "auth_required": 1 if camera.auth_required else 0,
            "auth_success": 1 if camera.auth_success else 0,
            "auth_user": camera.auth_user,
            "auth_pass": camera.auth_pass,
            "auth_method": camera.auth_method,
            "codec": camera.stream.codec if camera.stream else None,
            "width": camera.stream.width if camera.stream else 0,
            "height": camera.stream.height if camera.stream else 0,
            "fps": camera.stream.fps if camera.stream else 0.0,
            "screenshot_path": camera.screenshot_path,
            "country": camera.geo.country,
            "country_code": camera.geo.country_code,
            "city": camera.geo.city,
            "region": camera.geo.region,
            "lat": camera.geo.lat,
            "lon": camera.geo.lon,
            "isp": camera.network.isp,
            "org": camera.network.org,
            "asn": camera.network.asn,
            "status": camera.status.value,
            "access_method": camera.access_method.value,
            "error_message": camera.error_message,
            "raw_banner": camera.raw_banner,
            "tags": json.dumps(camera.tags) if camera.tags else None,
            "json_data": json.dumps(camera.to_dict(), default=str),
        }

        if existing:
            # Atualizar existente
            data["scan_count"] = existing["scan_count"] + 1
            set_clause = ", ".join(f"{k} = ?" for k in data)
            values = list(data.values()) + [camera.ip, camera.port]
            conn.execute(
                f"UPDATE cameras SET {set_clause} WHERE ip = ? AND port = ?",
                values,
            )
            return int(existing["id"])
        else:
            # Inserir nova
            data["first_seen"] = now
            data["scan_count"] = 1
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" for _ in data)
            cursor = conn.execute(
                f"INSERT INTO cameras ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def get_camera(self, ip: str, port: int = 554) -> dict | None:
        """Obter câmara por IP+porta."""
        row = self._get_conn().execute(
            "SELECT * FROM cameras WHERE ip = ? AND port = ?",
            (ip, port),
        ).fetchone()
        if row:
            return dict(row)
        return None

    def get_all_cameras(self, status: str | None = None, limit: int = 1000) -> list[dict]:
        """Listar câmaras, opcionalmente filtradas por status."""
        if status:
            rows = self._get_conn().execute(
                "SELECT * FROM cameras WHERE status = ? ORDER BY last_seen DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._get_conn().execute(
                "SELECT * FROM cameras ORDER BY last_seen DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_new_since(self, since: float) -> list[dict]:
        """Obter câmaras descobertas desde um timestamp."""
        rows = self._get_conn().execute(
            "SELECT * FROM cameras WHERE first_seen > ? ORDER BY first_seen DESC",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_status_changed_since(self, since: float) -> list[dict]:
        """Obter câmaras cujo status mudou desde um timestamp."""
        rows = self._get_conn().execute(
            "SELECT * FROM cameras WHERE last_seen > ? ORDER BY last_seen DESC",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Scans ────────────────────────────────────────────────────────

    def save_scan(self, scan_id: str, started_at: float, config: ScanConfig) -> int:
        """Inserir registo de scan. Devolve rowid."""
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO scans (scan_id, started_at, source, query, country, config_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                scan_id,
                started_at,
                "censys" if config.censys_enabled else "local",
                config.censys_query,
                config.censys_country,
                json.dumps(asdict(config), default=str),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def finish_scan(self, scan_id: str, result: ScanResult) -> None:
        """Atualizar scan com resultados."""
        conn = self._get_conn()
        conn.execute(
            """UPDATE scans SET
                finished_at = ?, total_ips = ?, live_count = ?, auth_count = ?,
                closed_count = ?, error_count = ?, duration_secs = ?
               WHERE scan_id = ?""",
            (
                time.time(),
                result.total_ips,
                result.accessible,
                result.auth_required,
                result.closed,
                result.errors,
                result.finished_at - result.started_at if result.finished_at else 0,
                scan_id,
            ),
        )
        conn.commit()

    def get_recent_scans(self, limit: int = 10) -> list[dict]:
        """Listar scans recentes."""
        rows = self._get_conn().execute(
            "SELECT * FROM scans ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Alertas ──────────────────────────────────────────────────────

    def create_alert(self, camera_ip: str, scan_id: str, alert_type: str, message: str) -> int:
        """Criar alerta. Devolve rowid."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO alerts (camera_ip, scan_id, alert_type, message) VALUES (?, ?, ?, ?)",
            (camera_ip, scan_id, alert_type, message),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)

    def get_unsent_alerts(self, limit: int = 50) -> list[dict]:
        """Obter alertas não enviados."""
        rows = self._get_conn().execute(
            "SELECT * FROM alerts WHERE sent = 0 ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_alert_sent(self, alert_id: int) -> None:
        """Marcar alerta como enviado."""
        self._get_conn().execute(
            "UPDATE alerts SET sent = 1, sent_at = ? WHERE id = ?",
            (time.time(), alert_id),
        )
        self._get_conn().commit()

    # ── GeoIP Cache ──────────────────────────────────────────────────

    def get_geoip_cache(self, ip: str) -> dict | None:
        """Obter GeoIP da cache se ainda válido."""
        row = self._get_conn().execute(
            "SELECT * FROM geoip_cache WHERE ip = ? AND expires_at > ?",
            (ip, time.time()),
        ).fetchone()
        if row:
            return dict(row)
        return None

    def set_geoip_cache(self, ip: str, data: dict, ttl: int = 86400) -> None:
        """Guardar GeoIP em cache (default 24h)."""
        conn = self._get_conn()
        data["ip"] = ip
        data["expires_at"] = time.time() + ttl
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn.execute(
            f"INSERT OR REPLACE INTO geoip_cache ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        conn.commit()

    # ── Estatísticas ─────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Estatísticas gerais da base de dados."""
        conn = self._get_conn()
        stats = {}
        for key, sql in [
            ("total_cameras", "SELECT COUNT(*) FROM cameras"),
            ("live", "SELECT COUNT(*) FROM cameras WHERE status = 'live'"),
            ("auth_required", "SELECT COUNT(*) FROM cameras WHERE status = 'auth'"),
            ("closed", "SELECT COUNT(*) FROM cameras WHERE status = 'closed'"),
            ("total_scans", "SELECT COUNT(*) FROM scans"),
            ("unsent_alerts", "SELECT COUNT(*) FROM alerts WHERE sent = 0"),
            ("vendors", "SELECT COUNT(DISTINCT vendor) FROM cameras WHERE vendor IS NOT NULL"),
        ]:
            stats[key] = conn.execute(sql).fetchone()[0]
        return stats
