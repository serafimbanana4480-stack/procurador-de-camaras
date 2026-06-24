# 01 — VISÃO GERAL DO PROJETO

> **"PROCURADOR DE CÂMERA"** — Ferramenta de descoberta e auditoria de câmaras IP
> Inspirada em: Cameradar, RTSPBrute, Shodan, Censys

---

## 1.1 O Que É

O **Procurador de Câmara** é uma ferramenta de **segurança ofensiva/defensiva** que:

1. **Descobre** câmaras IP na internet (Censys API) e na rede local (scapy + ONVIF)
2. **Testa** acessibilidade RTSP com probe DESCRIBE
3. **Tenta** default credentials por fabricante
4. **Apresenta** streams ao vivo num dashboard interativo
5. **Exporta** resultados para relatórios

---

## 1.2 Objetivos

### Primários
- ✅ Scanner multi-fonte (Censys, Shodan, LAN)
- ✅ RTSP probe + brute de creds default
- ✅ Dashboard TUI rico em tempo real
- ✅ Stream viewer com grid de câmaras
- ✅ Localização GeoIP + mapa
- ✅ Export para VLC, JSON, HTML

### Secundários
- ✅ Web dashboard opcional
- ✅ ONVIF auto-discovery na LAN
- ✅ Screenshot automation
- ✅ Relatório HTML exportável
- ✅ Playlist .m3u para VLC

### Stretch Goals
- 🔄 PTZ control
- 🔄 Motion detection
- 🔄 Shodan API integration (full)
- 🔄 Telegram/Discord notifications
- 🔄 Executável standalone (EXE)

---

## 1.3 Público-Alvo

| Utilizador | Caso de Uso |
|---|---|
| **Pentester** | Auditoria de redes, ethical hacking |
| **Sysadmin** | Descobrir câmaras esquecidas na rede |
| **Security researcher** | Estudo de exposição IoT |
| **TI empresarial** | Inventário de dispositivos de rede |
| **Curioso/Tu** | Aprendizagem, demonstrações, diversão |

---

## 1.4 Stack Tecnológica Completa

### Backend (Python 3.11+)

```
Camada              Tecnologia          Função
─────────────────────────────────────────────────────────────
APIs externas       censys, shodan      Buscar IPs de câmaras
Scanner             scapy, socket       Probes de rede
Streaming           opencv-python       Capturar streams RTSP
Brute force         aiohttp/requests   Teste de creds
GeoIP               geoip2, ipinfo      Localizar IPs
ONVIF               onvif-python        Descobrir câmaras ONVIF
Dados               dataclasses + json Modelos e persistência
Async               asyncio + aiohttp   Concorrência
Logging             structlog           Logging estruturado
```

### Frontend TUI

```
TUI                 rich                Tabelas, painéis, layouts
Live update         rich.live           Atualização em tempo real
Stream grid         opencv + rich       Grid de streams
```

### Frontend Web (Opcional)

```
Web framework       Flask               Servidor web
Templating          Jinja2              HTML templates
Frontend            HTMX + Alpine.js    Interatividade sem JS build
CSS                 Tailwind (CDN)      Estilo moderno
Maps                Folium              Mapa interativo
Charts              Chart.js (CDN)      Gráficos
```

### Infra

```
Runtime             Python 3.11+
OS                  Windows 10/11 (com WSL opcional)
GPU (opcional)      NVIDIA RTX 3060 Ti (CUDA para YOLO)
Package manager     pip + venv ou uv
Build               PyInstaller (para EXE)
```

---

## 1.5 Fluxo de Dados Principal

```
                    ┌──────────────────────────────┐
                    │          CENSYS API            │
                    │  (query: RTSP + país X)        │
                    └────────────┬─────────────────┘
                                 │ JSON: [IP, porta, banner, coords]
                                 ▼
                    ┌──────────────────────────────┐
                    │       FILTER ENGINE            │
                    │  - Remove duplicados           │
                    │  - Identifica fabricante       │
                    │  - Ordena por potencial        │
                    └────────────┬─────────────────┘
                                 │ Lista de alvos
                                 ▼
              ┌──────────────────────────────────────┐
              │         RTSP PROBE (socket)           │
              │  OPTIONS → DESCRIBE → analyse response │
              │  200 ✓ = acessível                     │
              │  401 ✗ = precisa creds                 │
              │  404 ✗ = path errado                   │
              └────────────┬────────────────────────┘
                           │
              ┌────────────▼────────────────────────┐
              │      CREDENTIAL BRUTE ENGINE         │
              │  - Tenta default creds por marca     │
              │  - Tenta lista genérica (top 50)     │
              │  - Se 200 → stream acessível         │
              └────────────┬────────────────────────┘
                           │
              ┌────────────▼────────────────────────┐
              │      STREAM CAPTURE (OpenCV)         │
              │  - Abre VideoCapture com creds       │
              │  - Screenshot frame                  │
              │  - Regista codec/resolution/fps      │
              └────────────┬────────────────────────┘
                           │
              ┌────────────▼────────────────────────┐
              │           DASHBOARD                  │
              │  TUI Rich: tabelas + painéis         │
              │  Web: mapa + grid de streams         │
              │  Export: JSON, HTML, CSV, M3U        │
              └─────────────────────────────────────┘
```

---

## 1.6 Funcionalidades por Versão

### MVP (v0.1)
- [ ] Censys API integration
- [ ] RTSP probe básico
- [ ] Tabela TUI simples
- [ ] Export JSON

### Alpha (v0.2)
- [ ] Default creds brute
- [ ] Identificação de fabricante
- [ ] GeoIP localização
- [ ] Screenshot automático

### Beta (v0.3)
- [ ] Dashboard Rich completo (live update)
- [ ] Stream grid OpenCV
- [ ] Shodan integration
- [ ] Scan LAN (ARP + ONVIF)

### Release (v1.0)
- [ ] Web dashboard
- [ ] Mapa interativo Folium
- [ ] Export HTML report
- [ ] Playlist .m3u
- [ ] Config file
- [ ] Executável standalone

---

## 1.7 Princípios de Design

### Dashboard
- **"Terminal hacker aesthetic"** — fundo preto, verde ciano, dados a fluir
- **Informação densa mas legível** — tabelas bem formatadas
- **Live updates** — dados mudam sem refresh, estilo mission control
- **Grid de streams** — miniaturas das câmaras encontradas

### Código
- **Modular** — cada fonte/componente é um módulo independente
- **Tipado** — type hints em todo o lado
- **Testável** — funções puras sempre que possível
- **Configurável** — config.toml, não hardcoded

### Segurança
- **Zero tráfego ofensivo** — apenas SYN scan local (LAN própria)
- **APIs públicas** — Censys/Shodan fazem o scan, nós só consultamos
- **Logs locais** — nunca enviar dados para terceiros
- **Opt-in** — user escolhe o que quer testar

---

## 1.8 Estrutura de Pastas Final

```
C:\Users\rodri\Desktop\PROCURADOR DE CAMERA\
│
├── procurador/                        # Pacote principal
│   ├── __init__.py
│   ├── __main__.py                    # Entry point: python -m procurador
│   ├── config.py                      # Config loader
│   │
│   ├── sources/                       # Fontes de dados
│   │   ├── __init__.py
│   │   ├── censys.py                  # Censys API
│   │   ├── shodan.py                  # Shodan API (opcional)
│   │   └── local.py                   # LAN scan
│   │
│   ├── core/                          # Motor principal
│   │   ├── __init__.py
│   │   ├── models.py                  # Dataclasses
│   │   ├── scanner.py                 # RTSP probe engine
│   │   ├── brute.py                   # Credential brute
│   │   ├── stream.py                  # OpenCV stream capture
│   │   ├── onvif.py                   # ONVIF discovery
│   │   └── geoip.py                   # GeoIP resolver
│   │
│   ├── ui/                            # Interfaces
│   │   ├── __init__.py
│   │   ├── tui.py                     # Dashboard Rich
│   │   ├── tui_stream.py              # Grid de streams
│   │   └── web/                       # Web dashboard
│   │       ├── __init__.py
│   │       ├── app.py                 # Flask server
│   │       ├── templates/
│   │       └── static/
│   │
│   ├── export/                        # Export
│   │   ├── __init__.py
│   │   ├── json.py
│   │   ├── html_report.py
│   │   └── m3u.py
│   │
│   └── utils/                         # Utilitários
│       ├── __init__.py
│       ├── logger.py
│       └── helpers.py
│
├── config.toml                        # Configuração
├── data/                              # Dados gerados
│   ├── found.json
│   ├── screenshots/
│   └── reports/
│
├── wordlists/                         # Wordlists
│   ├── credentials.txt
│   └── routes.txt
│
├── tests/                             # Testes
│
├── requirements.txt                   # Dependências
├── pyproject.toml                     # Metadados do projeto
├── README.md                          # Documentação
└── LICENSE                            # MIT
```

---

## 1.9 Dependências (requirements.txt)

```txt
# === Core ===
requests>=2.31.0
aiohttp>=3.9.0

# === APIs ===
censys>=2.2.0
shodan>=1.28.0            # Opcional

# === Scanning ===
scapy>=2.5.0              # LAN scan
onvif-python>=0.2.10      # ONVIF discovery

# === Streaming ===
opencv-python>=4.8.0
numpy>=1.24.0

# === TUI ===
rich>=13.0.0
textual>=0.41.0            # Opcional (para TUI avançada)

# === GeoIP ===
geoip2>=4.6.0             # MaxMind DB
ipinfo>=4.4.0             # API ipinfo.io

# === Web Dashboard ===
flask>=3.0.0
folium>=0.15.0
jinja2>=3.1.0

# === Tools ===
structlog>=24.0.0
orjson>=3.9.0              # JSON rápido (opcional)
tomli>=2.0.0               # Python 3.11+ já inclui tomllib

# === Dev ===
pytest>=8.0.0
ruff>=0.1.0
mypy>=1.7.0
```

---

## 1.10 Cronograma

```
Dia 1:  Setup + Censys integração + probe RTSP básico
Dia 2:  Core engine completo (brute, stream, geoip)
Dia 3:  Dashboard Rich (TUI)
Dia 4:  Grid de streams + screenshots + export
Dia 5:  Web dashboard + mapa
Dia 6:  Polimento + edge cases + logging
Dia 7:  Documentação + packaging + release

Total: ~7 dias (pode ser mais se fizeres ao fim de semana)
```

---

> Seguir para o documento 02 — Dashboard Design
