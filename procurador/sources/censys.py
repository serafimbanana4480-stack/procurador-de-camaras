"""
Integração com Censys API v2 (Platform API).

Procura dispositivos com serviços RTSP/HTTP/ONVIF e devolve objetos Camera.
Suporta fallback gracioso se a API não responder.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from procurador.core.models import (
    Camera,
    CameraStatus,
    GeoLocation,
    NetworkInfo,
    ScanConfig,
    SourceType,
)
from procurador.utils.helpers import retry

logger = logging.getLogger(__name__)


# =====================================================================
# Vendor identification (banner / path / service patterns)
# =====================================================================

# Map low-level identifier → vendor
VENDOR_SIGNATURES: dict[str, list[str]] = {
    "Hikvision": [
        "hikvision",
        "iVMS",
        "ds-2cd",
        "ds-2de",
        "ds-7600",
        "h264/ch1",
        "h265/ch1",
        "/streaming/channels",
        "hiksdk",
    ],
    "Dahua": [
        "dahua",
        "realmonitor",
        "dss",
        "xvr",
        "ipc-hdw",
        "ipc-hfw",
        "dh-sd",
        "/cam/realmonitor",
    ],
    "Axis": [
        "axis",
        "vapix",
        "axis-media/media.amp",
        "axis-",
        "p33",
        "q16",
        "m1065",
        "m3046",
    ],
    "Reolink": [
        "reolink",
        "h264preview",
        "rlc-",
        "b800",
        "rlc-410",
        "rcl-",
    ],
    "TP-Link": ["tp-link", "tapo", "/stream1", "kasa"],
    "Foscam": ["foscam", "videomain", "videosub", "fi9821", "c1", "c2"],
    "Bosch": ["bosch", "videoserver", "autodome", "dinion"],
    "Hanwha": ["hanwha", "samsung", "media.smp", "snp", "xno"],
    "Uniview": ["uniview", "unicast/c", "ipc-", "ezview"],
    "Amcrest": ["amcrest", "ip2m-", "ip4m-"],
    "Lorex": ["lorex"],
    "Annke": ["annke"],
    "Swann": ["swann"],
    "Vivotek": ["vivotek", "live.sdp", "ip7137", "fd836", "ib836"],
    "GeoVision": ["geovision", "ch001.sdp", "gv-"],
    "Hipcam": ["hipcam"],
    "HiSilicon": ["hisilicon", "goke"],
    "Xiongmaitech": ["xiongmai", "xiongmai", "xmeye", "xmtech"],
    "Ezviz": ["ezviz", "cs-cv246"],
    "GALAYOU": ["galayou"],
    "Provision": ["provision"],
    "Alula": ["alula"],
    "Arecont": ["arecont"],
    "Avigilon": ["avigilon", "acc"],
    "Pelco": ["pelco", "sarix", "spectra"],
    "Vicon": ["vicon"],
    "March Networks": ["march networks"],
    "Digital Watchdog": ["digital watchdog", "dw"],
    "Speco": ["speco"],
    "Honeywell": ["honeywell"],
}


def identify_vendor(banner: str, http_title: str | None = None) -> str | None:
    """Identifica fabricante a partir de banner RTSP, HTTP, ou service info.

    Args:
        banner: Texto do banner (RTSP server, raw service, etc).
        http_title: Título da página HTTP (opcional, pode confirmar).

    Returns:
        Nome do fabricante (canonical) ou None.
    """
    text_parts = [banner or "", http_title or ""]
    combined = " ".join(t for t in text_parts if t).lower()
    if not combined.strip():
        return None

    for vendor, signatures in VENDOR_SIGNATURES.items():
        for sig in signatures:
            if sig in combined:
                return vendor
    return None


# =====================================================================
# Query builder
# =====================================================================

# Country code → ISO mapping (Censys usa ISO-3166 alpha-2)
COUNTRY_CODE_MAP: dict[str, str] = {
    "portugal": "PT",
    "espanha": "ES",
    "spain": "ES",
    "brasil": "BR",
    "brazil": "BR",
    "estados unidos": "US",
    "united states": "US",
    "frança": "FR",
    "france": "FR",
    "alemanha": "DE",
    "germany": "DE",
    "itália": "IT",
    "italy": "IT",
    "reino unido": "GB",
    "united kingdom": "GB",
    "uk": "GB",
    "méxico": "MX",
    "mexico": "MX",
    "holanda": "NL",
    "netherlands": "NL",
    "suécia": "SE",
    "sweden": "SE",
    "irlanda": "IE",
    "ireland": "IE",
}


def _normalize_country(country: str) -> str | None:
    """Normaliza input de país para código ISO-2.

    Aceita: 'PT', 'pt', 'Portugal', 'portugal'.
    """
    if not country:
        return None
    c = country.strip()
    if not c:
        return None
    if len(c) == 2:
        return c.upper()
    return COUNTRY_CODE_MAP.get(c.lower(), c)


def query_builder(
    country: str = "",
    base_query: str = "",
) -> str:
    """Constrói query Censys optimizada para câmaras.

    Args:
        country: País para filtro ('PT' ou 'Portugal'). Vazio = sem filtro.
        base_query: Query base (default: serviços RTSP).

    Returns:
        String com query CenQL.
    """
    base = (base_query or "services.service_name: RTSP").strip()
    code = _normalize_country(country)
    if code:
        # Tenta o campo correto do Censys Platform API
        base = f"{base} and location.country_code: {code}"
    return base


# =====================================================================
# Censys search
# =====================================================================


@retry(exceptions=(Exception,), tries=2, delay=1.0)
def _build_client(api_id: str, api_secret: str | None):
    """Constrói o cliente CensysHosts (lazy import).

    Suporta:
    - Personal Access Token: CensysHosts(api_id="<token>", api_secret=None)
    - API ID + Secret: CensysHosts(api_id="<id>", api_secret="<secret>")
    """
    from censys.search import CensysHosts

    return CensysHosts(api_id=api_id, api_secret=api_secret)


def search_censys(
    config: ScanConfig,
    api_id: str | None = None,
    api_secret: str | None = None,
) -> Generator[Camera, None, None]:
    """Procura câmaras no Censys e devolve Camera objects.

    Args:
        config: ScanConfig (usa censys_query, censys_country, censys_max_pages).
        api_id: API ID (opcional; usa env).
        api_secret: API secret (opcional; pode ser vazio).

    Yields:
        Camera objects com info básica do Censys (sem probe ainda).
    """
    from procurador.config import get_censys_credentials

    if not api_id:
        api_id, api_secret = get_censys_credentials()
        if not api_id:
            logger.error(
                "Censys API key não configurada. "
                "Set CENSYS_API_KEY, CENSYS_API_ID ou CENSYS_SECRET no .env"
            )
            return

    # Tenta com o cliente oficial
    try:
        client = _build_client(api_id, api_secret)
    except Exception as e:
        logger.warning(f"CensysHosts falhou ({e}). A tentar API direta...")
        client = None

    if client is None:
        # Fallback: API direta HTTP
        yield from _search_censys_direct(api_id, api_secret, config)
        return

    query = query_builder(config.censys_country, config.censys_query)
    logger.info(f"🔍 Censys query: {query}")
    logger.info(f"   max_pages={config.censys_max_pages} per_page={config.censys_per_page}")

    # Detectar API disponível
    use_v2 = hasattr(client, "v2") and hasattr(client.v2, "hosts")

    # Censys v2 — paginação com next_page_token
    count = 0
    cursor: str | None = None
    pages = 0
    try:
        while pages < config.censys_max_pages:
            per_page = min(max(1, config.censys_per_page), 100)

            try:
                if use_v2:
                    search_kwargs: dict = {"q": query, "per_page": per_page}
                    if cursor:
                        search_kwargs["cursor"] = cursor
                    result = client.v2.hosts.search(**search_kwargs)
                else:
                    # API antiga (CensysHosts.search)
                    result = client.search(
                        query,
                        per_page=per_page,
                        cursor=cursor,
                    )
            except Exception as e:
                logger.error(f"Erro Censys search: {e}")
                return

            hosts = list(result)
            if not hosts:
                break

            for host in hosts:
                try:
                    camera = _parse_censys_host(host)
                    if camera:
                        count += 1
                        yield camera
                except Exception as e:
                    logger.debug(f"Erro a parsear host Censys: {e}")
                    continue

            pages += 1

            # Próxima página
            try:
                cursor = getattr(result, "next_page_token", None)
            except Exception:
                cursor = None
            if not cursor:
                break

            # Log progresso
            logger.debug(f"   página {pages}: {len(hosts)} hosts, total={count}")

    except Exception as e:
        logger.error(f"Erro durante Censys search: {e}")
        return

    logger.info(f"✅ Censys: {count} câmaras encontradas ({pages} página(s))")


def _parse_censys_host(host) -> Camera | None:
    """Converte um host Censys num Camera.

    Aceita dict (v2) ou objeto (v1). Suporta tanto .ip como ['ip'].
    """
    if not isinstance(host, dict):
        # Tentar acesso por atributo
        try:
            host = {
                "ip": host.ip,
                "location": getattr(host, "location", {}) or {},
                "services": getattr(host, "services", []) or [],
                "last_updated_at": getattr(host, "last_updated_at", None),
            }
        except Exception:
            return None

    ip = host.get("ip")
    if not ip:
        return None

    # Location
    loc = host.get("location", {}) or {}
    geo = GeoLocation(
        country=loc.get("country"),
        country_code=loc.get("country_code"),
        city=loc.get("city"),
        region=loc.get("region") or loc.get("subdivision"),
        lat=(loc.get("coordinates") or {}).get("latitude") or loc.get("lat"),
        lon=(loc.get("coordinates") or {}).get("longitude") or loc.get("lng") or loc.get("lon"),
        postal=loc.get("postal_code"),
        timezone=loc.get("timezone"),
    )

    # Network
    net = host.get("network", {}) or {}
    network = NetworkInfo(
        isp=net.get("isp"),
        org=net.get("organization") or net.get("org"),
        asn=str(net.get("asn")) if net.get("asn") else None,
        as_name=net.get("as_name"),
        hostname=None,  # Censys v2 não tem por default
    )

    # Services
    services = host.get("services", []) or []
    ports_open: list[int] = []
    rtsp_service: dict | None = None
    http_service: dict | None = None
    onvif_service: dict | None = None

    for svc in services:
        port = svc.get("port", 0)
        if port:
            ports_open.append(port)
        name = (svc.get("service_name") or svc.get("transport_protocol") or "").lower()
        ext_name = (svc.get("extended_service_name") or "").lower()

        # RTSP — porta 554 ou nome RTSP
        if port == 554 or "rtsp" in name or "rtsp" in ext_name:
            if not rtsp_service:
                rtsp_service = svc
        # HTTP — porta 80, 443, 8080 ou nome HTTP
        elif (
            port in (80, 443, 8000, 8008, 8080, 8081, 8443) or "http" in name or "http" in ext_name
        ):
            if not http_service:
                http_service = svc
        # ONVIF — porta 80/8080 com path /onvif/
        if "onvif" in ext_name or port in (2020, 3702):
            if not onvif_service:
                onvif_service = svc

    if not rtsp_service and not http_service:
        return None

    # Decide porta inicial
    primary_port = 554
    if rtsp_service and rtsp_service.get("port"):
        primary_port = int(rtsp_service["port"])
    elif http_service and http_service.get("port"):
        primary_port = int(http_service["port"])

    # Banner / vendor
    raw_banner = ""
    if rtsp_service:
        raw_banner = (
            rtsp_service.get("banner", "")
            or rtsp_service.get("raw", "")
            or (rtsp_service.get("rtsp") or {}).get("response", "")
        )
    if not raw_banner and http_service:
        raw_banner = http_service.get("http", {}).get("response", {}).get(
            "body", ""
        ) or http_service.get("banner", "")

    # HTTP title
    http_title = None
    if http_service:
        http_resp = http_service.get("http", {}).get("response", {}) or {}
        http_title = http_resp.get("html_title") or http_resp.get("title")

    vendor = identify_vendor(raw_banner, http_title)

    # Timestamp
    last_updated = host.get("last_updated_at") or host.get("last_seen")
    try:
        first_seen = float(last_updated) if last_updated else 0.0
    except (TypeError, ValueError):
        first_seen = 0.0

    camera = Camera(
        ip=ip,
        port=primary_port,
        source=SourceType.CENSYS,
        source_query=query_builder("", ""),
        first_seen=first_seen,
        last_seen=first_seen,
        vendor=vendor,
        geo=geo,
        network=network,
        ports_open=sorted(set(ports_open)),
        http_status=(http_service or {}).get("http", {}).get("response", {}).get("status_code"),
        http_title=http_title,
        status=CameraStatus.PENDING,
        raw_banner=raw_banner or None,
        onvif_supported=onvif_service is not None,
    )

    return camera


def _search_censys_direct(
    api_id: str,
    api_secret: str | None,
    config: ScanConfig,
) -> Generator[Camera, None, None]:
    """Fallback: pesquisa Censys via API HTTP direta.

    Suporta:
    - Personal Access Token: Basic auth (token, '')
    - API ID + Secret: Basic auth (id, secret)
    """
    import requests

    base_url = "https://search.censys.io/api/v2"
    query = query_builder(config.censys_country, config.censys_query)
    logger.info(f"🔍 Censys direct API: {query}")

    if api_secret is None:
        # Personal Access Token: Basic auth com token + password vazio
        auth = (api_id, "")
    else:
        auth = (api_id, api_secret)
    headers = {"Accept": "application/json"}
    page = 1
    next_token = None
    count = 0

    while page <= config.censys_max_pages:
        params = {
            "q": query,
            "per_page": min(config.censys_per_page, 100),
        }
        if next_token:
            params["page_token"] = next_token

        try:
            r = requests.get(
                f"{base_url}/hosts/search",
                auth=auth,
                headers=headers,
                params=params,
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                hits = data.get("result", {}).get("hits", [])
                for host in hits:
                    camera = _parse_censys_host(host)
                    if camera:
                        count += 1
                        yield camera
                next_token = data.get("result", {}).get("next_page_token")
                if not next_token:
                    break
                page += 1
            elif r.status_code == 401:
                logger.error("Censys API: 401 Unauthorized — verifica API key")
                return
            else:
                logger.error(f"Censys API error: {r.status_code} — {r.text[:100]}")
                return
        except requests.exceptions.Timeout:
            logger.warning(f"Censys API timeout (página {page})")
            return
        except Exception as e:
            logger.error(f"Censys API error: {e}")
            return

    logger.info(f"✅ Censys direct: {count} câmaras")

