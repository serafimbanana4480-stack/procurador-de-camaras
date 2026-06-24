# 03 — ARQUITETURA DO PROJETO

> Arquitetura full stack, fluxos de dados, componentes, decisões técnicas

---

## 3.1 Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PROCURADOR DE CÂMERA                             │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                      LAYER 1 — SOURCES                          │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│      │
│  │  │ censys   │  │ shodan   │  │ local    │  │ manual (CLI)     ││      │
│  │  │ API      │  │ API      │  │ ARP+ONVIF│  │ stdin args       ││      │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘│      │
│  └───────┼──────────────┼─────────────┼──────────────────┼──────────┘      │
│          ▼              ▼             ▼                  ▼                 │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                      LAYER 2 — CORE ENGINE                      │      │
│  │                                                                  │      │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │      │
│  │  │ filter       │───▶│ rtsp probe   │───▶│ cred brute       │   │      │
│  │  │ + dedup      │    │ (socket)     │    │ (default creds)  │   │      │
│  │  └──────────────┘    └──────────────┘    └────────┬─────────┘   │      │
│  │                                                    │             │      │
│  │  ┌──────────────┐    ┌──────────────┐              │             │      │
│  │  │ onvif probe  │    │ geoip        │              │             │      │
│  │  │ (LAN only)   │    │ resolver     │              │             │      │
│  │  └──────────────┘    └──────────────┘              │             │      │
│  │                                                    ▼             │      │
│  │                                            ┌──────────────────┐  │      │
│  │                                            │ stream capture   │  │      │
│  │                                            │ (OpenCV)         │  │      │
│  │                                            └────────┬─────────┘  │      │
│  └──────────────────────────────────────────────────────┼───────────┘      │
│                                                         │                  │
│  ┌──────────────────────────────────────────────────────▼───────────┐      │
│  │                    LAYER 3 — DATA PERSISTENCE                    │      │
│  │                                                                  │      │
│  │  ┌─────────────────┐  ┌────────────────┐  ┌──────────────────┐  │      │
│  │  │ found.json      │  │ data/cameras/  │  │ screenshots/*.png│  │      │
│  │  │ (scan results)  │  │ (individual)   │  │ (frames)         │  │      │
│  │  └────────┬────────┘  └────────────────┘  └──────────────────┘  │      │
│  └───────────┼──────────────────────────────────────────────────────┘      │
│              ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                   LAYER 4 — UI LAYER                             │      │
│  │                                                                  │      │
│  │  ┌────────────────────┐    ┌──────────────────────┐              │      │
│  │  │ TUI (Rich)         │    │ Web (Flask + HTMX)   │              │      │
│  │  │                    │    │                      │              │      │
│  │  │ • Main dashboard   │    │ • Dashboard page     │              │      │
│  │  │ • Stream grid      │    │ • Live streams       │              │      │
│  │  │ • Detail view      │    │ • Mapa Folium        │              │      │
│  │  │ • Export menu      │    │ • Detail pages       │              │      │
│  │  │ • Mapa terminal    │    │ • Export download    │              │      │
│  │  └────────────────────┘    └──────────────────────┘              │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                    LAYER 5 — EXPORT                               │      │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────────┐ │      │
│  │  │ JSON │ │ CSV  │ │ HTML │ │ M3U  │ │ TXT  │ │ VLC playlist │ │      │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────────────┘ │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3.2 Modelos de Dados (Dataclasses)

### Camera

```python
@dataclass
class Camera:
    """Representa uma câmara IP descoberta."""

    # Identificação
    ip: str
    port: int = 554
    hostname: str | None = None

    # Fabricante
    vendor: str | None = None          # Hikvision, Dahua, Axis, etc
    model: str | None = None            # DS-2CD2386G2-I
    firmware: str | None = None         # V5.7.1 build 230824
    mac: str | None = None              # 2c:8a:72:XX:XX:XX

    # Acesso
    auth_required: bool = True
    auth_success: bool = False
    auth_user: str | None = None
    auth_pass: str | None = None

    # RTSP
    rtsp_url: str | None = None         # URL completo com creds
    rtsp_path: str | None = None        # /Streaming/Channels/101
    rtsp_methods: list[str] | None = None  # OPTIONS, DESCRIBE, etc

    # Stream info
    codec: str | None = None            # H.264, H.265, MJPEG
    width: int = 0
    height: int = 0
    fps: float = 0.0
    bitrate: float | None = None        # em Mbps

    # ONVIF
    onvif_supported: bool = False
    onvif_url: str | None = None        # http://IP:2020/onvif/device_service
    ptz_supported: bool = False

    # Localização
    country: str | None = None
    city: str | None = None
    lat: float | None = None
    lon: float | None = None
    isp: str | None = None              # NOS, Vodafone, MEO
    org: str | None = None              # Organização

    # Estado do scan
    status: CameraStatus = CameraStatus.PENDING
    last_seen: float = 0.0              # timestamp
    screenshot_path: str | None = None   # path para frame capturado
    source: str = "censys"              # censys | shodan | local | manual

    # Metadados
    raw_banner: str | None = None       # banner RTSP cru
    http_title: str | None = None       # título da página admin
    http_server: str | None = None      # server header
    ports_open: list[int] | None = None  # outras portas abertas
```

### CameraStatus (Enum)

```python
class CameraStatus(Enum):
    PENDING = "pending"         # À espera de scan
    SCANNING = "scanning"       # A ser escaneada agora
    LIVE = "live"               # Stream acessível
    AUTH_REQUIRED = "auth"      # Precisa credenciais (401)
    AUTH_FAILED = "auth_fail"   # Creds testadas sem sucesso
    CLOSED = "closed"           # Porta fechada ou timeout
    ERROR = "error"             # Erro no scan
    WEB_ONLY = "web"            # Só HTTP admin, sem RTSP
```

### ScanResult

```python
@dataclass
class ScanResult:
    """Resultado completo de um scan."""

    # Metadados do scan
    scan_id: str                    # timestamp uuid
    started_at: float
    finished_at: float | None = None
    source: str                     # censys | shodan | local

    # Estatísticas
    total_ips: int = 0
    accessible: int = 0
    auth_required: int = 0
    closed: int = 0
    errors: int = 0

    # Dados
    cameras: list[Camera] = field(default_factory=list)
    query: str = ""                 # Query usada no Censys/Shodan
```

---

## 3.3 Fluxo de Dados Detalhado

### Censys Flow

```
1. user define query + country
2. censys.search(query, per_page=100)
   ├─ Página 1: 100 resultados
   ├─ Página 2: 100 resultados
   └─ ... até limite configurado
3. Para cada resultado:
   ├─ Extrair IP, porta, banner
   ├─ Identificar fabricante (regex no banner)
   ├─ Adicionar à lista de alvos
   └─ Aplicar dedup (hash: IP:porta)
4. Devolver list[Camera] para o core engine
```

### RTSP Probe Flow

```
Para cada alvo Camera:
1. Socket TCP connect -> IP:porta (timeout 3s)
   ├─ Sucesso → continuar
   └─ Falha → status = CLOSED
2. Enviar OPTIONS RTSP request
   ├─ Resposta → extrair métodos suportados
   └─ Timeout → status = ERROR
3. Enviar DESCRIBE request
   ├─ 200 OK → status = LIVE, extrair SDP (codec, res)
   ├─ 401 Unauthorized → status = AUTH_REQUIRED
   ├─ 404 Not Found → tentar path alternativo
   └─ Outro erro → status = ERROR
4. Guardar resultados em Camera
```

### Brute Flow

```
Para cada Camera com status = AUTH_REQUIRED:
1. Identificar fabricante pelo banner
2. Carregar wordlist específica do fabricante
3. Adicionar wordlist genérica (top 20)
4. Para cada par (user, pass):
   ├─ Construir rtsp://user:pass@IP:port/path
   ├─ DESCRIBE request com auth
   ├─ Se 200 OK → guardar creds, status = LIVE
   └─ Se 401 → próxima combinação
5. Se exaurir wordlist sem sucesso → status = AUTH_FAILED
```

### Stream Capture Flow

```
Para cada Camera com status = LIVE:
1. Construir rtsp://user:pass@IP:port/path
2. OpenCV VideoCapture(rtsp_url)
   ├─ Se abrir → capturar 1 frame
   ├─ Guardar screenshot
   ├─ Extrair codec, resolução, fps das props
   └─ Fechar stream
```

### GeoIP Flow

```
Para cada Camera:
1. Verificar se lat/lon já existem
2. Se não:
   ├─ Tenta ipinfo.io API (grátis, 50k req/mês)
   │  └─ country, city, lat, lon, org, isp
   └─ Fallback: geoip2 (MaxMind DB local)
3. Guardar no objeto Camera
```

---

## 3.4 Concorrência e Performance

### Estratégia

| Componente | Abordagem | Threads | Razão |
|---|---|---|---|
| Censys API | Sync (requests) | 1 | API rate limited |
| RTSP Probe | AsyncIO | N/A | I/O bound, centenas de sockets |
| Cred Brute | ThreadPoolExecutor | 50 | CPU + I/O mix |
| Stream Capture | ThreadPoolExecutor | 10 | OpenCV é blocking |
| GeoIP | Sync (requests) | 1 | API rate limited |
| ONVIF LAN | ThreadPoolExecutor | 20 | I/O bound |

### Configuração

```toml
[performance]
rtsp_probe_timeout = 3        # segundos
rtsp_probe_concurrent = 200   # sockets simultâneos
brute_threads = 50            # threads para brute
stream_threads = 10           # threads para OpenCV
geoip_cache_ttl = 3600        # 1 hora
batch_size = 100              # IPs por batch de scan
```

---

## 3.5 Gestão de Erros

### Estratégia por Camada

```
SOURCE LAYER:
  Erro de API → log + retry 3x + fallback para próxima fonte
  Rate limit → wait + backoff exponencial
  Timeout     → skip IP + log

CORE LAYER:
  Socket error → marcar como CLOSED
  Auth error   → marcar como AUTH_REQUIRED
  Stream error → marcar como ERROR + log detalhado

UI LAYER:
  TUI crash   → fallback para print() básico
  Web crash   → error page 500 + log
  Export fail → sugerir formato alternativo

GLOBAL:
  KeyboardInterrupt → graceful shutdown (salvar progresso)
  Memory limit      → batch processing
  File errors       → criar diretórios automaticamente
```

---

## 3.6 Configuração (config.toml)

```toml
[project]
name = "Procurador de Câmara"
version = "1.0.0"
data_dir = "data"
wordlists_dir = "wordlists"

[api]
censys_api_id = ""              # Opcional, usar env vars de preferência
censys_secret = ""
shodan_api_key = ""
ipinfo_token = ""

[sources]
censys_enabled = true
shodan_enabled = false
local_scan_enabled = true

[censys]
default_query = "services.service_name: RTSP"
max_pages = 5                   # 5 páginas = ~500 resultados
per_page = 100
timeout = 10

[shodan]
max_results = 100
timeout = 10

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
provider = "ipinfo"             # ipinfo | maxmind | both
maxmind_db_path = ""            # path para GeoLite2-City.mmdb
cache_enabled = true
cache_ttl = 3600

[export]
json_enabled = true
csv_enabled = true
html_enabled = true
m3u_enabled = true
report_dir = "data/reports"

[ui]
tui_enabled = true
web_enabled = false
web_host = "127.0.0.1"
web_port = 5000
web_refresh_seconds = 30

[logging]
level = "INFO"                  # DEBUG | INFO | WARNING | ERROR
file = "data/procurador.log"
format = "json"                 # json | text
```

---

## 3.7 Dependências Entre Módulos

```
sources/censys.py
    └── core/models.py
    └── core/geoip.py (opcional)

sources/shodan.py
    └── core/models.py
    └── core/geoip.py (opcional)

sources/local.py
    └── core/models.py
    └── core/onvif.py

core/scanner.py
    └── core/models.py
    └── utils/helpers.py

core/brute.py
    └── core/models.py
    └── core/scanner.py (função DESCRIBE)
    └── utils/helpers.py

core/stream.py
    └── core/models.py

core/geoip.py
    └── core/models.py

core/onvif.py
    └── core/models.py

ui/tui.py
    └── core/models.py
    └── core/scanner.py
    └── core/brute.py
    └── core/stream.py
    └── core/geoip.py

ui/tui_stream.py
    └── core/models.py
    └── core/stream.py

ui/web/app.py
    └── core/models.py
    └── export/*.py
    └── core/geoip.py

export/*.py
    └── core/models.py
```

---

## 3.8 Decisões Técnicas (ADRs)

### ADR-001: Dataclasses em vez de ORM
**Contexto:** Precisamos de modelos de dados leves sem DB.
**Decisão:** Usar `@dataclass` do Python. JSON para persistência. Se precisar de queries complexas, migrar para SQLite.
**Consequências:** Simples, rápido, sem dependências. Sacrifica queries complexas.

### ADR-002: Rich em vez de Textual (TUI)
**Contexto:** Textual é mais potente mas mais complexo.
**Decisão:** Rich com `rich.live.Live` para updates. Textual fica como opção para v2.
**Consequências:** Mais rápido de implementar, menos flexível.

### ADR-003: HTMX em vez de React (Web)
**Contexto:** Precisamos de interatividade web sem complexidade.
**Decisão:** Flask + Jinja2 + HTMX + Alpine.js + Tailwind CDN.
**Consequências:** Zero build step, zero npm, HTML puro. Sacrifica SPA features.

### ADR-004: Requests em vez de aiohttp para RTSP
**Contexto:** RTSP é TCP raw, não HTTP. aiohttp não serve.
**Decisão:** Socket nativo do Python + ThreadPoolExecutor para concorrência.
**Consequências:** Mais código, mas controlo total sobre o protocolo RTSP.

### ADR-005: JSON como formato de dados primário
**Contexto:** Precisamos de persistência leve e exportável.
**Decisão:** JSON em disco. Cada scan gera um ficheiro. orjson para serialização rápida.
**Consequências:** Legível por humanos, fácil de exportar, sem schema migrations.

### ADR-006: Config via TOML + env vars
**Contexto:** API keys não devem estar em ficheiros commitados.
**Decisão:** config.toml para config geral, env vars para segredos (CENSYS_API_ID, CENSYS_SECRET, etc).
**Consequências:** Seguro, flexível, padrão da indústria.

---

## 3.9 Segurança

### Boas Práticas
1. **API keys** → Variáveis de ambiente, nunca no código
2. **Logs** → Nunca logar passwords ou tokens
3. **Screenshots** → Nunca partilhar automaticamente
4. **Rede local** → Só escanear redes autorizadas
5. **Rate limiting** → Respeitar limites das APIs
6. **Timeout** → Sempre timeout em sockets (default 3s)
7. **Graceful shutdown** → Ctrl+C salva progresso

### O Que NÃO Fazer
1. ❌ Escanear IPs aleatórios na internet com masscan
2. ❌ Partilhar resultados de scans não autorizados
3. ❌ Commitar API keys no git
4. ❌ Ignorar rate limits (gets blocked)
5. ❌ Fazer brute force sem rate limiting (DoS involuntário)

---

## 3.10 Testes

### Estratégia

```
Unit tests:
├── test_models.py         → Dataclasses, enums, serialização
├── test_scanner.py        → RTSP probe (mocked socket)
├── test_brute.py          → Brute engine (mocked responses)
├── test_geoip.py          → GeoIP resolver
├── test_export.py         → Export formats
└── test_censys.py         → Censys query builder

Integration tests:
├── test_censys_live.py    → (opcional) Teste com API real
└── test_scan_pipeline.py  → Pipeline completo (mocked)

Fixtures:
├── tests/fixtures/
│   ├── censys_response_sample.json
│   ├── rtsp_banners.txt
│   └── sample_cameras.json
```

---

> Seguir para o documento 04 — FASE 0: PESQUISA E SETUP
