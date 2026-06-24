"""
Testes para o módulo models.py.
"""

from __future__ import annotations

import json

from procurador.core.models import (
    Camera,
    CameraStatus,
    GeoLocation,
    RTSPProbe,
    ScanConfig,
    SourceType,
)


def test_camera_creation():
    """Testa criação básica de Camera."""
    cam = Camera(ip="1.2.3.4", port=554)
    assert cam.ip == "1.2.3.4"
    assert cam.port == 554
    assert cam.status == CameraStatus.PENDING
    assert cam.source == SourceType.CENSYS


def test_camera_to_dict_from_dict(sample_camera_live):
    """Testa serialização roundtrip."""
    d = sample_camera_live.to_dict()
    assert d["ip"] == "192.168.1.10"
    assert d["status"] == "live"
    assert d["vendor"] == "Hikvision"
    assert d["geo"]["country"] == "Portugal"
    assert d["resolution"] == "1920x1080"

    cam2 = Camera.from_dict(d)
    assert cam2.ip == sample_camera_live.ip
    assert cam2.vendor == sample_camera_live.vendor
    assert cam2.geo.country == sample_camera_live.geo.country
    assert cam2.status == sample_camera_live.status
    assert cam2.stream.width == 1920


def test_camera_country_flag():
    """Testa emoji de bandeira."""
    cam = Camera(
        ip="1.2.3.4",
        geo=GeoLocation(country="Portugal", country_code="PT"),
    )
    assert cam.country_flag == "🇵🇹"

    cam_empty = Camera(ip="1.2.3.4")
    assert cam_empty.country_flag == ""


def test_camera_location_str():
    """Testa string de localização."""
    cam = Camera(
        ip="1.2.3.4",
        geo=GeoLocation(country="Portugal", country_code="PT", city="Lisboa"),
    )
    assert "Lisboa" in cam.location_str
    assert "Portugal" in cam.location_str

    cam_unknown = Camera(ip="1.2.3.4")
    assert cam_unknown.location_str == "Unknown"


def test_camera_is_accessible():
    """Testa propriedade is_accessible."""
    assert Camera(ip="1", status=CameraStatus.LIVE).is_accessible
    assert Camera(ip="1", status=CameraStatus.AUTH_REQUIRED).is_accessible
    assert Camera(ip="1", status=CameraStatus.WEB_ONLY).is_accessible
    assert not Camera(ip="1", status=CameraStatus.CLOSED).is_accessible
    assert not Camera(ip="1", status=CameraStatus.ERROR).is_accessible
    assert not Camera(ip="1", status=CameraStatus.PENDING).is_accessible


def test_scan_result_calculate_stats(sample_scan_result):
    """Testa cálculo de stats."""
    r = sample_scan_result
    assert r.total_ips == 3
    assert r.accessible == 1
    assert r.auth_required == 1
    assert r.closed == 1
    assert r.live_streams == 1
    assert "Hikvision" in r.vendors
    assert "Dahua" in r.vendors
    assert "Unknown" in r.vendors
    assert "Portugal" in r.countries


def test_scan_result_to_json(tmp_path, sample_scan_result):
    """Testa export para JSON."""
    out = tmp_path / "scan.json"
    path = sample_scan_result.to_json(str(out))
    assert path == str(out)
    assert out.exists()

    with out.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["scan_id"] == "test-001"
    assert data["stats"]["total_ips"] == 3
    assert data["stats"]["accessible"] == 1


def test_scan_config_defaults():
    """Testa defaults do ScanConfig."""
    cfg = ScanConfig()
    assert cfg.censys_query == "services.service_name: RTSP"
    assert cfg.censys_max_pages == 5
    assert cfg.rtsp_probe_timeout == 3.0
    assert cfg.brute_enabled is True
    assert cfg.stream_capture is False
    assert 8554 in cfg.alt_ports  # 554 é a porta principal, não está em alt_ports


def test_rtsp_probe_creation():
    """Testa RTSPProbe."""
    p = RTSPProbe(
        methods=["DESCRIBE", "SETUP"],
        status_code=200,
        status_text="OK",
        server_header="Hikvision",
    )
    assert p.status_code == 200
    assert "DESCRIBE" in p.methods
    assert p.server_header == "Hikvision"
