"""
Motor de probe do Procurador de Câmara.

Implementa as técnicas de acesso:
- Técnica 1: RTSP sem auth (probe_rtsp_no_auth)
- Técnica 3: HTTP Snapshot (find_snapshot)
- Técnica 4: HTTP Admin + creds default (probe_http_admin)
- Técnica 6: Portas alternativas (scan_alt_ports)

Técnica 5 (brute) e Técnica 7 (CVE) estão em módulos separados.
Técnica 2 (ONVIF) está em core/onvif.py.
"""

from __future__ import annotations

import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from procurador.core.models import (
    AccessMethod,
    Camera,
    CameraStatus,
    RTSPProbe,
)
from procurador.core.wordlists import (
    HTTP_ADMIN_PATHS,
    HTTP_PORTS,
    HTTP_SNAPSHOT_PATHS,
    RTSP_PORTS,
    get_paths_for_vendor,
)
from procurador.utils.helpers import extract_title

logger = logging.getLogger(__name__)


# =====================================================================
# TÉCNICA 1 — RTSP sem auth (incl. CVE-2025-9983 GALAYOU, CVE-2025-66049 Vivotek)
# =====================================================================


def _parse_rtsp_response(raw: str) -> tuple[int, str, dict]:
    """Parseia resposta RTSP. Devolve (status_code, status_text, headers)."""
    headers: dict[str, str] = {}
    status_code = 0
    status_text = ""
    if not raw:
        return 0, "", headers

    lines = raw.splitlines()
    if not lines:
        return 0, "", headers

    # Status line: "RTSP/1.0 200 OK"
    first = lines[0]
    if first.startswith("RTSP/") or first.startswith("HTTP/"):
        parts = first.split(" ", 2)
        if len(parts) >= 2:
            try:
                status_code = int(parts[1])
            except ValueError:
                status_code = 0
            status_text = parts[2] if len(parts) >= 3 else ""

    # Headers
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        headers[key.strip().lower()] = value.strip()

    return status_code, status_text, headers


def _parse_www_auth(headers: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    """Parseia WWW-Authenticate header. Devolve (method, realm, nonce)."""
    auth = headers.get("www-authenticate")
    if not auth:
        return None, None, None
    method = auth.split(" ", 1)[0].strip()
    realm = None
    nonce = None
    if 'realm="' in auth:
        try:
            realm = auth.split('realm="', 1)[1].split('"', 1)[0]
        except IndexError:
            realm = None
    if 'nonce="' in auth:
        try:
            nonce = auth.split('nonce="', 1)[1].split('"', 1)[0]
        except IndexError:
            nonce = None
    return method, realm, nonce


def probe_rtsp(
    ip: str,
    port: int = 554,
    path: str = "/",
    user: str | None = None,
    password: str | None = None,
    timeout: float = 3.0,
) -> RTSPProbe | None:
    """Envia DESCRIBE RTSP e devolve um RTSPProbe ou None em caso de erro.

    Args:
        ip: Endereço IP.
        port: Porto RTSP.
        path: Path RTSP (ex.: /live, /Streaming/Channels/101).
        user: Username (None = sem auth).
        password: Password.
        timeout: Timeout em segundos.

    Returns:
        RTSPProbe com status_code, headers, etc. None se não foi possível conectar.
    """
    import base64

    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        start = time.monotonic()
        try:
            sock.connect((ip, port))
        except (TimeoutError, OSError) as e:
            logger.debug(f"RTSP connect {ip}:{port} falhou: {e}")
            return None

        # Build request
        url = f"rtsp://{ip}:{port}{path}"
        cseq = 1
        req_lines = [
            f"DESCRIBE {url} RTSP/1.0",
            f"CSeq: {cseq}",
            "Accept: application/sdp",
        ]

        if user is not None:
            # Basic auth no DESCRIBE
            token = base64.b64encode(f"{user}:{password or ''}".encode()).decode()
            req_lines.append(f"Authorization: Basic {token}")

        req_lines.append("")  # Blank line ending headers
        req_lines.append("")
        req = "\r\n".join(req_lines)

        try:
            sock.sendall(req.encode("latin-1", errors="ignore"))
        except OSError as e:
            logger.debug(f"RTSP send {ip}:{port} falhou: {e}")
            return None

        # Ler resposta
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
            if b"\r\n\r\n" in data and b"RTSP/" in data[:32]:
                # Pequena pausa para body SDP
                sock.settimeout(0.3)
                try:
                    extra = sock.recv(8192)
                    if extra:
                        data += extra
                except TimeoutError:
                    pass
                break
            if len(data) > 65536:
                break

        elapsed_ms = (time.monotonic() - start) * 1000
        raw = data.decode("latin-1", errors="ignore")
        if not raw.strip():
            return None

        status_code, status_text, headers = _parse_rtsp_response(raw)
        if status_code == 0:
            return None

        method, realm, nonce = _parse_www_auth(headers)
        public = headers.get("public", "")
        server = headers.get("server", "")

        # SDP body (depois de \r\n\r\n)
        sdp_body: str | None = None
        if "\r\n\r\n" in raw:
            sdp_body = raw.split("\r\n\r\n", 1)[1][:4096]

        return RTSPProbe(
            methods=[m.strip() for m in public.split(",") if m.strip()],
            public_header=public or None,
            server_header=server or None,
            sdp_body=sdp_body,
            status_code=status_code,
            status_text=status_text,
            response_time_ms=elapsed_ms,
            auth_header=headers.get("www-authenticate"),
            auth_realm=realm,
            auth_nonce=nonce,
            auth_method=method,
        )
    except Exception as e:
        logger.debug(f"RTSP probe {ip}:{port}{path} falhou: {e}")
        return None
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def probe_rtsp_no_auth(
    camera: Camera,
    paths: list[str] | None = None,
    timeout: float = 3.0,
    max_workers: int = 20,
) -> Camera:
    """Técnica 1: Tentar RTSP sem auth em vários paths (paralelo).

    Se algum path responder 200 OK, marca a câmara como LIVE.
    Para no primeiro 200 ou 401 encontrado.

    Args:
        camera: Camera a testar.
        paths: Lista de paths (default: paths do fabricante + genérico).
        timeout: Timeout por probe.
        max_workers: Threads paralelas (default: 20).

    Returns:
        Camera atualizada (in-place).
    """
    if paths is None:
        paths = get_paths_for_vendor(camera.vendor)[:10]  # Top 10

    if not paths:
        return camera

    def _try(path: str) -> tuple[str, RTSPProbe | None]:
        try:
            return path, probe_rtsp(camera.ip, camera.port, path, timeout=timeout)
        except Exception as e:
            logger.debug(f"probe_rtsp_no_auth {camera.ip}{path} err: {e}")
            return path, None

    # Testar em paralelo até encontrar 200/401
    found_200: tuple[str, RTSPProbe] | None = None
    found_401: tuple[str, RTSPProbe] | None = None

    with ThreadPoolExecutor(max_workers=min(max_workers, len(paths))) as ex:
        futures = [ex.submit(_try, p) for p in paths]
        try:
            for fut in as_completed(futures, timeout=timeout + 2):
                path, probe = fut.result()
                if probe is None:
                    continue
                if probe.status_code == 200 and found_200 is None:
                    found_200 = (path, probe)
                    # Cancela resto
                    for f in futures:
                        f.cancel()
                    break
                if probe.status_code == 401 and found_401 is None:
                    found_401 = (path, probe)
                    # Não cancela ainda — pode haver 200 mais cedo
        except TimeoutError:
            pass

    # Processar resultado: 200 tem prioridade, depois 401
    if found_200:
        path, probe = found_200
        camera.status = CameraStatus.LIVE
        camera.auth_required = False
        camera.auth_success = True
        camera.auth_user = None
        camera.auth_pass = None
        camera.rtsp_path = path
        camera.rtsp_url = f"rtsp://{camera.ip}:{camera.port}{path}"
        camera.rtsp_probe = probe
        camera.access_method = AccessMethod.RTSP_NO_AUTH
        camera.raw_banner = (camera.raw_banner or "") + "\n" + (probe.server_header or "")
        camera.tags.append("no-auth")
        logger.info(
            f"🟢 LIVE (no-auth) {camera.ip}:{camera.port}{path} ({probe.response_time_ms:.0f}ms)"
        )
        return camera

    if found_401:
        path, probe = found_401
        camera.rtsp_probe = probe
        camera.rtsp_path = path
        camera.auth_required = True
        camera.status = CameraStatus.AUTH_REQUIRED
        logger.debug(f"🔒 AUTH required {camera.ip}:{camera.port}{path}")
        return camera

    return camera


# =====================================================================
# TÉCNICA 3 — HTTP Snapshot
# =====================================================================


def find_snapshot(
    ip: str,
    ports: list[int] | None = None,
    paths: list[str] | None = None,
    timeout: float = 3.0,
    max_workers: int = 10,
) -> tuple[str, int, str] | None:
    """Técnica 3: Procura snapshot HTTP acessível.

    Args:
        ip: IP da câmara.
        ports: Portas HTTP a testar (default: HTTP_PORTS).
        paths: Paths a testar (default: HTTP_SNAPSHOT_PATHS).
        timeout: Timeout por pedido.
        max_workers: Threads paralelas (default: 10).

    Returns:
        Tupla (url, port, content_type) ou None.
    """
    if ports is None:
        ports = HTTP_PORTS
    if paths is None:
        paths = HTTP_SNAPSHOT_PATHS

    targets: list[tuple[str, int]] = [(p, port) for port in ports for p in paths]

    def _try(target: tuple[str, int]) -> tuple[str, int, str] | None:
        path, port = target
        url = f"http://{ip}:{port}{path}"
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                stream=True,
                allow_redirects=True,
                headers={"User-Agent": "Procurador/1.0"},
            )
            if resp.status_code == 200:
                ct = resp.headers.get("Content-Type", "")
                if "image" in ct or "octet-stream" in ct or "jpeg" in ct or "jpg" in ct:
                    logger.info(f"📸 Snapshot found: {url} ({ct})")
                    resp.close()
                    return (url, port, ct)
            resp.close()
        except requests.exceptions.RequestException:
            pass
        except Exception as e:
            logger.debug(f"snapshot {url} err: {e}")
        return None

    with ThreadPoolExecutor(max_workers=min(max_workers, len(targets))) as ex:
        futures = {ex.submit(_try, t): t for t in targets}
        for fut in as_completed(futures):
            result = fut.result()
            if result is not None:
                # Cancel pending futures
                for f in futures:
                    f.cancel()
                return result

    return None


# =====================================================================
# TÉCNICA 4 — HTTP Admin + creds default
# =====================================================================

# Keywords de deteção de login page
_LOGIN_KEYWORDS: list[str] = [
    "login",
    "sign in",
    "signin",
    "user",
    "password",
    "auth",
    "authentication",
    "log in",
    "username",
    "passwd",
    "pwd",
]


# Dicionário de campos de form comuns (user/pass) para tentar
_LOGIN_FORM_FIELDS: list[tuple[str, str]] = [
    ("username", "password"),
    ("user", "password"),
    ("user", "passwd"),
    ("user", "pass"),
    ("login", "password"),
    ("Username", "Password"),
    ("admin", "admin"),
    ("userName", "password"),
    ("user_name", "password"),
    ("login_user", "login_pass"),
    ("ID", "PassWord"),
    ("userid", "userpass"),
]


def _detect_login_page(html: str) -> bool:
    """Deteta se o HTML é uma página de login."""
    if not html:
        return False
    html_lower = html.lower()
    return any(kw in html_lower for kw in _LOGIN_KEYWORDS)


def _extract_form_fields(html: str) -> dict[str, str]:
    """Extrai nomes de campos de formulário do HTML (heurística simples)."""
    import re

    fields: dict[str, str] = {}
    # Procura inputs com name=...
    for m in re.finditer(
        r'<input[^>]+name=["\']([^"\']+)["\'][^>]*type=["\']([^"\']+)["\']', html, re.IGNORECASE
    ):
        name, t = m.group(1), m.group(2).lower()
        if t in ("text", "password", "email"):
            fields[name] = ""
    for m in re.finditer(
        r'<input[^>]+type=["\']([^"\']+)["\'][^>]*name=["\']([^"\']+)["\']', html, re.IGNORECASE
    ):
        t, name = m.group(1).lower(), m.group(2)
        if t in ("text", "password", "email") and name not in fields:
            fields[name] = ""
    return fields


def _try_login(
    session: requests.Session,
    url: str,
    user_field: str,
    pass_field: str,
    user: str,
    password: str,
    timeout: float,
) -> requests.Response | None:
    """Tenta um login. Devolve a Response se sucesso, None caso contrário."""
    try:
        # Primeiro obter cookies / csrf
        session.get(url, timeout=timeout)
        # Login POST
        data = {user_field: user, pass_field: password, "submit": "1", "Login": "Login"}
        resp = session.post(
            url,
            data=data,
            timeout=timeout,
            allow_redirects=False,
        )
        # Sucesso = 302 (redirect) ou 200 com cookies de sessão
        if resp.status_code in (301, 302):
            return resp
        if resp.status_code == 200:
            # Heurística: se setou cookies de sessão, é sucesso
            if session.cookies and any(
                "session" in c.name.lower() or "sid" in c.name.lower() or "auth" in c.name.lower()
                for c in session.cookies
            ):
                return resp
            # Senão, verificar se ainda está na página de login
            text_lower = resp.text.lower()
            login_failed_markers = ["invalid", "incorrect", "failed", "wrong", "error", "denied"]
            if not any(m in text_lower for m in login_failed_markers):
                return resp
        return None
    except requests.exceptions.RequestException:
        return None


def probe_http_admin(
    camera: Camera,
    creds: list[tuple[str, str]] | None = None,
    timeout: float = 3.0,
    max_login_attempts: int = 20,
) -> Camera:
    """Técnica 4: Testa HTTP admin e tenta creds default.

    Testa ports em paralelo; para cada port encontrada com login page,
    tenta credenciais.

    Args:
        camera: Camera a testar.
        creds: Lista de (user, pass). Se None, usa os primeiros 20.
        timeout: Timeout HTTP.
        max_login_attempts: Limite de tentativas de login.

    Returns:
        Camera atualizada.
    """
    from procurador.core.wordlists import GENERIC_CREDS

    if creds is None:
        creds = GENERIC_CREDS[:max_login_attempts]

    def _scan_port(port: int) -> tuple[int, requests.Response | None]:
        base_url = f"http://{camera.ip}:{port}"
        try:
            resp = requests.get(
                base_url,
                timeout=timeout,
                allow_redirects=True,
                headers={"User-Agent": "Procurador/1.0"},
            )
            return port, resp
        except requests.exceptions.RequestException:
            return port, None
        except Exception as e:
            logger.debug(f"http admin {base_url} err: {e}")
            return port, None

    # Testar todas as ports em paralelo
    with ThreadPoolExecutor(max_workers=min(8, len(HTTP_PORTS))) as ex:
        port_results = list(ex.map(_scan_port, HTTP_PORTS))

    # Processar respostas (ordem por port)
    for port, resp in port_results:
        if resp is None or resp.status_code >= 400:
            continue

        base_url = f"http://{camera.ip}:{port}"
        camera.http_status = resp.status_code
        camera.http_url = base_url
        camera.http_title = extract_title(resp.text)
        camera.http_server = resp.headers.get("Server")

        # Se não tem HTML ou é só página estática, skip
        if not _detect_login_page(resp.text):
            continue

        # Tentar login
        login_url = base_url
        combined_html = resp.text
        for login_path in HTTP_ADMIN_PATHS:
            if login_path in ("/", "/index.html", "/index.htm", "/web/", "/web/index.html"):
                continue
            url = f"{base_url}{login_path}"
            try:
                r2 = requests.get(url, timeout=timeout, allow_redirects=False)
            except requests.exceptions.RequestException:
                continue
            if r2.status_code not in (200, 301, 302):
                continue
            login_url = url
            combined_html = resp.text + "\n" + r2.text
            break

        # Detetar campos do form
        fields = _extract_form_fields(combined_html)
        if fields:
            user_field = None
            pass_field = None
            for name in fields:
                name_lower = name.lower()
                if "user" in name_lower or "login" in name_lower or name == "name":
                    user_field = user_field or name
                if "pass" in name_lower or "pwd" in name_lower:
                    pass_field = pass_field or name
            user_field = user_field or "username"
            pass_field = pass_field or "password"
        else:
            user_field, pass_field = "username", "password"

        # Tentar creds
        session = requests.Session()
        session.headers["User-Agent"] = "Procurador/1.0"
        for user, pwd in creds[:max_login_attempts]:
            try:
                result = _try_login(session, login_url, user_field, pass_field, user, pwd, timeout)
            except Exception as e:
                logger.debug(f"login {login_url} err: {e}")
                result = None
            if result is not None:
                camera.http_login_url = login_url
                camera.auth_user = user
                camera.auth_pass = pwd
                camera.auth_success = True
                camera.auth_method = "form"
                camera.access_method = AccessMethod.HTTP_ADMIN
                camera.status = CameraStatus.WEB_ONLY
                camera.tags.append("http-admin")
                logger.info(f"🔓 HTTP admin login OK: {camera.ip}:{port} {user}:{pwd}")
                return camera

    return camera


# =====================================================================
# TÉCNICA 6 — Portas alternativas
# =====================================================================


def _test_port(ip: str, port: int, timeout: float = 2.0) -> bool:
    """Testa se uma porta está aberta (TCP connect)."""
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        sock.close()
        return True
    except (TimeoutError, OSError):
        return False
    except Exception:
        return False
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def scan_alt_ports(
    ip: str,
    ports: list[int] | None = None,
    timeout: float = 2.0,
    max_workers: int = 10,
) -> list[int]:
    """Técnica 6: Testa portas RTSP alternativas em paralelo.

    Args:
        ip: Endereço IP.
        ports: Lista de portas (default: RTSP_PORTS).
        timeout: Timeout por porta.
        max_workers: Threads paralelas.

    Returns:
        Lista de portas abertas.
    """
    if ports is None:
        ports = RTSP_PORTS

    open_ports: list[int] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(ports))) as ex:
        futures = {ex.submit(_test_port, ip, p, timeout): p for p in ports}
        for fut in as_completed(futures):
            port = futures[fut]
            try:
                if fut.result():
                    open_ports.append(port)
                    logger.debug(f"🔌 Port {ip}:{port} OPEN")
            except Exception as e:
                logger.debug(f"port scan err {ip}:{port}: {e}")

    return sorted(open_ports)


# =====================================================================
# Scanner pipeline (combina técnicas)
# =====================================================================


def scan_camera_basic(
    camera: Camera,
    config,
) -> Camera:
    """Pipeline de probe básico (Técnicas 1, 3, 4, 6).

    Args:
        camera: Camera (será mutada in-place).
        config: ScanConfig.

    Returns:
        Camera atualizada.
    """
    camera.status = CameraStatus.SCANNING

    # 1. Probe RTSP sem auth (Técnica 1) - tenta paths do vendor
    if config.rtsp_brute_paths:
        probe_rtsp_no_auth(
            camera,
            paths=get_paths_for_vendor(camera.vendor)[: config.rtsp_brute_max_paths],
            timeout=config.rtsp_probe_timeout,
        )
    else:
        probe_rtsp_no_auth(camera, paths=["/"], timeout=config.rtsp_probe_timeout)

    # Se já está LIVE, capturar screenshot opcional e sair cedo
    if camera.status == CameraStatus.LIVE and not config.stream_capture:
        return camera

    # 2. Portas alternativas (Técnica 6) - rápido
    if camera.status != CameraStatus.LIVE:
        alt_open = scan_alt_ports(camera.ip, timeout=min(config.rtsp_probe_timeout, 1.0))
        if alt_open:
            camera.ports_open = sorted(set(camera.ports_open + alt_open))
            for port in alt_open:
                if port == camera.port:
                    continue
                # Tentar RTSP na porta alternativa
                probe = probe_rtsp(camera.ip, port, "/", timeout=config.rtsp_probe_timeout)
                if probe and probe.status_code == 200:
                    old_port = camera.port
                    camera.port = port
                    camera.rtsp_url = f"rtsp://{camera.ip}:{port}/"
                    camera.rtsp_path = "/"
                    camera.status = CameraStatus.LIVE
                    camera.access_method = AccessMethod.ALT_PORT
                    camera.tags.append(f"alt-port:{port}")
                    logger.info(f"🟢 LIVE (alt port) {camera.ip}:{old_port} -> {port}")
                    break
                elif probe and probe.status_code == 401:
                    # Path existe, mas precisa auth
                    if camera.status == CameraStatus.PENDING:
                        camera.port = port
                        camera.rtsp_probe = probe
                        camera.status = CameraStatus.AUTH_REQUIRED
                        camera.tags.append(f"alt-port:{port}")

    # 3. HTTP Snapshot (Técnica 3) - se RTSP falhou
    if camera.status not in (CameraStatus.LIVE,):
        snap = find_snapshot(camera.ip, timeout=config.http_timeout)
        if snap:
            camera.http_snapshot_url = snap[0]
            if camera.status not in (CameraStatus.AUTH_REQUIRED,):
                camera.status = CameraStatus.WEB_ONLY
                camera.access_method = AccessMethod.HTTP_SNAPSHOT
                camera.tags.append("snapshot")

    # 4. HTTP Admin (Técnica 4) - se tudo falhou
    if camera.status not in (CameraStatus.LIVE, CameraStatus.AUTH_REQUIRED):
        if config.http_admin_brute:
            probe_http_admin(
                camera,
                timeout=config.http_timeout,
                max_login_attempts=config.http_max_login_attempts,
            )

    # 5. Estado final
    if camera.status == CameraStatus.SCANNING:
        if not camera.is_accessible:
            camera.status = CameraStatus.CLOSED

    return camera
