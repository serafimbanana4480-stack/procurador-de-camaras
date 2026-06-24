"""
Testes de performance do pipeline.

Garante que o scanner é rápido para uso prático.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from procurador.core.models import Camera, CameraStatus, ScanConfig
from procurador.core.scanner import scan_camera_basic

# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture(scope="module")
def rtsp_server():
    """Mini RTSP server que responde /live com 200 OK."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 18556))
    server.listen(5)
    server.settimeout(15.0)

    response_200 = (
        b"RTSP/1.0 200 OK\r\n"
        b"CSeq: 1\r\n"
        b"Server: PytestTest\r\n"
        b"Public: DESCRIBE, SETUP, TEARDOWN\r\n"
        b"\r\n"
        b"v=0\r\n"
    )
    response_404 = b"RTSP/1.0 404 Not Found\r\nCSeq: 1\r\n\r\n"
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except TimeoutError:
                break
            try:
                req = conn.recv(4096)
                if b"/live" in req:
                    conn.sendall(response_200)
                else:
                    conn.sendall(response_404)
            except Exception:
                pass
            finally:
                conn.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    time.sleep(0.3)

    yield 18556

    stop.set()
    server.close()
    t.join(timeout=2)


@pytest.fixture
def fast_config() -> ScanConfig:
    """Config com timeouts curtos para testes."""
    return ScanConfig(
        rtsp_probe_timeout=0.3,
        http_timeout=0.3,
        alt_ports=[],  # sem alt ports para acelerar
    )


# =====================================================================
# Testes
# =====================================================================


def test_live_camera_fast(rtsp_server, fast_config):
    """Câmara LIVE deve ser encontrada em <2s."""
    cam = Camera(ip="127.0.0.1", port=rtsp_server)
    t0 = time.time()
    cam = scan_camera_basic(cam, fast_config)
    elapsed = time.time() - t0

    assert cam.status == CameraStatus.LIVE
    # Aceita qualquer path comum de stream que comece com /live
    assert cam.rtsp_path.startswith("/live"), f"Path inesperado: {cam.rtsp_path}"
    assert elapsed < 2.0, f"LIVE levou {elapsed:.2f}s (esperado <2s)"


def test_closed_port_under_15s(fast_config):
    """IP fechado deve ser fechado em <15s."""
    cam = Camera(ip="127.0.0.1", port=1)
    t0 = time.time()
    cam = scan_camera_basic(cam, fast_config)
    elapsed = time.time() - t0

    assert cam.status == CameraStatus.CLOSED
    assert elapsed < 15.0, f"CLOSED levou {elapsed:.2f}s (esperado <15s)"


def test_multiple_cameras_parallel(rtsp_server, fast_config):
    """3 câmaras em paralelo devem completar em <20s."""
    from concurrent.futures import ThreadPoolExecutor

    targets = [
        ("127.0.0.1", rtsp_server),  # LIVE
        ("127.0.0.1", 1),  # closed
        ("127.0.0.1", 2),  # closed
    ]

    def scan_one(args):
        ip, port = args
        cam = Camera(ip=ip, port=port)
        return scan_camera_basic(cam, fast_config)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(scan_one, targets))
    elapsed = time.time() - t0

    assert results[0].status == CameraStatus.LIVE
    assert results[1].status == CameraStatus.CLOSED
    assert results[2].status == CameraStatus.CLOSED
    assert elapsed < 20.0, f"3 paralelo levou {elapsed:.2f}s (esperado <20s)"


def test_live_response_under_500ms(rtsp_server):
    """Probe RTSP direto a câmara LIVE < 500ms."""
    from procurador.core.scanner import probe_rtsp

    t0 = time.time()
    probe = probe_rtsp("127.0.0.1", rtsp_server, "/live", timeout=0.5)
    elapsed = time.time() - t0

    assert probe is not None
    assert probe.status_code == 200
    assert elapsed < 0.5, f"probe levou {elapsed:.2f}s"
