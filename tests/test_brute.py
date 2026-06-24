"""
Testes para o módulo brute.py (credenciais).
"""

from __future__ import annotations

import hashlib

from procurador.core.brute import _build_digest_auth, _compute_digest_response
from procurador.core.wordlists import (
    get_creds_for_vendor,
    get_paths_for_vendor,
)


def test_get_paths_for_vendor_known():
    """Paths para vendor conhecido começam com vendor-specific."""
    paths = get_paths_for_vendor("Hikvision")
    assert "/Streaming/Channels/101" in paths
    assert len(paths) > 5


def test_get_paths_for_vendor_unknown():
    """Vendor desconhecido devolve paths genéricos."""
    paths = get_paths_for_vendor(None)
    assert "/live" in paths
    assert len(paths) > 0


def test_get_creds_for_vendor_known():
    """Creds para vendor conhecido começa com vendor-specific."""
    creds = get_creds_for_vendor("Hikvision", max_n=20)
    assert ("admin", "12345") in creds
    assert ("admin", "admin") in creds


def test_get_creds_for_vendor_unknown():
    """Creds para vendor desconhecido começa com top genéricos."""
    creds = get_creds_for_vendor(None, max_n=10)
    assert ("admin", "admin") in creds  # O mais comum


def test_get_creds_dedup():
    """Creds são deduplicados."""
    creds = get_creds_for_vendor("Hikvision", max_n=100)
    assert len(creds) == len(set(creds))


def test_compute_digest_response_known():
    """Testa cálculo Digest Auth com valores conhecidos."""
    response = _compute_digest_response(
        user="admin",
        realm="test",
        password="pass",
        method="DESCRIBE",
        uri="/live",
        nonce="abc",
    )
    ha1 = hashlib.md5(b"admin:test:pass").hexdigest()
    ha2 = hashlib.md5(b"DESCRIBE:/live").hexdigest()
    expected = hashlib.md5(f"{ha1}:abc:{ha2}".encode()).hexdigest()
    assert response == expected


def test_compute_digest_response_with_qop():
    """Testa cálculo Digest Auth com qop=auth."""
    response = _compute_digest_response(
        user="admin",
        realm="test",
        password="pass",
        method="DESCRIBE",
        uri="/live",
        nonce="abc",
        qop="auth",
        nc="00000001",
        cnonce="deadbeef",
    )
    ha1 = hashlib.md5(b"admin:test:pass").hexdigest()
    ha2 = hashlib.md5(b"DESCRIBE:/live").hexdigest()
    expected = hashlib.md5(f"{ha1}:abc:00000001:deadbeef:auth:{ha2}".encode()).hexdigest()
    assert response == expected


def test_build_digest_auth():
    """Testa construção do header Authorization Digest completo."""
    auth = _build_digest_auth(
        user="admin",
        password="pass",
        uri="/live",
        method="DESCRIBE",
        realm="test",
        nonce="abc",
        qop="auth",
    )
    assert auth.startswith("Digest ")
    assert 'username="admin"' in auth
    assert 'realm="test"' in auth
    assert 'nonce="abc"' in auth
    assert 'uri="/live"' in auth
    assert "response=" in auth
    assert "qop=auth" in auth
    assert "nc=" in auth
    assert "cnonce=" in auth
