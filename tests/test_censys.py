"""
Testes para o módulo Censys.

Testa:
- identify_vendor
- query_builder
- _parse_censys_host
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from procurador.core.models import ScanConfig
from procurador.sources.censys import (
    _normalize_country,
    _parse_censys_host,
    identify_vendor,
    query_builder,
    search_censys,
)


def test_identify_vendor_hikvision():
    """Identifica Hikvision pelo banner."""
    assert identify_vendor("Server: Hikvision/IPC") == "Hikvision"
    assert identify_vendor("RTSP server running on hikvision") == "Hikvision"


def test_identify_vendor_dahua():
    """Identifica Dahua."""
    assert identify_vendor("Dahua Web Server") == "Dahua"
    assert identify_vendor("realmonitor IPC-HDW2231T") == "Dahua"


def test_identify_vendor_axis():
    """Identifica Axis."""
    assert identify_vendor("axis-media/media.amp") == "Axis"
    assert identify_vendor("AXIS VAPIX") == "Axis"


def test_identify_vendor_reolink():
    """Identifica Reolink."""
    assert identify_vendor("h264Preview_01_main") == "Reolink"


def test_identify_vendor_galayou():
    """Identifica GALAYOU."""
    assert identify_vendor("GALAYOU G2 server") == "GALAYOU"


def test_identify_vendor_unknown():
    """Devolve None se não reconhecido."""
    assert identify_vendor("random server") is None
    assert identify_vendor("") is None
    assert identify_vendor(None) is None


def test_query_builder_default():
    """Default query inclui RTSP."""
    q = query_builder()
    assert "RTSP" in q


def test_query_builder_with_country_code():
    """Query com código de país."""
    q = query_builder("PT")
    assert "PT" in q
    assert "country_code" in q


def test_query_builder_with_country_name():
    """Query com nome de país."""
    q = query_builder("Portugal")
    assert "PT" in q  # Normalizado para código


def test_query_builder_with_custom_query():
    """Query base customizada."""
    q = query_builder(base_query="services.port:554")
    assert "554" in q


def test_normalize_country():
    """Testa normalização de países."""
    assert _normalize_country("PT") == "PT"
    assert _normalize_country("Portugal") == "PT"
    assert _normalize_country("United States") == "US"
    assert _normalize_country("") is None
    assert _normalize_country(None) is None


def test_parse_censys_host_minimal():
    """Parse de host minimal (só IP e RTSP service)."""
    host = {
        "ip": "1.2.3.4",
        "services": [
            {"port": 554, "service_name": "RTSP", "banner": "Server: Hikvision"},
        ],
    }
    cam = _parse_censys_host(host)
    assert cam is not None
    assert cam.ip == "1.2.3.4"
    assert cam.port == 554
    assert cam.vendor == "Hikvision"


def test_parse_censys_host_with_location():
    """Parse de host com location."""
    host = {
        "ip": "1.2.3.4",
        "location": {
            "country": "Portugal",
            "country_code": "PT",
            "city": "Lisboa",
        },
        "services": [
            {"port": 554, "service_name": "RTSP"},
        ],
    }
    cam = _parse_censys_host(host)
    assert cam is not None
    assert cam.geo.country == "Portugal"
    assert cam.geo.country_code == "PT"
    assert cam.geo.city == "Lisboa"


def test_parse_censys_host_no_rtsp_returns_none():
    """Sem serviço RTSP/HTTP, devolve None."""
    host = {
        "ip": "1.2.3.4",
        "services": [
            {"port": 22, "service_name": "SSH"},
        ],
    }
    assert _parse_censys_host(host) is None


def test_parse_censys_host_no_ip_returns_none():
    """Sem IP, devolve None."""
    assert _parse_censys_host({}) is None
    assert _parse_censys_host({"services": []}) is None


def test_search_censys_no_api_id():
    """Sem API ID, log error e devolve generator vazio."""
    with patch.dict("os.environ", {}, clear=True):
        cams = list(search_censys(ScanConfig(censys_max_pages=1)))
    assert cams == []


def test_search_censys_no_secret_graceful():
    """Sem secret, log warning e devolve generator vazio."""
    with patch.dict("os.environ", {"CENSYS_API_ID": "abc123", "CENSYS_SECRET": ""}, clear=True):
        cams = list(search_censys(ScanConfig(censys_max_pages=1)))
    assert cams == []


def test_search_censys_with_api_credentials():
    """Com credenciais, usa CensysHosts."""
    with patch.dict("os.environ", {"CENSYS_API_ID": "abc123", "CENSYS_SECRET": "secret"}):
        with patch("censys.search.CensysHosts") as MockClient:
            mock_instance = MagicMock()
            mock_result = [
                {
                    "ip": "1.2.3.4",
                    "services": [{"port": 554, "service_name": "RTSP", "banner": "Hikvision"}],
                }
            ]
            # Suportar v1 e v2
            if hasattr(mock_instance, "v2"):
                mock_instance.v2.hosts.search.return_value = iter(mock_result)
            else:
                mock_instance.search.return_value = iter(mock_result)
            MockClient.return_value = mock_instance

            cams = list(search_censys(ScanConfig(censys_max_pages=1, censys_per_page=5)))

            assert len(cams) == 1
            assert cams[0].ip == "1.2.3.4"
            assert cams[0].vendor == "Hikvision"
