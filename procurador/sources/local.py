"""
Scanner de rede local.

- ARP scan (Scapy) — descobre hosts na LAN
- WS-Discovery (ONVIF) — descobre câmaras ONVIF
- TCP connect scan rápido — alternativo a Scapy no Windows
"""

from __future__ import annotations

import logging
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import ip_network

from procurador.core.models import Camera, CameraStatus, SourceType

logger = logging.getLogger(__name__)


# =====================================================================
# ARP scan (Scapy)
# =====================================================================


def scan_arp_scapy(subnet: str = "192.168.1.0/24", timeout: int = 3) -> list[dict]:
    """ARP scan via Scapy.

    Args:
        subnet: Sub-rede (CIDR).
        timeout: Timeout do scan em segundos.

    Returns:
        Lista de dicts {ip, mac}.
    """
    hosts: list[dict] = []
    try:
        from scapy.all import ARP, Ether, srp

        arp = ARP(pdst=subnet)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp
        result = srp(packet, timeout=timeout, verbose=0)[0]

        for _sent, received in result:
            hosts.append(
                {
                    "ip": received.psrc,
                    "mac": received.hwsrc,
                }
            )
        logger.info(f"ARP scan (scapy): {len(hosts)} hosts em {subnet}")
    except ImportError:
        logger.warning("Scapy não instalado")
    except Exception as e:
        logger.warning(f"ARP scan (scapy) falhou: {e}")
    return hosts


# =====================================================================
# ARP scan fallback (Windows - arp -a + nbtstat)
# =====================================================================


def scan_arp_windows() -> list[dict]:
    """Fallback para Windows: usa `arp -a` para listar hosts conhecidos."""
    hosts: list[dict] = []
    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return hosts

        for line in result.stdout.splitlines():
            # Formato típico: "  192.168.1.1        aa-bb-cc-dd-ee-ff     dynamic"
            parts = line.split()
            if len(parts) >= 2:
                ip = parts[0]
                if _is_valid_ipv4(ip):
                    mac = parts[1].replace("-", ":")
                    if mac.count(":") == 5:
                        hosts.append({"ip": ip, "mac": mac})
        logger.info(f"ARP scan (arp -a): {len(hosts)} hosts")
    except Exception as e:
        logger.debug(f"arp -a err: {e}")
    return hosts


def _is_valid_ipv4(s: str) -> bool:
    """Verifica se string é IPv4."""
    import ipaddress

    try:
        ipaddress.IPv4Address(s)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False


# =====================================================================
# TCP scan rápido
# =====================================================================


def _tcp_connect(ip: str, port: int, timeout: float = 1.0) -> bool:
    """Testa porta via TCP connect."""
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


def scan_rtsp_ports(
    subnet_cidr: str, ports: list[int], timeout: float = 1.0, max_workers: int = 50
) -> list[dict]:
    """Scan IPs/portas RTSP em paralelo.

    Returns:
        Lista de {ip, port, mac=None}.
    """
    network = ip_network(subnet_cidr, strict=False)
    targets: list[tuple[str, int]] = []
    for ip in network.hosts():
        for port in ports:
            targets.append((str(ip), port))

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_tcp_connect, ip, port, timeout): (ip, port) for ip, port in targets}
        for fut in as_completed(futures):
            ip_str = str(futures[fut][0])
            port = futures[fut][1]
            try:
                if fut.result():
                    results.append({"ip": ip, "port": port, "mac": None})
            except Exception as e:
                logger.debug(f"tcp scan err: {e}")
    return results


# =====================================================================
# WS-Discovery
# =====================================================================


def scan_ws_discovery(timeout: int = 4) -> list[dict]:
    """Descobre câmaras via WS-Discovery (ONVIF)."""
    from procurador.core.onvif import onvif_discover

    return onvif_discover(timeout)


# =====================================================================
# Orquestrador
# =====================================================================


def scan_local_network(
    subnet: str = "192.168.1.0/24",
    onvif: bool = True,
    arp_timeout: int = 3,
) -> list[Camera]:
    """Pipeline completo de scan local.

    Args:
        subnet: Sub-rede (CIDR).
        onvif: Se True, faz WS-Discovery para ONVIF.
        arp_timeout: Timeout ARP.

    Returns:
        Lista de câmaras encontradas na LAN.
    """
    cameras: list[Camera] = []

    # 1. ARP (Scapy, com fallback arp -a)
    hosts = scan_arp_scapy(subnet, arp_timeout)
    if not hosts:
        hosts = scan_arp_windows()

    # Cria cameras para cada host (porta default 554)
    for h in hosts:
        cameras.append(
            Camera(
                ip=h["ip"],
                port=554,
                source=SourceType.LOCAL_ARP,
                mac_address=h.get("mac"),
                status=CameraStatus.PENDING,
            )
        )

    # 2. ONVIF WS-Discovery
    if onvif:
        try:
            devices = scan_ws_discovery(timeout=4)
            for d in devices:
                for ip in d.get("ips", []):
                    # Evitar duplicar
                    if not any(c.ip == ip for c in cameras):
                        cameras.append(
                            Camera(
                                ip=ip,
                                port=80,
                                source=SourceType.LOCAL_ONVIF,
                                onvif_supported=True,
                                status=CameraStatus.PENDING,
                            )
                        )
        except Exception as e:
            logger.warning(f"WS-Discovery falhou: {e}")

    # 3. TCP scan rápido nas portas RTSP comuns (só se subnet pequeno)
    network = ip_network(subnet, strict=False)
    if network.num_addresses <= 1024:  # /22 ou menor
        rtsp_hits = scan_rtsp_ports(subnet, [554, 8554], timeout=0.8, max_workers=50)
        for hit in rtsp_hits:
            ip, port = hit["ip"], hit["port"]
            existing = next((c for c in cameras if c.ip == ip), None)
            if existing:
                if port not in existing.ports_open:
                    existing.ports_open.append(port)
            else:
                cameras.append(
                    Camera(
                        ip=ip,
                        port=port,
                        source=SourceType.LOCAL_ARP,
                        status=CameraStatus.PENDING,
                    )
                )

    logger.info(f"Scan local: {len(cameras)} câmaras encontradas em {subnet}")
    return cameras
