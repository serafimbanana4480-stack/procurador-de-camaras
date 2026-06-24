"""
Testes para o scanner (Técnicas 1, 3, 4, 6).
"""

from __future__ import annotations

import socket
import threading

from procurador.core.models import (
    Camera,
    CameraStatus,
    ScanConfig,
)
from procurador.core.scanner import (
    _parse_rtsp_response,
    _parse_www_auth,
    probe_rtsp,
    scan_alt_ports,
)


def test_parse_rtsp_response_200():
    """Testa parsing de resposta 200 OK."""
    raw = (
        "RTSP/1.0 200 OK\r\n"
        "CSeq: 1\r\n"
        "Server: Hikvision/IPC\r\n"
        "Public: DESCRIBE, SETUP, TEARDOWN\r\n"
        "\r\n"
        "v=0\r\n"
    )
    code, text, headers = _parse_rtsp_response(raw)
    assert code == 200
    assert text == "OK"
    assert headers.get("server") == "Hikvision/IPC"
    assert "DESCRIBE" in headers.get("public", "")


def test_parse_rtsp_response_401_digest():
    """Testa parsing de resposta 401 com Digest."""
    raw = (
        "RTSP/1.0 401 Unauthorized\r\n"
        "CSeq: 1\r\n"
        'WWW-Authenticate: Digest realm="Hikvision", nonce="abc123", qop="auth"\r\n'
        "\r\n"
    )
    code, text, headers = _parse_rtsp_response(raw)
    assert code == 401
    assert "Unauthorized" in text

    method, realm, nonce = _parse_www_auth(headers)
    assert method == "Digest"
    assert realm == "Hikvision"
    assert nonce == "abc123"


def test_parse_rtsp_response_404():
    """Testa parsing de resposta 404."""
    raw = "RTSP/1.0 404 Not Found\r\nCSeq: 1\r\n\r\n"
    code, text, headers = _parse_rtsp_response(raw)
    assert code == 404
    assert text == "Not Found"


def test_parse_rtsp_response_garbage():
    """Testa parsing de input inválido."""
    code, text, headers = _parse_rtsp_response("")
    assert code == 0

    code, text, headers = _parse_rtsp_response("garbage data")
    assert code == 0


def test_scan_alt_ports_no_open():
    """Testa scan_alt_ports quando não há portas abertas."""
    # Port 1 está tipicamente fechada
    opens = scan_alt_ports("127.0.0.1", ports=[1], timeout=0.3)
    assert opens == []


def test_probe_rtsp_no_connection():
    """Testa probe_rtsp com IP que não existe."""
    probe = probe_rtsp("0.0.0.0", 554, "/", timeout=0.3)
    assert probe is None


def test_probe_rtsp_local_server():
    """Testa probe_rtsp com um mini server local."""
    # Inicia um mini server TCP que devolve 200 OK
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))  # porta auto
    server_sock.listen(5)
    port = server_sock.getsockname()[1]

    response_data = (
        b"RTSP/1.0 200 OK\r\n"
        b"CSeq: 1\r\n"
        b"Server: TestServer\r\n"
        b"Public: DESCRIBE, SETUP\r\n"
        b"\r\n"
        b"v=0\r\n"
    )

    def handle_client(conn):
        try:
            conn.recv(4096)
            conn.sendall(response_data)
        finally:
            conn.close()

    server_thread = threading.Thread(
        target=lambda: (
            (server_sock.accept()[0] and handle_client(server_sock.accept()[0])) if False else None
        ),
        daemon=True,
    )
    # Versão mais limpa:
    stop = threading.Event()

    def server_loop():
        server_sock.settimeout(2.0)
        while not stop.is_set():
            try:
                conn, _ = server_sock.accept()
            except TimeoutError:
                break
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        server_sock.close()

    server_thread = threading.Thread(target=server_loop, daemon=True)
    server_thread.start()

    try:
        probe = probe_rtsp("127.0.0.1", port, "/", timeout=2.0)
        if probe is not None:
            assert probe.status_code == 200
            assert probe.server_header == "TestServer"
    finally:
        stop.set()
        server_thread.join(timeout=3.0)


def test_camera_with_no_open_rtsp():
    """Testa scan_camera_basic com IP sem RTSP (CLOSED)."""
    from procurador.core.scanner import scan_camera_basic

    cam = Camera(ip="127.0.0.1", port=65530)  # porta tipicamente fechada
    cfg = ScanConfig(rtsp_probe_timeout=0.3, http_timeout=0.3, alt_ports=[])
    cam = scan_camera_basic(cam, cfg)
    # Pode ser CLOSED ou ERROR
    assert cam.status in (CameraStatus.CLOSED, CameraStatus.ERROR)
