"""
Fixtures partilhados para os testes do Procurador de Câmara.
"""

from __future__ import annotations

import pytest

from procurador.core.models import (
    AccessMethod,
    Camera,
    CameraStatus,
    GeoLocation,
    NetworkInfo,
    ScanConfig,
    ScanResult,
    StreamInfo,
)


@pytest.fixture
def sample_camera_live() -> Camera:
    """Câmara LIVE com info completa."""
    return Camera(
        ip="192.168.1.10",
        port=554,
        vendor="Hikvision",
        model="DS-2CD2",
        geo=GeoLocation(
            country="Portugal",
            country_code="PT",
            city="Lisboa",
            lat=38.72,
            lon=-9.14,
        ),
        network=NetworkInfo(isp="MEO", org="Altice"),
        status=CameraStatus.LIVE,
        access_method=AccessMethod.RTSP_NO_AUTH,
        auth_required=False,
        auth_success=True,
        rtsp_path="/Streaming/Channels/101",
        rtsp_url="rtsp://192.168.1.10:554/Streaming/Channels/101",
        stream=StreamInfo(codec="H264", width=1920, height=1080, fps=25.0),
        ports_open=[80, 554, 8080],
    )


@pytest.fixture
def sample_camera_auth() -> Camera:
    """Câmara que requer autenticação."""
    return Camera(
        ip="192.168.1.20",
        port=554,
        vendor="Dahua",
        status=CameraStatus.AUTH_REQUIRED,
        access_method=AccessMethod.RTSP_BRUTE,
        auth_required=True,
        auth_user="admin",
        auth_pass="admin",
        rtsp_url="rtsp://admin:admin@192.168.1.20:554/cam/realmonitor",
        rtsp_path="/cam/realmonitor",
    )


@pytest.fixture
def sample_camera_closed() -> Camera:
    """Câmara com porta fechada."""
    return Camera(
        ip="192.168.1.99",
        port=554,
        status=CameraStatus.CLOSED,
    )


@pytest.fixture
def sample_rtsp_banner_200() -> bytes:
    """Banner RTSP 200 OK com SDP."""
    return (
        b"RTSP/1.0 200 OK\r\n"
        b"CSeq: 1\r\n"
        b"Server: Hikvision/IPC\r\n"
        b"Public: DESCRIBE, SETUP, TEARDOWN, PLAY, PAUSE\r\n"
        b"Content-Type: application/sdp\r\n"
        b"\r\n"
        b"v=0\r\n"
        b"o=- 0 0 IN IP4 192.168.1.10\r\n"
        b"s=Session\r\n"
        b"c=IN IP4 192.168.1.10\r\n"
        b"t=0 0\r\n"
        b"m=video 0 RTP/AVP 96\r\n"
    )


@pytest.fixture
def sample_rtsp_banner_401() -> bytes:
    """Banner RTSP 401 com Digest Auth challenge."""
    return (
        b"RTSP/1.0 401 Unauthorized\r\n"
        b"CSeq: 1\r\n"
        b'WWW-Authenticate: Digest realm="Hikvision", nonce="abc123", qop="auth"\r\n'
        b"\r\n"
    )


@pytest.fixture
def sample_rtsp_banner_404() -> bytes:
    """Banner RTSP 404 Not Found."""
    return b"RTSP/1.0 404 Not Found\r\nCSeq: 1\r\n\r\n"


@pytest.fixture
def sample_scan_result(sample_camera_live, sample_camera_auth, sample_camera_closed) -> ScanResult:
    """ScanResult com 3 câmaras sintéticas."""
    r = ScanResult(
        scan_id="test-001",
        config=ScanConfig(),
        started_at=1000000.0,
        finished_at=1000050.0,
        cameras=[sample_camera_live, sample_camera_auth, sample_camera_closed],
    )
    r.calculate_stats()
    return r
