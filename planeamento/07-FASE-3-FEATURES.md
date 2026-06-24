# 07 — FASE 3: FEATURES AVANÇADAS

> Duração estimada: 2 dias
> Objetivo: Adicionar funcionalidades avançadas ao core

---

## 7.1 Stream Capture com OpenCV

### `procurador/core/stream.py`

```python
"""
Captura de streams RTSP com OpenCV.
Screenshots, info de stream, codec, resolução, fps.
"""
import logging
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2
import numpy as np

from procurador.core.models import Camera, CameraStatus, StreamInfo, ScanConfig

logger = logging.getLogger(__name__)


def capture_stream(
    camera: Camera,
    screenshot_dir: str = "data/screenshots",
    max_retries: int = 2,
) -> Camera:
    """
    Capturar um frame do stream RTSP.

    1. Abre VideoCapture com URL RTSP
    2. Lê 1 frame
    3. Guarda screenshot
    4. Extrai codec, resolução, fps
    5. Fecha stream
    """
    if not camera.rtsp_url or camera.status != CameraStatus.LIVE:
        return camera

    logger.debug(f"📸 Capturing {camera.ip}...")

    for attempt in range(max_retries):
        try:
            cap = cv2.VideoCapture(camera.rtsp_url)

            if not cap.isOpened():
                logger.debug(f"Failed to open stream for {camera.ip}")
                continue

            # Extrair propriedades do stream
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            codec_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = _decode_fourcc(codec_int)

            # Atualizar stream info
            camera.stream = StreamInfo(
                codec=codec,
                width=width,
                height=height,
                fps=fps,
            )

            # Ler 1 frame
            ret, frame = cap.read()

            if ret and frame is not None:
                # Guardar screenshot
                screenshot_dir_p = Path(screenshot_dir)
                screenshot_dir_p.mkdir(parents=True, exist_ok=True)

                filename = f"{camera.ip}_{int(time.time())}.png"
                filepath = screenshot_dir_p / filename
                cv2.imwrite(str(filepath), frame)
                camera.screenshot_path = str(filepath)

                logger.info(f"📸 Screenshot saved: {filename} ({width}x{height})")
            else:
                logger.debug(f"Could not read frame from {camera.ip}")

            cap.release()
            return camera

        except Exception as e:
            logger.debug(f"Stream capture error {camera.ip}: {e}")
            continue

    return camera


def _decode_fourcc(fourcc_int: int) -> str:
    """Descodificar int FOURCC para string codec."""
    try:
        return "".join(chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)).strip()
    except:
        return "Unknown"


def capture_batch(
    cameras: list[Camera],
    config: ScanConfig,
    screenshot_dir: str = "data/screenshots",
) -> list[Camera]:
    """
    Capturar screenshots de todas as câmaras LIVE em paralelo.
    """
    live_cams = [c for c in cameras if c.status == CameraStatus.LIVE and c.rtsp_url]
    if not live_cams:
        logger.info("📸 Nenhuma câmara live para capturar")
        return cameras

    logger.info(f"📸 Capturing {len(live_cams)} streams...")

    with ThreadPoolExecutor(max_workers=config.stream_threads) as executor:
        futures = {
            executor.submit(
                capture_stream,
                cam,
                screenshot_dir,
            ): cam.ip
            for cam in live_cams
        }

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                ip = futures[future]
                logger.error(f"Stream capture failed for {ip}: {e}")

    return cameras
```

---

## 7.2 Scan Local (LAN)

### `procurador/sources/local.py`

```python
"""
Scanner de rede local.
ARP scan + WS-Discovery (ONVIF) para descobrir câmaras na LAN.
"""
import logging
import time
from typing import Generator
from ipaddress import ip_network

from procurador.core.models import Camera, CameraStatus, SourceType, ScanConfig

logger = logging.getLogger(__name__)


def scan_arp(subnet: str = "192.168.1.0/24", timeout: int = 5) -> list[dict]:
    """
    ARP scan com scapy para descobrir hosts na rede.

    Returns: [{"ip": "192.168.1.1", "mac": "aa:bb:cc:dd:ee:ff"}, ...]
    """
    hosts = []
    try:
        from scapy.all import ARP, Ether, srp

        # Criar pacote ARP request
        arp = ARP(pdst=subnet)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp

        # Enviar e receber
        result = srp(packet, timeout=timeout, verbose=0)[0]

        for sent, received in result:
            hosts.append({
                "ip": received.psrc,
                "mac": received.hwsrc,
            })

        logger.info(f"📡 ARP scan: {len(hosts)} hosts encontrados em {subnet}")

    except ImportError:
        logger.warning("⚠️ Scapy não instalado. A instalar...")
        import subprocess
        subprocess.run(["pip", "install", "scapy"], capture_output=True)
        logger.info("✅ Scapy instalado. Executa novamente.")
    except Exception as e:
        logger.error(f"ARP scan error: {e}")

    return hosts


def scan_onvif(timeout: int = 4) -> list[dict]:
    """
    WS-Discovery multicast para descobrir dispositivos ONVIF.

    Envia probe multicast UDP para 239.255.255.250:3702
    """
    devices = []
    try:
        from onvif import ONVIFCamera
        from wsdiscovery import WSDiscovery

        wsd = WSDiscovery()
        wsd.start()
        services = wsd.searchServices(timeout=timeout)

        for service in services:
            for addr in service.getXAddrs():
                devices.append({
                    "url": addr,
                    "types": [str(t) for t in service.getTypes()],
                    "scopes": [str(s) for s in service.getScopes()],
                })

        wsd.stop()
        logger.info(f"📡 ONVIF discovery: {len(devices)} dispositivos encontrados")

    except ImportError:
        logger.warning("⚠️ onvif-python ou WSDiscovery não instalados")
    except Exception as e:
        logger.debug(f"ONVIF discovery error: {e}")

    return devices


def scan_local(config: ScanConfig) -> Generator[Camera, None, None]:
    """
    Scanner completo da rede local.

    1. ARP scan para descobrir hosts
    2. Port scan rápido (554, 80, 8080)
    3. ONVIF WS-Discovery
    """
    logger.info(f"🔍 Scanning local network: {config.local_subnet}")

    # 1. ARP Scan
    hosts = scan_arp(config.local_subnet)

    for host in hosts:
        ip = host["ip"]
        mac = host.get("mac")

        camera = Camera(
            ip=ip,
            source=SourceType.LOCAL_ARP,
            mac_address=mac,
            status=CameraStatus.PENDING,
        )

        yield camera

    # 2. ONVIF Discovery
    if config.onvif_discovery:
        onvif_devices = scan_onvif()

        for dev in onvif_devices:
            # Extrair IP do URL
            url = dev.get("url", "")
            if "://" in url:
                ip = url.split("://")[1].split(":")[0]
                port = 80
                if ":" in url.split("://")[1]:
                    try:
                        port = int(url.split("://")[1].split(":")[1].split("/")[0])
                    except (IndexError, ValueError):
                        port = 80

                camera = Camera(
                    ip=ip,
                    port=port,
                    source=SourceType.LOCAL_ONVIF,
                    onvif_supported=True,
                    onvif_url=url,
                    status=CameraStatus.PENDING,
                )

                yield camera
```

---

## 7.3 ONVIF Probe

### `procurador/core/onvif.py`

```python
"""
Módulo ONVIF.
Descoberta e interação com câmaras ONVIF.
"""
import logging

from procurador.core.models import Camera

logger = logging.getLogger(__name__)


def probe_onvif(camera: Camera, user: str = "admin", password: str = "") -> Camera:
    """
    Probe ONVIF para obter:
    - Informação do dispositivo (modelo, firmware, MAC)
    - Stream URIs (RTSP)
    - PTZ capabilities
    """
    try:
        from onvif import ONVIFCamera

        # Connect via ONVIF
        cam = ONVIFCamera(camera.ip, camera.port or 80, user, password)

        # Device info
        try:
            device_info = cam.devicemgmt.GetDeviceInformation()
            camera.vendor = camera.vendor or device_info.Manufacturer
            camera.model = camera.model or device_info.Model
            camera.firmware = device_info.FirmwareVersion
        except Exception as e:
            logger.debug(f"ONVIF device info error: {e}")

        # Media profiles (streams)
        try:
            media = cam.create_media_service()
            profiles = media.GetProfiles()

            for profile in profiles:
                try:
                    stream_uri = media.GetStreamUri({
                        "StreamSetup": {
                            "Stream": "RTP-Unicast",
                            "Transport": {"Protocol": "RTSP"},
                        },
                        "ProfileToken": profile.token,
                    })
                    camera.rtsp_url = stream_uri.Uri
                    camera.rtsp_path = stream_uri.Uri.split("/", 3)[-1] if stream_uri.Uri else None
                    camera.onvif_supported = True

                    # Resolution from profile
                    vs = profile.VideoSourceConfiguration
                    if vs and hasattr(vs, "Bounds"):
                        camera.stream = camera.stream or StreamInfo()
                        camera.stream.width = vs.Bounds.width or 0
                        camera.stream.height = vs.Bounds.height or 0

                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"ONVIF media error: {e}")

        # PTZ
        try:
            ptz = cam.create_ptz_service()
            configs = ptz.GetConfigurations()
            if configs:
                camera.ptz_supported = True
        except Exception:
            camera.ptz_supported = False

    except ImportError:
        logger.warning("⚠️ onvif-python não instalado")
    except Exception as e:
        logger.debug(f"ONVIF probe error for {camera.ip}: {e}")

    return camera
```

---

## 7.4 Export — HTML Report

### `procurador/export/html_report.py`

```python
"""
Exportar relatório HTML bonito.
Dashboard estático com todas as câmaras, screenshots e estatísticas.
"""
import logging
from pathlib import Path
from datetime import datetime

from procurador.core.models import ScanResult, CameraStatus

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📹 Procurador de Câmara — Relatório</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
        body {{ font-family: 'JetBrains Mono', monospace; background: #0f1117; color: #e0e0e0; }}
        .card {{ background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 12px; padding: 16px; }}
        .live {{ color: #10b981; }}
        .auth {{ color: #f59e0b; }}
        .closed {{ color: #6b7280; }}
    </style>
</head>
<body class="p-6">
    <div class="max-w-6xl mx-auto">
        <h1 class="text-3xl font-bold text-cyan-400 mb-2">📹 Procurador de Câmara</h1>
        <p class="text-gray-500 mb-6">Relatório gerado em {date}</p>

        <div class="grid grid-cols-5 gap-4 mb-8">
            <div class="card text-center">
                <div class="text-3xl font-bold text-cyan-400">{total}</div>
                <div class="text-sm text-gray-400">📡 IPs</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-green-400">{live}</div>
                <div class="text-sm text-gray-400">🟢 Live</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-yellow-400">{auth}</div>
                <div class="text-sm text-gray-400">🟡 Auth</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-gray-400">{closed}</div>
                <div class="text-sm text-gray-400">⚫ Closed</div>
            </div>
            <div class="card text-center">
                <div class="text-3xl font-bold text-red-400">{errors}</div>
                <div class="text-sm text-gray-400">❌ Erros</div>
            </div>
        </div>

        <div class="card mb-8">
            <h2 class="text-lg font-bold text-cyan-400 mb-4">📹 Câmaras Acessíveis</h2>
            <table class="w-full text-sm">
                <thead>
                    <tr class="text-gray-400 border-b border-gray-700">
                        <th class="py-2 text-left">IP</th>
                        <th class="py-2 text-left">Fabricante</th>
                        <th class="py-2 text-left">Resolução</th>
                        <th class="py-2 text-left">País</th>
                        <th class="py-2 text-left">Credenciais</th>
                        <th class="py-2 text-left">Link RTSP</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2 class="text-lg font-bold text-cyan-400 mb-4">📸 Screenshots</h2>
            <div class="grid grid-cols-3 gap-4">
                {screenshots}
            </div>
        </div>
    </div>
</body>
</html>"""


def export_html(result: ScanResult, output_dir: str = "data/reports") -> str:
    """Exportar relatório HTML."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    rows = ""
    screenshots_html = ""
    live_cams = [c for c in result.cameras if c.status == CameraStatus.LIVE]

    for cam in live_cams[:30]:
        row = f"""<tr class="border-b border-gray-800">
            <td class="py-2 font-mono">{cam.ip}</td>
            <td class="py-2">{cam.vendor or 'Unknown'}</td>
            <td class="py-2">{cam.resolution}</td>
            <td class="py-2">{cam.geo.country or '??'}</td>
            <td class="py-2">{'✅ ' + cam.auth_user + ':' + cam.auth_pass if cam.auth_success else '🔒 locked'}</td>
            <td class="py-2"><code class="text-xs text-cyan-400">{cam.rtsp_url or 'N/A'}</code></td>
        </tr>"""
        rows += row

        # Screenshots
        if cam.screenshot_path:
            ss = f"""<div class="bg-gray-800 rounded p-2">
                <img src="../../{cam.screenshot_path}" alt="{cam.ip}" class="w-full rounded">
                <p class="text-xs text-gray-400 mt-1 text-center">{cam.ip}</p>
            </div>"""
            screenshots_html += ss

    html = HTML_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total=result.total_ips,
        live=result.accessible,
        auth=result.auth_required,
        closed=result.closed,
        errors=result.errors,
        rows=rows,
        screenshots=screenshots_html or "<p class='text-gray-500'>Nenhuma screenshot disponível</p>",
    )

    path = output / "report.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"📤 HTML report: {path}")
    return str(path)
```

---

## 7.5 Export — M3U Playlist

### `procurador/export/m3u.py`

```python
"""
Exportar playlist .m3u para abrir streams no VLC.
"""
import logging
from pathlib import Path
from datetime import datetime

from procurador.core.models import ScanResult, CameraStatus

logger = logging.getLogger(__name__)


def export_m3u(result: ScanResult, output_dir: str = "data/reports") -> str:
    """Exportar playlist M3U com todos os streams live."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    live_cams = [c for c in result.cameras
                 if c.status == CameraStatus.LIVE and c.rtsp_url]

    lines = [
        "#EXTM3U",
        f"#PLAYLIST: Procurador de Câmara — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"#EXTINF:0,--- {len(live_cams)} streams encontrados ---",
        "",
    ]

    for cam in live_cams:
        name = f"{cam.vendor or 'Unknown'} - {cam.ip} ({cam.resolution})"
        lines.append(f"#EXTINF:-1,📹 {name}")
        lines.append(cam.rtsp_url)
        lines.append("")

    # Guardar
    path = output / "streams.m3u"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"📤 M3U playlist: {path} ({len(live_cams)} streams)")
    return str(path)
```

---

## 7.6 Export — JSON

### `procurador/export/json_export.py`

```python
"""
Exportar resultados para JSON detalhado.
"""
import json
from pathlib import Path
from datetime import datetime

from procurador.core.models import ScanResult


def export_json(result: ScanResult, output_dir: str = "data/reports") -> str:
    """Exportar JSON."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    path = output / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Usar método to_dict do modelo
    data = {
        "scan_id": result.scan_id,
        "generated_at": datetime.now().isoformat(),
        "stats": {
            "total_ips": result.total_ips,
            "accessible": result.accessible,
            "auth_required": result.auth_required,
            "auth_failed": result.auth_failed,
            "closed": result.closed,
            "errors": result.errors,
            "live_streams": result.live_streams,
            "vendors": result.vendors,
            "countries": result.countries,
        },
        "cameras": [
            c.to_dict() for c in result.cameras
            if c.status in (CameraStatus.LIVE, CameraStatus.AUTH_REQUIRED)
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return str(path)
```

---

## 7.7 Export — CSV

### `procurador/export/csv_export.py`

```python
"""
Exportar resultados para CSV simples.
"""
import csv
from pathlib import Path
from datetime import datetime

from procurador.core.models import ScanResult


def export_csv(result: ScanResult, output_dir: str = "data/reports") -> str:
    """Exportar CSV."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    path = output / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "IP", "Porta", "Fabricante", "Status",
            "Resolução", "Codec", "FPS",
            "País", "Cidade", "Lat", "Lon",
            "ISP", "Auth", "User", "Pass",
            "RTSP URL",
        ])

        for cam in result.cameras:
            writer.writerow([
                cam.ip,
                cam.port,
                cam.vendor or "",
                cam.status.value,
                cam.resolution,
                cam.stream.codec if cam.stream else "",
                f"{cam.stream.fps:.1f}" if cam.stream and cam.stream.fps else "",
                cam.geo.country or "",
                cam.geo.city or "",
                cam.geo.lat or "",
                cam.geo.lon or "",
                cam.network.isp or "",
                "Yes" if cam.auth_success else "No",
                cam.auth_user or "",
                cam.auth_pass or "",
                cam.rtsp_url or "",
            ])

    return str(path)
```

---

## 7.8 Checklist da Fase 3

- [ ] Stream capture com OpenCV (screenshot + info)
- [ ] Scan local (ARP + ONVIF WS-Discovery)
- [ ] ONVIF probe (device info, media, PTZ)
- [ ] Export HTML report
- [ ] Export M3U playlist
- [ ] Export JSON
- [ ] Export CSV
- [ ] Todos os exports testados
- [ ] Screenshots guardadas em `data/screenshots/`
- [ ] Playlist .m3u abre no VLC sem erros

---

> Seguir para o documento 08 — FASE 4: POLISH
