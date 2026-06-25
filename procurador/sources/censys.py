"""
Integração com Censys API v2 (Platform API).

Procura dispositivos com serviços RTSP/HTTP/ONVIF e devolve objetos Camera.
Suporta fallback gracioso se a API não responder.

Fluxo de autenticação:
- Personal Access Token (PAT) → tenta censys_platform SDK primeiro
- Se SDK falhar (conta FREE), fallback para HTTP v3 directo
- API ID + Secret → SDK legado censys v2 (CensysHosts)
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
# Censys search (entry point)
# =====================================================================


@retry(exceptions=(Exception,), tries=2, delay=1.0)
def _build_client(api_id: str, api_secret: str | None):
    """Constrói o cliente CensysHosts (lazy import)."""
    from censys.search import CensysHosts

    return CensysHosts(api_id=api_id, api_secret=api_secret)


def search_censys(
    config: ScanConfig,
    api_id: str | None = None,
    api_secret: str | None = None,
) -> Generator[Camera, None, None]:
    """Procura câmaras no Censys e devolve Camera objects.

    Fluxo:
    1. Personal Access Token (secret=None) → SDK censys_platform → fallback HTTP v3
    2. API ID + Secret       → SDK legado CensysHosts → fallback HTTP v2

    Args:
        config: ScanConfig (usa censys_query, censys_country, censys_max_pages).
        api_id: API ID / PAT (opcional; usa env).
        api_secret: API secret (opcional; None=PAT, ""=vazio).

    Yields:
        Camera objects com info básica do Censys (sem probe ainda).
    """
    from procurador.config import get_censys_credentials

    if not api_id:
        api_id, api_secret = get_censys_credentials()
        if not api_id:
            logger.error(
                "Censys API key não configurada. "
                "Set CENSYS_PERSONAL_ACCESS_TOKEN, CENSYS_API_KEY, "
                "CENSYS_API_ID ou CENSYS_SECRET no .env"
            )
            return

    # ── Personal Access Token ─────────────────────────────────────
    if api_secret is None:
        logger.info("   PAT detetado, a tentar censys_platform SDK...")
        sdk_count = 0
        for cam in _search_platform_sdk(api_id, config):
            yield cam
            sdk_count += 1

        if sdk_count > 0:
            logger.info(f"   Platform SDK: {sdk_count} câmaras")
            return

        # Fallback: direct HTTP v3 (conta FREE sem acesso a search)
        logger.info(
            "   SDK search indisponível (conta FREE?). "
            "A usar fallback HTTP v3..."
        )
        query = query_builder(config.censys_country, config.censys_query)
        yield from _search_censys_v3(api_id, query, config)
        return

    # ── API ID + Secret (legado) ──────────────────────────────────
    try:
        client = _build_client(api_id, api_secret)
    except Exception as e:
        logger.warning(f"CensysHosts falhou ({e}). A tentar API direta...")
        client = None

    if client is None:
        yield from _search_censys_direct(api_id, api_secret, config)
        return

    query = query_builder(config.censys_country, config.censys_query)
    logger.info(f"🔍 Censys query: {query}")
    logger.info(f"   max_pages={config.censys_max_pages} per_page={config.censys_per_page}")

    use_v2 = hasattr(client, "v2") and hasattr(client.v2, "hosts")

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

            try:
                cursor = getattr(result, "next_page_token", None)
            except Exception:
                cursor = None
            if not cursor:
                break

            logger.debug(f"   página {pages}: {len(hosts)} hosts, total={count}")

    except Exception as e:
        logger.error(f"Erro durante Censys search: {e}")
        return

    logger.info(f"✅ Censys: {count} câmaras encontradas ({pages} página(s))")


# =====================================================================
# Platform SDK search (+ get_hosts)
# =====================================================================


def _search_platform_sdk(
    api_key: str,
    config: ScanConfig,
) -> Generator[Camera, None, None]:
    """Pesquisa Censys via censys_platform SDK (Platform API v3).

    Usa ``sdk.global_data.search()``.
    Se retornar 403 (conta FREE), log warning e sai sem resultados
    para permitir fallback a HTTP directo.

    Args:
        api_key: Personal Access Token.
        config: ScanConfig com query, país, páginas, etc.

    Yields:
        Camera objects convertidos dos SDK hits.
    """
    try:
        from censys_platform import SDK
        from censys_platform.models.searchqueryinputbody import SearchQueryInputBody
    except ImportError:
        logger.warning("   censys_platform SDK não instalado. A usar fallback HTTP...")
        return

    query = query_builder(config.censys_country, config.censys_query)
    logger.info(f"   Platform SDK search: {query}")

    try:
        sdk = SDK(personal_access_token=api_key)
    except Exception as e:
        logger.warning(f"   SDK init falhou: {e}")
        return

    page = 1
    page_token: str | None = None
    count = 0
    total_hits = 0

    while page <= config.censys_max_pages:
        page_size = min(max(1, config.censys_per_page), 100)

        try:
            body = SearchQueryInputBody(
                query=query,
                page_size=page_size,
                page_token=page_token,
            )
            response = sdk.global_data.search(search_query_input_body=body)
        except Exception as e:
            error_lower = str(e).lower()
            if "403" in error_lower or "forbidden" in error_lower or "not authorized" in error_lower:
                logger.warning("   SDK search: 403 (conta FREE?). Fallback para HTTP v3...")
                return  # Sem yield → caller sabe que falhou
            logger.error(f"   SDK search error: {e}")
            return

        if not response or not response.result:
            break

        result = response.result
        hits = result.hits or []
        if total_hits == 0:
            total_hits = int(result.total_hits) if result.total_hits else 0
            logger.info(f"   SDK search: {total_hits} total hits")

        for hit in hits:
            camera = _convert_sdk_search_hit_to_camera(hit)
            if camera:
                count += 1
                yield camera

        page_token = result.next_page_token if result.next_page_token else None
        if not page_token or not hits:
            break
        page += 1

    if count > 0:
        logger.info(f"   Platform SDK search: {count} câmaras ({page} página(s))")


def _get_hosts_platform_sdk(
    api_key: str,
    ips: list[str],
) -> Generator[Camera, None, None]:
    """Lookup de IPs específicos via censys_platform SDK (global_data.get_hosts()).

    Args:
        api_key: Personal Access Token.
        ips: Lista de IPs para consultar.

    Yields:
        Camera objects convertidos.
    """
    try:
        from censys_platform import SDK
        from censys_platform.models.assethostlistinputbody import AssetHostListInputBody
    except ImportError:
        logger.warning("   censys_platform SDK não instalado. Ignorando get_hosts...")
        return

    if not ips:
        return

    logger.info(f"   SDK get_hosts: {len(ips)} IP(s)")

    try:
        sdk = SDK(personal_access_token=api_key)
    except Exception as e:
        logger.warning(f"   SDK init falhou: {e}")
        return

    # Process in batches (API may limit)
    batch_size = 50
    count = 0
    for i in range(0, len(ips), batch_size):
        batch = ips[i : i + batch_size]
        try:
            body = AssetHostListInputBody(host_ids=batch)
            response = sdk.global_data.get_hosts(asset_host_list_input_body=body)
        except Exception as e:
            logger.warning(f"   SDK get_hosts error (batch {i}): {e}")
            continue

        if response and response.result and response.result.result:
            for asset in response.result.result:
                if asset and asset.resource:
                    camera = _convert_sdk_host_to_camera(asset.resource)
                    if camera:
                        count += 1
                        yield camera

    if count > 0:
        logger.info(f"   SDK get_hosts: {count} câmaras")


# =====================================================================
# SDK → Camera conversion
# =====================================================================


def _convert_sdk_search_hit_to_camera(hit) -> Camera | None:
    """Converte um SearchQueryHit do SDK censys_platform em Camera.

    A hit contém ``host_v1`` (HostAssetWithMatchedServices) com
    ``resource`` (Host) e ``matched_services``.
    """
    if not hit or not hit.host_v1 or not hit.host_v1.resource:
        return None
    return _convert_sdk_host_to_camera(
        hit.host_v1.resource,
        hit.host_v1.matched_services,
    )


def _convert_sdk_host_to_camera(host, matched_services=None) -> Camera | None:
    """Converte um modelo ``Host`` do SDK censys_platform em Camera.

    Args:
        host: Instância de censys_platform.models.host.Host.
        matched_services: Opcional, lista de MatchedService.

    Returns:
        Camera ou None se inválido.
    """
    if not host or not host.ip:
        return None

    ip = host.ip

    # ── Location ────────────────────────────────────────────────
    loc = host.location
    geo = GeoLocation(
        country=loc.country if loc else None,
        country_code=loc.country_code if loc else None,
        city=loc.city if loc else None,
        region=loc.province if loc else None,
        lat=loc.coordinates.latitude if loc and loc.coordinates else None,
        lon=loc.coordinates.longitude if loc and loc.coordinates else None,
        postal=loc.postal_code if loc else None,
        timezone=loc.timezone if loc else None,
    )

    # ── Network / ASN ────────────────────────────────────────────
    asys = host.autonomous_system
    network = NetworkInfo(
        isp=None,
        org=asys.organization if asys else None,
        asn=str(asys.asn) if asys and asys.asn else None,
        as_name=asys.name if asys else None,
    )

    # ── Services ─────────────────────────────────────────────────
    services = list(host.services or [])
    ports_open: list[int] = []
    rtsp_svc = None
    http_svc = None
    onvif_svc = None

    for svc in services:
        port = svc.port or 0
        if port:
            ports_open.append(port)

        # RTSP — porta 554 ou objecto rtsp presente
        if port == 554 or svc.rtsp is not None:
            if not rtsp_svc:
                rtsp_svc = svc
        # HTTP — portas comuns ou objecto http presente
        elif (
            port in (80, 443, 8000, 8008, 8080, 8081, 8443)
            or svc.http is not None
        ):
            if not http_svc:
                http_svc = svc

        # ONVIF
        if svc.onvif is not None or port in (2020, 3702):
            if not onvif_svc:
                onvif_svc = svc

    if not rtsp_svc and not http_svc:
        return None

    # Porta primária
    primary_port = 554
    if rtsp_svc and rtsp_svc.port:
        primary_port = rtsp_svc.port
    elif http_svc and http_svc.port:
        primary_port = http_svc.port

    # Banner / vendor
    raw_banner = ""
    if rtsp_svc:
        raw_banner = rtsp_svc.banner or ""
        if not raw_banner and rtsp_svc.rtsp:
            raw_banner = rtsp_svc.rtsp.server or ""
    if not raw_banner and http_svc:
        raw_banner = http_svc.banner or ""

    # HTTP title / status
    http_title: str | None = None
    http_status: int | None = None
    if http_svc and http_svc.http:
        http_title = http_svc.http.html_title
        http_status = http_svc.http.status_code

    vendor = identify_vendor(raw_banner, http_title)

    return Camera(
        ip=ip,
        port=primary_port,
        source=SourceType.CENSYS,
        first_seen=0.0,
        last_seen=0.0,
        vendor=vendor,
        geo=geo,
        network=network,
        ports_open=sorted(set(ports_open)),
        http_status=http_status,
        http_title=http_title,
        status=CameraStatus.PENDING,
        raw_banner=raw_banner or None,
        onvif_supported=onvif_svc is not None,
    )


# =====================================================================
# Legacy CensysHost parser
# =====================================================================


def _parse_censys_host(host) -> Camera | None:
    """Converte um host Censys (dict ou objecto v1/v2) num Camera.

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


# =====================================================================
# Direct HTTP fallbacks
# =====================================================================


def _search_censys_direct(
    api_id: str,
    api_secret: str | None,
    config: ScanConfig,
) -> Generator[Camera, None, None]:
    """Fallback: pesquisa Censys via API HTTP directa.

    Estrategia (por ordem):
    1. Platform API v3 (search.censys.io/api/v3) - Bearer token
    2. Legacy Search API v2 (search.censys.io/api/v2) - API ID + Secret

    O Personal Access Token (PAT) so funciona na Platform API v3.
    """
    import requests

    query = query_builder(config.censys_country, config.censys_query)
    logger.info(f"Direct Censys API: {query}")

    is_pat = api_secret is None or api_secret == ""
    is_legacy = api_secret is not None and api_secret != ""

    if is_pat:
        # Platform API v3 - Bearer token
        logger.info("   Platform API v3 (Bearer token)")
        count = 0
        for cam in _search_censys_v3(api_id, query, config):
            yield cam
            count += 1
        if count > 0:
            return  # v3 funcionou

    # Legacy Search API v2 - Basic auth
    logger.info("   Legacy Search API v2")
    for cam in _search_censys_v2(api_id, api_secret, query, config):
        yield cam


def _search_censys_v3(
    token: str,
    query: str,
    config: ScanConfig,
) -> Generator[Camera, None, None]:
    """Platform API v3: search.censys.io/api/v3/global/search/query.

    Usa POST com Bearer token.
    """
    import requests

    url = "https://search.censys.io/api/v3/global/search/query"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    page = 1
    cursor: str | None = None
    count = 0

    while page <= config.censys_max_pages:
        per_page = min(max(1, config.censys_per_page), 100)
        body: dict = {
            "q": query,
            "per_page": per_page,
        }
        if cursor:
            body["cursor"] = cursor

        try:
            r = requests.post(url, json=body, headers=headers, timeout=20)
        except requests.exceptions.Timeout:
            logger.warning(f"Censys v3 timeout (pagina {page})")
            return
        except Exception as e:
            logger.error(f"Censys v3 error: {e}")
            return

        if r.status_code == 200:
            data = r.json()
            result = data.get("result", {}) or {}
            hits = result.get("hits", []) or []

            for hit in hits:
                camera = _parse_censys_v3_host(hit)
                if camera:
                    count += 1
                    yield camera

            next_cursor = result.get("next_cursor") or result.get("cursor")
            if not next_cursor or not hits:
                break
            cursor = next_cursor
            page += 1

        elif r.status_code in (401, 403):
            if page == 1:
                logger.warning(f"Censys v3: {r.status_code} - token invalido")
            return
        else:
            logger.debug(f"Censys v3: {r.status_code}")
            return

    if count > 0:
        logger.info(f"   Censys v3: {count} hosts ({page} pagina(s))")


def _parse_censys_v3_host(hit: dict) -> Camera | None:
    """Converte um hit da Platform API v3 em Camera."""
    ip = hit.get("ip")
    if not ip:
        return None

    loc = hit.get("location", {}) or {}
    geo = GeoLocation(
        country=loc.get("country"),
        country_code=loc.get("country_code"),
        city=loc.get("city"),
        region=loc.get("region"),
        lat=loc.get("latitude") or loc.get("lat"),
        lon=loc.get("longitude") or loc.get("lng") or loc.get("lon"),
        postal=loc.get("postal_code"),
        timezone=loc.get("timezone"),
    )

    net = hit.get("network", {}) or {}
    network = NetworkInfo(
        isp=net.get("isp"),
        org=net.get("organization") or net.get("org"),
        asn=str(net.get("asn")) if net.get("asn") else None,
        as_name=net.get("as_name"),
    )

    services = hit.get("services", []) or []
    ports_open = []
    rtsp_service = None
    http_service = None
    onvif_service = None

    for svc in services:
        port = svc.get("port", 0)
        if port:
            ports_open.append(port)
        name = (svc.get("service_name") or svc.get("transport_protocol") or "").lower()
        ext_name = (svc.get("extended_service_name") or "").lower()

        if port == 554 or "rtsp" in name or "rtsp" in ext_name:
            if not rtsp_service:
                rtsp_service = svc
        elif port in (80, 443, 8080, 8000, 8443) or "http" in name:
            if not http_service:
                http_service = svc
        if "onvif" in ext_name or port in (2020, 3702):
            if not onvif_service:
                onvif_service = svc

    if not rtsp_service and not http_service:
        return None

    primary_port = 554
    if rtsp_service and rtsp_service.get("port"):
        primary_port = int(rtsp_service["port"])
    elif http_service and http_service.get("port"):
        primary_port = int(http_service["port"])

    raw_banner = ""
    if rtsp_service:
        raw_banner = (
            rtsp_service.get("banner", "")
            or (rtsp_service.get("rtsp") or {}).get("response", "")
        )
    if not raw_banner and http_service:
        raw_banner = http_service.get("http", {}).get("response", {}).get("body", "")

    http_title = None
    if http_service:
        http_resp = http_service.get("http", {}).get("response", {}) or {}
        http_title = http_resp.get("html_title") or http_resp.get("title")

    vendor = identify_vendor(raw_banner, http_title)

    ts = hit.get("last_updated_at") or hit.get("last_seen")
    try:
        first_seen = float(ts) if ts else 0.0
    except (TypeError, ValueError):
        first_seen = 0.0

    return Camera(
        ip=ip,
        port=primary_port,
        source=SourceType.CENSYS,
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


def _search_censys_v2(
    api_id: str,
    api_secret: str | None,
    query: str,
    config: ScanConfig,
) -> Generator[Camera, None, None]:
    """Legacy Search API v2: Basic auth (API ID + Secret)."""
    import requests

    if api_secret is None:
        auth = (api_id, "")
    else:
        auth = (api_id, api_secret)

    headers = {"Accept": "application/json"}
    url = "https://search.censys.io/api/v2/hosts/search"
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
            r = requests.get(url, auth=auth, headers=headers, params=params, timeout=15)
        except requests.exceptions.Timeout:
            logger.warning(f"Censys v2 timeout (pagina {page})")
            return
        except Exception as e:
            logger.error(f"Censys v2 error: {e}")
            return

        if r.status_code == 200:
            data = r.json()
            hits = data.get("result", {}).get("hits", [])
            if not hits:
                break
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
            logger.debug("Censys v2: 401 (esperado com PAT)")
            return
        else:
            logger.debug(f"Censys v2: {r.status_code}")
            return

    if count > 0:
        logger.info(f"   Censys v2: {count} hosts ({page} pagina(s))")
