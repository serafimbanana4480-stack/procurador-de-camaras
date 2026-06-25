"""
GeoIP resolution — converte IP em localização geográfica.

Suporta duas fontes:
- ipinfo.io (token opcional, rate-limited)
- MaxMind GeoLite2 (requer base de dados local)

Cache em memória para evitar queries repetidas.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

from procurador.core.models import GeoLocation
from procurador.utils.helpers import retry

logger = logging.getLogger(__name__)


# =====================================================================
# Cache
# =====================================================================


class _Cache:
    """Cache em memória + disco (JSON simples)."""

    def __init__(self, cache_path: str = "data/geoip_cache.json"):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_path.exists():
            try:
                with self.cache_path.open("r", encoding="utf-8") as f:
                    self._mem = json.load(f)
            except Exception:
                self._mem = {}

    def _save(self) -> None:
        try:
            with self.cache_path.open("w", encoding="utf-8") as f:
                json.dump(self._mem, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"geoip cache save err: {e}")

    def get(self, ip: str) -> dict | None:
        return self._mem.get(ip)

    def set(self, ip: str, data: dict) -> None:
        self._mem[ip] = data
        # Salvar periodicamente — só se mudou muito
        if len(self._mem) % 50 == 0:
            self._save()


_cache = _Cache()


# =====================================================================
# ipinfo.io
# =====================================================================


@retry(exceptions=(requests.exceptions.RequestException,), tries=2, delay=0.5)
def _query_ipinfo(ip: str, token: str | None = None) -> dict | None:
    """Query ipinfo.io. Devolve dict com info ou None."""
    url = f"https://ipinfo.io/{ip}/json"
    headers = {"User-Agent": "Procurador/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            logger.warning("ipinfo.io rate limit")
        else:
            logger.debug(f"ipinfo {ip}: HTTP {resp.status_code}")
    except requests.exceptions.RequestException as e:
        logger.debug(f"ipinfo {ip} err: {e}")
    return None


def _parse_ipinfo_response(data: dict) -> GeoLocation:
    """Converte resposta ipinfo.io num GeoLocation."""
    geo = GeoLocation()
    geo.country = data.get("country")
    geo.country_code = data.get("country")
    geo.city = data.get("city")
    geo.region = data.get("region")
    geo.postal = data.get("postal")
    geo.timezone = data.get("timezone")

    loc_str = data.get("loc")
    if loc_str and "," in loc_str:
        try:
            lat, lon = loc_str.split(",", 1)
            geo.lat = float(lat)
            geo.lon = float(lon)
        except (ValueError, IndexError):
            pass
    return geo


# =====================================================================
# MaxMind GeoLite2 (opcional, requer base de dados)
# =====================================================================


def _query_maxmind(ip: str, db_path: str) -> GeoLocation | None:
    """Query MaxMind GeoLite2 (requer geoip2 + base de dados)."""
    try:
        import geoip2.database

        reader = geoip2.database.Reader(db_path)
        try:
            resp = reader.city(ip)
            return GeoLocation(
                country=resp.country.name,
                country_code=resp.country.iso_code,
                city=resp.city.name,
                region=resp.subdivisions.most_specific.name if resp.subdivisions else None,
                lat=resp.location.latitude,
                lon=resp.location.longitude,
                postal=resp.postal.code,
                timezone=resp.location.time_zone,
            )
        finally:
            reader.close()
    except ImportError:
        logger.debug("geoip2 não instalado")
    except FileNotFoundError:
        logger.debug(f"MaxMind DB not found: {db_path}")
    except Exception as e:
        logger.debug(f"maxmind {ip} err: {e}")
    return None


# =====================================================================
# Public API
# =====================================================================


class GeoIPResolver:
    """Resolve IP → GeoLocation usando ipinfo.io (default) ou MaxMind."""

    def __init__(
        self,
        ipinfo_token: str | None = None,
        maxmind_db: str | None = None,
        use_cache: bool = True,
        db: Any | None = None,
    ):
        self.token = ipinfo_token or os.environ.get("IPINFO_TOKEN")
        self.maxmind_db = maxmind_db
        self.use_cache = use_cache
        self._maxmind_available: bool | None = None
        self._db = db  # SQLite Database instance (opcional)

    def _check_db_cache(self, ip: str) -> GeoLocation | None:
        """Verificar cache SQLite."""
        if self._db is None:
            return None
        try:
            cached = self._db.get_geoip_cache(ip)
            if cached:
                return GeoLocation(
                    country=cached.get("country"),
                    country_code=cached.get("country_code"),
                    city=cached.get("city"),
                    region=cached.get("region"),
                    lat=cached.get("lat"),
                    lon=cached.get("lon"),
                )
        except Exception:
            pass
        return None

    def _save_db_cache(self, ip: str, geo: GeoLocation) -> None:
        """Guardar na cache SQLite."""
        if self._db is None or not geo.country_code:
            return
        try:
            self._db.set_geoip_cache(ip, {
                "country": geo.country,
                "country_code": geo.country_code,
                "city": geo.city,
                "region": geo.region,
                "lat": geo.lat,
                "lon": geo.lon,
            })
        except Exception:
            pass

    def resolve(self, ip: str) -> GeoLocation:
        """Resolve um IP num GeoLocation."""
        if not ip:
            return GeoLocation()

        # 1. Cache SQLite (prioritário, persistente)
        db_cached = self._check_db_cache(ip)
        if db_cached:
            return db_cached

        # 2. Cache em memória
        if self.use_cache:
            cached = _cache.get(ip)
            if cached:
                return _parse_ipinfo_response(cached)

        # 2. MaxMind (local, mais rápido)
        if self.maxmind_db:
            geo = _query_maxmind(ip, self.maxmind_db)
            if geo:
                return geo

        # 3. ipinfo.io
        if not self.token:
            # Tenta sem token (rate limit é baixo, ~50k/mês)
            pass

        data = _query_ipinfo(ip, self.token)
        if data:
            geo = _parse_ipinfo_response(data)
            if self.use_cache:
                _cache.set(ip, data)
            self._save_db_cache(ip, geo)
            return geo

        # 4. Empty
        return GeoLocation()

    def resolve_batch(self, ips: list[str]) -> dict[str, GeoLocation]:
        """Resolve múltiplos IPs."""
        result: dict[str, GeoLocation] = {}
        for ip in ips:
            result[ip] = self.resolve(ip)
            time.sleep(0.05)  # Throttle
        return result
