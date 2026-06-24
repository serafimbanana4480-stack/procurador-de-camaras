"""
Modelos de dados do Procurador de Câmara.

Dataclasses partilhadas: Camera, ScanResult, ScanConfig, GeoLocation,
NetworkInfo, StreamInfo, RTSPProbe.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# =====================================================================
# Enums
# =====================================================================

class CameraStatus(str, Enum):
    """Estado actual da câmara no pipeline de scan."""
    PENDING = "pending"
    SCANNING = "scanning"
    LIVE = "live"                 # Stream acessível!
    AUTH_REQUIRED = "auth"        # RTSP responde mas pede creds
    AUTH_FAILED = "auth_fail"     # Tentámos creds default, sem sucesso
    CLOSED = "closed"             # Porta fechada / timeout
    ERROR = "error"               # Erro genérico
    WEB_ONLY = "web"              # Só HTTP admin, sem RTSP


class SourceType(str, Enum):
    """Fonte de onde o IP veio."""
    CENSYS = "censys"
    SHODAN = "shodan"
    LOCAL_ARP = "local_arp"
    LOCAL_ONVIF = "local_onvif"
    MANUAL = "manual"


class AccessMethod(str, Enum):
    """Método pelo qual a câmara foi acedida."""
    RTSP_NO_AUTH = "rtsp_no_auth"
    RTSP_BRUTE = "rtsp_brute"
    ONVIF = "onvif"
    HTTP_SNAPSHOT = "http_snapshot"
    HTTP_ADMIN = "http_admin"
    CVE_EXPLOIT = "cve_exploit"
    ALT_PORT = "alt_port"
    UNKNOWN = "unknown"


# =====================================================================
# Sub-modelos
# =====================================================================

@dataclass
class GeoLocation:
    """Informação de localização geográfica."""
    country: str | None = None
    country_code: str | None = None
    city: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None
    postal: str | None = None
    timezone: str | None = None


@dataclass
class NetworkInfo:
    """Informação de rede do dispositivo."""
    isp: str | None = None
    org: str | None = None
    asn: str | None = None
    as_name: str | None = None
    hostname: str | None = None
    domain: str | None = None


@dataclass
class StreamInfo:
    """Informação do stream RTSP/HTTP."""
    codec: str | None = None         # H.264, H.265, MJPEG
    width: int = 0
    height: int = 0
    fps: float = 0.0
    bitrate_kbps: float | None = None
    pixel_format: str | None = None
    profile: str | None = None
    url: str | None = None           # URL final do stream (snapshot ou RTSP)

    @property
    def resolution(self) -> str:
        """Resolução legível."""
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return "N/A"


@dataclass
class RTSPProbe:
    """Resultado do probe RTSP."""
    methods: list[str] = field(default_factory=list)
    public_header: str | None = None
    server_header: str | None = None
    sdp_body: str | None = None
    status_code: int = 0
    status_text: str = ""
    response_time_ms: float = 0.0
    auth_header: str | None = None  # WWW-Authenticate (Basic/Digest)
    auth_realm: str | None = None
    auth_nonce: str | None = None
    auth_method: str | None = None   # "Basic" | "Digest" | "None"


# =====================================================================
# Camera
# =====================================================================

@dataclass
class Camera:
    """Representação completa de uma câmara IP."""

    # Identificação base
    ip: str
    port: int = 554

    # Descoberta
    source: SourceType = SourceType.CENSYS
    source_query: str = ""
    first_seen: float = 0.0
    last_seen: float = 0.0

    # Fabricante / Modelo
    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    mac_address: str | None = None

    # Portas
    ports_open: list[int] = field(default_factory=list)

    # HTTP / Web Admin
    http_status: int | None = None
    http_title: str | None = None
    http_server: str | None = None
    http_url: str | None = None
    http_login_url: str | None = None
    http_snapshot_url: str | None = None

    # RTSP
    rtsp_probe: RTSPProbe | None = None
    rtsp_path: str | None = None
    rtsp_url: str | None = None         # Com creds embutidas

    # Auth
    auth_required: bool = True
    auth_success: bool = False
    auth_user: str | None = None
    auth_pass: str | None = None
    auth_method: str | None = None      # "Basic" | "Digest"

    # Stream
    stream: StreamInfo | None = None
    screenshot_path: str | None = None

    # ONVIF
    onvif_supported: bool = False
    onvif_url: str | None = None
    onvif_profiles: list[str] = field(default_factory=list)
    onvif_stream_uris: list[str] = field(default_factory=list)
    ptz_supported: bool = False

    # CVE
    cve_exploited: str | None = None

    # Como foi acedido
    access_method: AccessMethod = AccessMethod.UNKNOWN

    # Localização
    geo: GeoLocation = field(default_factory=GeoLocation)
    network: NetworkInfo = field(default_factory=NetworkInfo)

    # Estado
    status: CameraStatus = CameraStatus.PENDING
    error_message: str | None = None
    raw_banner: str | None = None
    tags: list[str] = field(default_factory=list)

    # ---- Serialização ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serializar para dicionário (JSON-friendly)."""
        d = asdict(self)
        d['source'] = self.source.value
        d['status'] = self.status.value
        d['access_method'] = self.access_method.value
        if self.stream:
            d['resolution'] = self.stream.resolution
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Camera:
        """Desserializar de dicionário."""
        d = dict(d)
        d['source'] = SourceType(d.get('source', 'censys'))
        d['status'] = CameraStatus(d.get('status', 'pending'))
        d['access_method'] = AccessMethod(d.get('access_method', 'unknown'))
        d['geo'] = GeoLocation(**d.get('geo', {}))
        d['network'] = NetworkInfo(**d.get('network', {}))
        if d.get('stream'):
            d['stream'] = StreamInfo(**d['stream'])
        if d.get('rtsp_probe'):
            d['rtsp_probe'] = RTSPProbe(**d['rtsp_probe'])
        d.pop('resolution', None)
        return cls(**d)

    # ---- Propriedades computadas ----------------------------------------

    @property
    def resolution(self) -> str:
        """Resolução do stream (ou N/A)."""
        return self.stream.resolution if self.stream else "N/A"

    @property
    def country_flag(self) -> str:
        """Devolve flag emoji do país."""
        if not self.geo.country_code:
            return ""
        cc = self.geo.country_code.upper()
        try:
            return chr(ord(cc[0]) + 127397) + chr(ord(cc[1]) + 127397)
        except Exception:
            return ""

    @property
    def location_str(self) -> str:
        """String amigável de localização."""
        parts: list[str] = []
        if self.geo.city:
            parts.append(self.geo.city)
        if self.geo.country:
            parts.append(f"{self.geo.country} {self.country_flag}")
        return ", ".join(parts) if parts else "Unknown"

    @property
    def is_accessible(self) -> bool:
        """Verdadeiro se a câmara tem algum tipo de acesso."""
        return self.status in (
            CameraStatus.LIVE,
            CameraStatus.WEB_ONLY,
            CameraStatus.AUTH_REQUIRED,
        )


# =====================================================================
# Configuração
# =====================================================================

@dataclass
class ScanConfig:
    """Configuração de um scan."""

    # Fontes
    censys_enabled: bool = True
    shodan_enabled: bool = False
    local_enabled: bool = False

    # Censys
    censys_query: str = "services.service_name: RTSP"
    censys_country: str = ""
    censys_max_pages: int = 5
    censys_per_page: int = 100

    # Shodan
    shodan_query: str = "port:554"

    # Scan RTSP
    rtsp_probe_timeout: float = 3.0
    rtsp_probe_concurrent: int = 200
    rtsp_brute_paths: bool = True
    rtsp_brute_max_paths: int = 30

    # Brute creds
    brute_enabled: bool = True
    brute_max_attempts: int = 100
    brute_threads: int = 20

    # HTTP
    http_probe_enabled: bool = True
    http_timeout: float = 3.0
    http_admin_brute: bool = True
    http_max_login_attempts: int = 20

    # ONVIF
    onvif_enabled: bool = True
    onvif_timeout: float = 4.0
    onvif_default_user: str = "admin"
    onvif_default_pass: str = ""

    # CVEs
    cve_enabled: bool = True
    cve_timeout: float = 5.0

    # Stream capture
    stream_capture: bool = False           # Desligado por default (caro)
    stream_threads: int = 4
    stream_timeout: float = 5.0
    screenshot_dir: str = "data/screenshots"

    # Local scan
    local_subnet: str = "192.168.1.0/24"
    arp_timeout: int = 3

    # Alt ports
    alt_ports: list[int] = field(default_factory=lambda: [8554, 5554, 37777, 7447, 7070, 1935])

    # GeoIP
    geoip_enabled: bool = True
    ipinfo_token: str = ""

    # Geral
    max_concurrent: int = 100
    stealth: bool = False
    save_json: bool = True
    output_dir: str = "data"


# =====================================================================
# Scan result
# =====================================================================

@dataclass
class ScanResult:
    """Resultado completo de uma execução de scan."""

    scan_id: str
    config: ScanConfig = field(default_factory=ScanConfig)
    started_at: float = 0.0
    finished_at: float | None = None
    cameras: list[Camera] = field(default_factory=list)

    # Estatísticas (preenchidas no fim via calculate_stats)
    total_ips: int = 0
    accessible: int = 0
    auth_required: int = 0
    auth_failed: int = 0
    closed: int = 0
    errors: int = 0
    live_streams: int = 0
    web_only: int = 0
    vendors: dict[str, int] = field(default_factory=dict)
    countries: dict[str, int] = field(default_factory=dict)
    access_methods: dict[str, int] = field(default_factory=dict)

    def calculate_stats(self) -> None:
        """Calcular estatísticas finais."""
        self.total_ips = len(self.cameras)
        self.accessible = sum(1 for c in self.cameras if c.status == CameraStatus.LIVE)
        self.auth_required = sum(1 for c in self.cameras if c.status == CameraStatus.AUTH_REQUIRED)
        self.auth_failed = sum(1 for c in self.cameras if c.status == CameraStatus.AUTH_FAILED)
        self.closed = sum(1 for c in self.cameras if c.status == CameraStatus.CLOSED)
        self.errors = sum(1 for c in self.cameras if c.status == CameraStatus.ERROR)
        self.live_streams = sum(1 for c in self.cameras if c.stream and c.stream.width > 0)
        self.web_only = sum(1 for c in self.cameras if c.status == CameraStatus.WEB_ONLY)

        vendor_counts: dict[str, int] = {}
        for c in self.cameras:
            v = c.vendor or "Unknown"
            vendor_counts[v] = vendor_counts.get(v, 0) + 1
        self.vendors = dict(sorted(vendor_counts.items(), key=lambda x: -x[1]))

        country_counts: dict[str, int] = {}
        for c in self.cameras:
            co = c.geo.country or "Unknown"
            country_counts[co] = country_counts.get(co, 0) + 1
        self.countries = dict(sorted(country_counts.items(), key=lambda x: -x[1]))

        method_counts: dict[str, int] = {}
        for c in self.cameras:
            m = c.access_method.value
            method_counts[m] = method_counts.get(m, 0) + 1
        self.access_methods = dict(sorted(method_counts.items(), key=lambda x: -x[1]))

    def to_dict(self) -> dict[str, Any]:
        """Serializar para dicionário."""
        return {
            "scan_id": self.scan_id,
            "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
            "finished_at": datetime.fromtimestamp(self.finished_at).isoformat() if self.finished_at else None,
            "config": asdict(self.config),
            "stats": {
                "total_ips": self.total_ips,
                "accessible": self.accessible,
                "auth_required": self.auth_required,
                "auth_failed": self.auth_failed,
                "closed": self.closed,
                "errors": self.errors,
                "live_streams": self.live_streams,
                "web_only": self.web_only,
                "vendors": self.vendors,
                "countries": self.countries,
                "access_methods": self.access_methods,
            },
            "cameras": [c.to_dict() for c in self.cameras if c.status in (
                CameraStatus.LIVE,
                CameraStatus.AUTH_REQUIRED,
                CameraStatus.WEB_ONLY,
            )],
        }

    def to_json(self, path: str) -> str:
        """Exportar para JSON. Devolve o path."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        return path
