# 08 — FASE 4: POLISH, PACKAGING E DOCUMENTAÇÃO

> Duração estimada: 1-2 dias
> Objetivo: Polir, documentar, empacotar e preparar para distribuição

---

## 8.1 Error Handling Global

### Estratégia

```
1. TODOS os módulos têm try/except nas funções públicas
2. Erros são logados, nunca ignorados silenciosamente
3. KeyboardInterrupt → graceful shutdown (salvar progresso)
4. Timeouts em todas as operações de rede
5. Rate limiting automático nas APIs
6. Fallback: se Censys falha → tenta sem API key
7. Graceful degradation: se OpenCV falha → skip, continua
```

### Implementação

```python
# procurador/utils/helpers.py

import time
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator para retry com backoff exponencial.

    Uso:
        @retry(max_attempts=3, delay=1.0)
        def fetch_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        wait = delay * (backoff ** attempt)
                        logger.debug(f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                                     f"after {wait:.1f}s: {e}")
                        time.sleep(wait)
            logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {last_error}")
            raise last_error
        return wrapper
    return decorator


def timeout(seconds: float = 5.0):
    """
    Decorator para timeout de função (com signal, Unix only).

    Em Windows, usa socket timeout onde aplicável.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Em Python Windows, signal não funciona para threads
            # Usar timeout nos sockets diretamente
            return func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(max_per_minute: int = 60):
    """
    Rate limiter simples.
    Garante no máximo N chamadas por minuto.
    """
    calls: list[float] = []

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            # Remover chamadas mais antigas que 60s
            while calls and calls[0] < now - 60:
                calls.pop(0)

            if len(calls) >= max_per_minute:
                wait = 60 - (now - calls[0])
                if wait > 0:
                    logger.debug(f"Rate limit: waiting {wait:.1f}s...")
                    time.sleep(wait)

            calls.append(time.time())
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

---

## 8.2 Config File Final

### `config.toml`

```toml
[project]
name = "Procurador de Câmara"
version = "1.0.0"
data_dir = "data"
screenshots_dir = "data/screenshots"
reports_dir = "data/reports"
wordlists_dir = "wordlists"

[api]
# API keys via env vars: CENSYS_API_ID, CENSYS_SECRET, IPINFO_TOKEN, SHODAN_API_KEY
censys_timeout = 10
shodan_timeout = 10
ipinfo_timeout = 5

[sources]
censys_enabled = true
shodan_enabled = false
local_scan_enabled = true

[censys]
default_query = "services.service_name: RTSP"
max_pages = 5
per_page = 100

[shodan]
max_results = 100

[local]
subnet = "192.168.1.0/24"
onvif_discovery = true
onvif_timeout = 4
arp_scan = true

[scan]
rtsp_probe_timeout = 3
rtsp_probe_retries = 2
rtsp_probe_concurrent = 200
brute_enabled = true
brute_threads = 50
stream_capture = true
stream_threads = 10
screenshot_format = "png"
screenshot_quality = 90

[geoip]
provider = "ipinfo"  # ipinfo | maxmind | both
maxmind_db_path = ""
cache_enabled = true
cache_ttl = 3600

[export]
json_enabled = true
csv_enabled = true
html_enabled = true
m3u_enabled = true

[ui]
tui_enabled = true
web_enabled = false
web_host = "127.0.0.1"
web_port = 5000
web_refresh_seconds = 30
tui_refresh_seconds = 2

[logging]
level = "INFO"  # DEBUG | INFO | WARNING | ERROR
file = "data/procurador.log"
format = "text"  # json | text
max_size_mb = 10
backup_count = 3
```

---

## 8.3 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "procurador"
version = "1.0.0"
description = "📹 Scanner e auditoria de câmaras IP via Censys/Shodan/LAN"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
keywords = ["camera", "rtsp", "onvif", "security", "censys", "pentest"]
authors = [
    {name = "Soberana"},
]

classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Information Technology",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Topic :: Security",
    "Topic :: System :: Networking :: Monitoring",
]

dependencies = [
    "requests>=2.31.0",
    "aiohttp>=3.9.0",
    "censys>=2.2.0",
    "rich>=13.0.0",
    "opencv-python>=4.8.0",
    "numpy>=1.24.0",
    "flask>=3.0.0",
    "folium>=0.15.0",
    "jinja2>=3.1.0",
    "geoip2>=4.6.0",
]

[project.optional-dependencies]
shodan = ["shodan>=1.28.0"]
onvif = ["onvif-python>=0.2.10", "WSDiscovery>=2.1.0"]
local = ["scapy>=2.5.0"]
all = [
    "shodan>=1.28.0",
    "onvif-python>=0.2.10",
    "WSDiscovery>=2.1.0",
    "scapy>=2.5.0",
    "ipinfo>=4.4.0",
]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]

[project.scripts]
procurador = "procurador.__main__:main"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
```

---

## 8.4 README.md

```markdown
# 📹 Procurador de Câmara

> **Scanner e auditoria de câmaras IP** — descobre, testa e visualiza câmaras
> na internet (Censys/Shodan) e na rede local.

![Dashboard TUI](docs/tui_preview.png)
![Web Dashboard](docs/web_preview.png)

## 🚀 Funcionalidades

### 🔍 Descoberta
- **Censys API** → milhões de câmaras indexadas, filtra por país/fabricante
- **Shodan API** → (opcional) com screenshots pré-feitas
- **Scan Local** → ARP scan + ONVIF WS-Discovery na tua LAN

### 🎯 Teste de Acesso
- **RTSP Probe** → DESCRIBE request para verificar acesso
- **Brute Force** → default credentials por fabricante (Hikvision, Dahua, Axis...)
- **GeoIP** → localização, ISP, organização (ipinfo.io)

### 📺 Visualização
- **TUI Dashboard** → terminal hacker aesthetic com Rich
- **Stream Grid** → miniaturas das câmaras ao vivo
- **Web Dashboard** → Flask + Tailwind + Chart.js + Folium
- **Mapa Interativo** → Folium com clusters e heatmap

### 📤 Export
- **JSON** → dados completos
- **CSV** → tabela simples
- **HTML** → relatório bonito com screenshots
- **M3U** → playlist para VLC (abres e vês todas as streams)

## 📦 Instalação

```bash
git clone https://github.com/.../procurador
cd procurador
python -m venv venv
venv\Scripts\Activate  # Windows
pip install -e .       # Instala com dependências base
pip install -e ".[all]"  # Todas as dependências
```

### Configuração

1. Cria conta em [censys.io](https://censys.io)
2. Cria conta em [ipinfo.io](https://ipinfo.io) (grátis)
3. Define as API keys:

```bash
set CENSYS_API_ID=seu-id
set CENSYS_SECRET=seu-secret
set IPINFO_TOKEN=seu-token
```

## 🎮 Uso

```bash
# Scan default (Censys RTSP global)
python -m procurador

# Câmaras em Portugal
python -m procurador --country PT

# Com dashboard TUI
python -m procurador --country PT --tui

# Com web dashboard
python -m procurador --country PT --web

# Scan da LAN apenas
python -m procurador --local

# Query personalizada
python -m procurador --query "services.port: 554 and location.country: Portugal"

# Desativar brute force (mais rápido)
python -m procurador --no-brute

# Desativar captura de stream (só probe)
python -m procurador --no-stream
```

## 🏗️ Estrutura

```
procurador/
├── __main__.py          # Entry point
├── config.py            # Config loader
├── sources/             # Fontes de dados
│   ├── censys.py
│   ├── shodan.py
│   └── local.py
├── core/                # Motor
│   ├── models.py
│   ├── scanner.py
│   ├── brute.py
│   ├── stream.py
│   ├── onvif.py
│   └── geoip.py
├── ui/                  # Interfaces
│   ├── tui.py
│   ├── tui_stream.py
│   └── web/
│       ├── app.py
│       ├── map_export.py
│       └── templates/
└── export/              # Export
    ├── json_export.py
    ├── csv_export.py
    ├── html_report.py
    └── m3u.py
```

## ⚠️ Aviso Legal

Esta ferramenta é para **fins educacionais e de auditoria autorizada**.
- ✅ Escanear a tua própria rede
- ✅ Testar dispositivos com autorização
- ✅ Consultar dados públicos (Censys/Shodan)
- ❌ NUNCA usar para aceder a dispositivos de terceiros sem permissão

"Scanning is legal. Logging in is NOT." — Shodan

## 🛠️ Tech Stack

Python 3.11+ | Rich | OpenCV | Flask | Folium | HTMX | Tailwind CSS
Censys API | ipinfo.io | Scapy | ONVIF

## 📄 Licença

MIT
```

---

## 8.5 .gitignore

```gitignore
# Python
venv/
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/

# Environment
.env
*.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Project data
data/screenshots/*
data/reports/*
data/maps/*
data/exports/*
data/*.log

# Only keep screenshots placeholder
!data/screenshots/.gitkeep
!data/reports/.gitkeep
```

---

## 8.6 Packaging para EXE (Windows)

```powershell
# Instalar PyInstaller
pip install pyinstaller

# Build do executável
pyinstaller --onefile --console `
    --name "ProcuradorCamera" `
    --add-data "procurador;procurador" `
    --hidden-import censys `
    --hidden-import rich `
    --hidden-import cv2 `
    --hidden-import flask `
    --hidden-import folium `
    procurador/__main__.py

# O EXE está em dist/ProcuradorCamera.exe
# Copiar config.toml para o mesmo diretório
```

---

## 8.7 Testes

### `tests/test_scanner.py`

```python
"""Testes para o motor de scan RTSP."""
import pytest
from unittest.mock import patch, MagicMock

from procurador.core.scanner import probe_rtsp, RTSP_PATHS
from procurador.core.models import Camera, CameraStatus, ScanConfig


class TestProbeRTSP:
    """Testes para probe_rtsp()."""

    def test_probe_success(self):
        """Probe RTSP com resposta 200 OK."""
        # Mock socket
        with patch("socket.socket") as mock_socket:
            mock_instance = MagicMock()
            mock_socket.return_value = mock_instance
            mock_instance.recv.return_value = (
                b"RTSP/1.0 200 OK\r\n"
                b"CSeq: 1\r\n"
                b"Public: OPTIONS, DESCRIBE, SETUP, PLAY, TEARDOWN\r\n"
                b"\r\n"
            )

            result = probe_rtsp("192.168.1.100", 554, timeout=3, path="/live")

            assert result is not None
            assert result.status_code == 200
            assert "DESCRIBE" in result.methods

    def test_probe_auth_required(self):
        """Probe RTSP com 401 Unauthorized."""
        with patch("socket.socket") as mock_socket:
            mock_instance = MagicMock()
            mock_socket.return_value = mock_instance
            mock_instance.recv.return_value = (
                b"RTSP/1.0 401 Unauthorized\r\n"
                b"CSeq: 1\r\n"
                b"\r\n"
            )

            result = probe_rtsp("192.168.1.100", 554, timeout=3, path="/live")

            assert result is not None
            assert result.status_code == 401

    def test_probe_timeout(self):
        """Probe RTSP com timeout de socket."""
        with patch("socket.socket") as mock_socket:
            mock_instance = MagicMock()
            mock_socket.return_value = mock_instance
            mock_instance.connect.side_effect = TimeoutError()

            result = probe_rtsp("192.168.1.100", 554, timeout=3, path="/live")

            assert result is None

    def test_probe_connection_refused(self):
        """Probe RTSP com connection refused."""
        with patch("socket.socket") as mock_socket:
            mock_instance = MagicMock()
            mock_socket.return_value = mock_instance
            mock_instance.connect.side_effect = ConnectionRefusedError()

            result = probe_rtsp("192.168.1.100", 554, timeout=3, path="/live")

            assert result is None


class TestScanCamera:
    """Testes para scan_camera()."""

    def test_scan_live_camera(self):
        """Câmara que responde 200."""
        camera = Camera(ip="192.168.1.100")
        config = ScanConfig()

        with patch("procurador.core.scanner.probe_rtsp") as mock_probe:
            mock_probe.return_value.status_code = 200
            mock_probe.return_value.server_header = "Hikvision"
            mock_probe.return_value.sdp_body = (
                "v=0\r\n"
                "o=- 0 0 IN IP4 192.168.1.100\r\n"
                "m=video 0 RTP/AVP 96\r\n"
                "a=rtpmap:96 H264/90000\r\n"
                "a=framerate:25\r\n"
            )

            from procurador.core.scanner import scan_camera
            result = scan_camera(camera, config)

            assert result.status == CameraStatus.LIVE
            assert result.auth_required == False
            assert result.vendor == "Hikvision"

    def test_scan_auth_camera(self):
        """Câmara que pede auth."""
        camera = Camera(ip="192.168.1.100")
        config = ScanConfig()

        with patch("procurador.core.scanner.probe_rtsp") as mock_probe:
            mock_probe.return_value.status_code = 401
            mock_probe.return_value.server_header = "Dahua"

            from procurador.core.scanner import scan_camera
            result = scan_camera(camera, config)

            assert result.status == CameraStatus.AUTH_REQUIRED
            assert result.auth_required == True
            assert result.vendor == "Dahua"

    def test_scan_closed_port(self):
        """Porta fechada."""
        camera = Camera(ip="192.168.1.100")
        config = ScanConfig()

        with patch("procurador.core.scanner.probe_rtsp") as mock_probe:
            mock_probe.return_value = None

            from procurador.core.scanner import scan_camera
            result = scan_camera(camera, config)

            assert result.status == CameraStatus.CLOSED
```

---

## 8.8 Checklist Final

### Fase 4 — Polimento
- [ ] Error handling em todos os módulos
- [ ] Retry decorator implementado
- [ ] Rate limiting nas APIs
- [ ] Graceful shutdown (Ctrl+C)
- [ ] Fallback para quando APIs falham

### Config
- [ ] config.toml completo e documentado
- [ ] Loader de config funcional
- [ ] Env vars sobrepõem config file

### Packaging
- [ ] pyproject.toml completo
- [ ] `pip install -e .` funciona
- [ ] `python -m procurador` funciona
- [ ] `procurador` CLI funciona (entry point)

### Documentação
- [ ] README.md completo (instalação, uso, exemplos)
- [ ] .gitignore configurado
- [ ] Comentários no código em PT-PT
- [ ] Exemplos de uso no README

### Testes
- [ ] Testes unitários para scanner
- [ ] Testes unitários para brute
- [ ] Testes unitários para modelos
- [ ] `pytest` passa sem erros

### Lint
- [ ] `ruff check` limpo
- [ ] `ruff format` aplicado
- [ ] `mypy` sem erros (ou ignorar imports opcionais)

### Quality
- [ ] Logging em todos os módulos
- [ ] Type hints em todas as funções públicas
- [ ] Constantes em vez de magic numbers
- [ ] Funções pequenas (< 50 linhas)

### Extras
- [ ] (Opcional) EXE com PyInstaller
- [ ] (Opcional) Dockerfile
- [ ] (Opcional) CI com GitHub Actions (ruff + pytest)

---

> Seguir para o documento 09 — MELHORES PRÁTICAS
