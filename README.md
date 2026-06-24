# 🦾 Procurador de Câmara

Ferramenta de cibersegurança para descoberta e auditoria de câmaras IP expostas na internet e redes locais.

Combina:
- **Censys API** — descoberta global de câmaras com RTSP/HTTP/ONVIF expostos
- **Scan local (ARP + WS-Discovery)** — descoberta na LAN
- **Pipeline de 7 técnicas de acesso** — maximiza taxa de acesso
- **Dashboard TUI (Rich)** — hacker aesthetic
- **Dashboard Web (Flask + Tailwind + Chart.js + Folium)** — moderno, com mapa
- **4 formatos de export** — JSON, CSV, HTML, M3U (VLC)

## ⚠️ Aviso Legal

Esta ferramenta é para **pentesting autorizado**, **inventário de rede corporativa** e **pesquisa de segurança**. Usar apenas em redes e dispositivos que possui ou tem autorização explícita. O uso indevido é ilegal.

## 🚀 Quickstart

```powershell
# 1. Setup
cd "C:\Users\rodri\Desktop\PROCURADOR DE CAMARA"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Configurar API keys (Censys é obrigatório para descoberta)
copy .env.example .env
# Editar .env e colocar o Personal Access Token (CENSYS_API_KEY)

# 3. Scan básico
python -m procurador --country PT --pages 5

# 4. Com targets manuais
python -m procurador --target 1.2.3.4:554 --target 5.6.7.8:8554

# 5. Scan local
python -m procurador --local --subnet 192.168.1.0/24

# 6. Com captura de screenshots
python -m procurador --country PT --pages 1 --stream

# 7. Dashboard TUI
python -m procurador --country PT --tui

# 8. Dashboard Web
python -m procurador --country PT --web --port 5000
```

## 🎯 Pipeline de Acesso (7 Técnicas)

Para CADA IP, tenta por ordem até encontrar acesso:

| # | Técnica | Taxa Esperada | CVE/Detalhes |
|---|---------|---------------|--------------|
| 1 | **RTSP sem auth** (DESCRIBE) | 8% | CVE-2025-9983 GALAYOU, CVE-2025-66049 Vivotek porta 8554 |
| 2 | **ONVIF stream URIs** (GetStreamUri) | 5% | CVE-2025-65856 Xiongmaitech (31 endpoints sem auth) |
| 3 | **HTTP Snapshot** (vários paths) | 12% | /cgi-bin/snapshot.cgi, /onvif/snapshot, etc |
| 4 | **HTTP Admin** (login + creds default) | 10% | /login, /admin, com brute de 20 credenciais |
| 5 | **RTSP brute** (paths + creds) | 28% | Basic + **Digest auth MD5 (RFC 2617)** |
| 6 | **Portas alternativas** (8554, 5554, 37777...) | 3% | scan paralelo de 9 portas |
| 7 | **CVE exploits** (vendor-specific) | 2% | CVE-2021-36260 Hikvision, CVE-2024-42531 Ezviz |

**Taxa esperada total: 30-50%** (vs ~30% em ferramentas single-technique).

## 🏗️ Arquitetura

```
procurador/
├── core/
│   ├── models.py       # Camera, ScanResult, ScanConfig (dataclasses)
│   ├── scanner.py      # RTSP probe + brute paths + HTTP admin
│   ├── brute.py        # Basic + Digest auth (RFC 2617)
│   ├── onvif.py        # WS-Discovery + GetStreamUri
│   ├── cve.py          # CVE-2021-36260, 2024-42531, 2025-9983, 2025-66049, 2025-65856
│   ├── geoip.py        # ipinfo.io + MaxMind (cache)
│   ├── stream.py       # OpenCV screenshot + ffmpeg fallback
│   └── wordlists.py    # 189 paths RTSP, 88 credenciais, 35 snapshot paths
├── sources/
│   ├── censys.py       # Censys API v2 + CenQL
│   └── local.py        # ARP scan (scapy) + WS-Discovery (ONVIF)
├── ui/
│   ├── tui.py          # Rich dashboard (stats + tabela + log)
│   ├── tui_stream.py   # Grid 2x3 de streams
│   └── web/            # Flask + Tailwind + Chart.js + HTMX + Folium
├── export/
│   ├── json_export.py  # JSON completo
│   ├── csv_export.py   # CSV tabela
│   ├── html_report.py  # HTML standalone com screenshots
│   └── m3u.py          # Playlist VLC
└── utils/
    ├── logger.py       # Rich logger
    └── helpers.py      # retry, rate_limit, extract_title, parse_hostport
```

## ⚙️ CLI

```powershell
python -m procurador [opções]

# Descoberta
  --country, -c        País (código "PT" ou nome "Portugal")
  --query, -q          Query Censys custom
  --pages              Número de páginas Censys (default: 5)
  --per-page           Resultados por página (default: 100)
  --local              Ativar scan local (ARP + ONVIF)
  --subnet             Sub-rede (default: 192.168.1.0/24)

# Scan
  --no-brute           Desativar brute force de credenciais
  --no-onvif           Desativar ONVIF discovery
  --no-cve             Desativar tentativas de CVE
  --no-geoip           Desativar GeoIP
  --stream             Capturar screenshots
  --max-workers        Threads paralelas (default: 50)
  --timeout            Timeout por probe em segundos (default: 3)

# UI
  --tui                Abrir dashboard TUI no fim
  --web                Abrir dashboard Web no fim
  --port               Porta do dashboard Web (default: 5000)

# Output
  --no-save            Não guardar resultados em JSON
  --out                Diretório de output (default: data)
  --log-level          DEBUG/INFO/WARNING/ERROR

# Manual
  --target, -t         IP manual (repetível, formato IP ou IP:porta)
```

## 🔑 API Keys

### Censys (obrigatório para descoberta)
1. Conta em https://search.censys.io/
2. API tokens em https://search.censys.io/account/api
3. Adicionar ao `.env`:
   ```
   CENSYS_API_ID=o_teu_id
   CENSYS_SECRET=o_teu_secret
   ```

⚠️ **A API Censys v2 (Platform) requer ID + Secret. O ID sozinho não basta.** Sem secret, o módulo reporta warning e segue em frente (útil para scan local ou manual).

### ipinfo.io (opcional, para GeoIP)
1. Token grátis em https://ipinfo.io/account/token
2. Adicionar ao `.env`:
   ```
   IPINFO_TOKEN=o_teu_token
   ```

## 📊 Output

Após um scan, os resultados estão em `data/`:
- `data/scan_<id>_<timestamp>.json` — JSON completo
- `data/screenshots/<ip>_<ts>.jpg` — Screenshots de streams LIVE
- `data/reports/` — Exports (gerados a partir do dashboard)

## 🧪 Testes

```powershell
# 43 testes, 100% pass
.\venv\Scripts\python.exe -m pytest tests/ -v

# Lint
.\venv\Scripts\python.exe -m ruff check procurador/
.\venv\Scripts\python.exe -m ruff format procurador/

# Type check
.\venv\Scripts\python.exe -m mypy procurador/
```

## 🐛 Troubleshooting

### Censys retorna 401
API ID sem secret. Verifica que `CENSYS_SECRET` está em `.env`.

### ONVIF falha
- `onvif-python` e `WSDiscovery` podem ter issues no Windows
- O scanner continua sem ONVIF, apenas sem esse vetor

### OpenCV não captura stream
- H.265/HEVC pode falhar com OpenCV
- ffmpeg é usado como fallback automaticamente
- Verifica que `ffmpeg` está no PATH (download em https://ffmpeg.org)

### Scapy / ARP scan falha
- Scapy no Windows requer Npcap (https://npcap.com)
- Sem Npcap, usa `arp -a` como fallback (hosts conhecidos apenas)

### Windows Defender bloqueia EXE
- Adicionar exceção para o diretório do projeto
- Ou correr direto via Python (sem PyInstaller)

## 📜 Licença

MIT — usar com responsabilidade.
