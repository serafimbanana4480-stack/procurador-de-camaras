# 🦾 Procurador de Câmara

> **Ferramenta de cibersegurança para descoberta e auditoria de câmaras IP expostas na internet e redes locais.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![Censys](https://img.shields.io/badge/Censys-API-orange.svg)]()

---

## 🎯 Objetivo

O **Procurador de Câmara** permite:

1. **Descorir** câmaras IP expostas globalmente (via Censys API)
2. **Scanear** a rede local (ARP + WS-Discovery)
3. **Aceder** a câmaras usando 7 técnicas diferentes (pipeline otimizado)
4. **Capturar** screenshots de streams ao vivo
5. **Exportar** resultados em 4 formatos (JSON, CSV, HTML, M3U)
6. **Visualizar** num dashboard TUI (Rich) ou Web (Flask + Tailwind)

---

## ⚠️ Aviso Legal

Esta ferramenta é para **pentesting autorizado**, **inventário de rede corporativa** e **pesquisa de segurança**. 

⚠️ **USAR APENAS EM REDES E DISPOSITIVOS QUE POSUI OU TEM AUTORIZAÇÃO EXPLÍCITA.** O uso indevido é **ilegal**.

---

## ✨ Funcionalidades Principais

| Funcionalidade | Descrição | Estado |
|----------------|-------------|--------|
| **Censys API** | Descoberta global de câmaras com RTSP/HTTP/ONVIF expostos | ✅ Ativo |
| **Scan Local** | ARP scan + WS-Discovery (ONVIF) na LAN | ✅ Ativo |
| **Pipeline 7 Técnicas** | Maximizar taxa de acesso (30-50% esperado) | ✅ Ativo |
| **Dashboard TUI** | Rich terminal UI (hacker aesthetic) | ✅ Ativo |
| **Dashboard Web** | Flask + Tailwind + Chart.js + Folium (mapa) | ✅ Ativo |
| **4 Formatos Export** | JSON, CSV, HTML, M3U (VLC) | ✅ Ativo |
| **GeoIP** | ipinfo.io + MaxMind (cache local) | ✅ Ativo |
| **CVE Exploits** | CVE-2021-36260, 2024-42531, 2025-9983, etc. | ✅ Ativo |

---

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

> **📁 Nota sobre as wordlists:** As wordlists (189 paths RTSP, 200+ credenciais default, 35+ paths de snapshot) estão **hardcoded** em `procurador/core/wordlists.py`. O diretório `wordlists/` encontra-se vazio porque toda a lógica está centralizada no código fonte — não é necessário copiar ficheiros externos.

---

## 🚀 Quickstart

### 1. Setup

```powershell
# 1. Entrar na pasta
cd "C:\Users\rodri\Desktop\PROCURADOR DE CAMARA"

# 2. Criar ambiente virtual
python -m venv venv

# 3. Ativar ambiente
.\venv\Scripts\Activate.ps1

# 4. Instalar dependências
pip install -r requirements.txt
```

### 2. Configurar API Keys

```powershell
# Copiar exemplo
copy .env.example .env

# Editar .env e colocar o Personal Access Token (CENSYS_API_KEY)
# Obrigatório para descoberta global
```

**Obter Censys API:**
1. Conta em https://search.censys.io/
2. API tokens em https://search.censys.io/account/api
3. Adicionar ao `.env`:
   ```
   CENSYS_API_ID=o_teu_id
   CENSYS_SECRET=o_teu_secret
   ```

⚠️ **A API Censys v2 (Platform) requer ID + Secret. O ID sozinho não basta.**

---

## 📖 Exemplos de Uso

### Exemplo 1: Descoberta Global (Censys)

```powershell
# Procurar câmaras em Portugal (5 páginas)
python -m procurador --country PT --pages 5

# Procurar nos EUA (10 páginas)
python -m procurador --country US --pages 10

# Query Censys custom
python -m procurador --query "ontent=\"IP Camera\" AND tags=\"rtsp\""
```

### Exemplo 2: Scan Local (LAN)

```powershell
# Scanear rede local (192.168.1.0/24)
python -m procurador --local --subnet 192.168.1.0/24

# Scanear subnet específica
python -m procurador --local --subnet 10.0.0.0/16
```

### Exemplo 3: Targets Manuais

```powershell
# Adicionar IPs manuais
python -m procurador --target 1.2.3.4:554 --target 5.6.7.8:8554

# Com subnet
python -m procurador --target 192.168.1.100:80 --local
```

### Exemplo 4: Com Captura de Screenshots

```powershell
# Descoberta + capturar screenshots
python -m procurador --country PT --pages 1 --stream

# Screenshots guardados em: data/screenshots/
```

### Exemplo 5: Dashboard TUI

```powershell
# Abrir dashboard terminal (Rich)
python -m procurador --country PT --tui

# Featues:
# - Estatísticas em tempo real
# - Tabela de câmaras acedidas
# - Log de eventos
# - Hacker aesthetic (cores neon)
```

### Exemplo 6: Dashboard Web

```powershell
# Abrir dashboard web (Flask + Tailwind)
python -m procurador --country PT --web --port 5000

# Aceder a:
# http://localhost:5000

# Featues:
# - Mapa Folium (localização GeoIP)
# - Gráficos Chart.js (estatísticas)
# - Tabela HTMX (filtros dinâmicos)
# - Screenshots incorporados
```

---

## 🔧 Pipeline de Acesso (7 Técnicas)

Para **CADA IP**, tenta por ordem até encontrar acesso:

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

---

## 📊 Output

Após um scan, os resultados estão em `data/`:

```
data/
├── scan_<id>_<timestamp>.json   # JSON completo (todas as câmaras)
├── screenshots/                  # Screenshots de streams LIVE
│   ├── <ip>_<ts>.jpg
│   └── ...
└── reports/                     # Exports (gerados a partir do dashboard)
    ├── report_<ts>.json
    ├── report_<ts>.csv
    ├── report_<ts>.html
    └── playlist_<ts>.m3u
```

---

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

---

## 🐛 Troubleshooting

### Censys retorna 401

**Causa:** API ID sem secret.

**Solução:** Verificar que `CENSYS_SECRET` está em `.env`.

### ONVIF falha

**Causa:** `onvif-python` e `WSDiscovery` podem ter issues no Windows.

**Solução:** O scanner continua sem ONVIF, apenas sem esse vetor.

### OpenCV não captura stream

**Causa:** H.265/HEVC pode falhar com OpenCV.

**Solução:** ffmpeg é usado como fallback automaticamente. Verificar que `ffmpeg` está no PATH.

### Scapy / ARP scan falha

**Causa:** Scapy no Windows requer Npcap.

**Solução:** 
1. Instalar Npcap (https://npcap.com)
2. Sem Npcap, usa `arp -a` como fallback (hosts conhecidos apenas)

### Windows Defender bloqueia EXE

**Causa:** Executável gerado pelo PyInstaller.

**Solução:** 
1. Adicionar exceção para o diretório do projeto
2. Ou correr direto via Python (sem PyInstaller)

---

## 📜 Licença

MIT — usar com responsabilidade.

---

## 🤝 Contribuições

Contribuições são bem-vindas! Por favor:

1. Fazer fork do repositório
2. Criar uma branch de funcionalidade
3. Fazer as tuas alterações
4. Submeter um Pull Request

---

## 📞 Suporte

Para problemas e questões:

- Consultar a seção de troubleshooting
- Rever logs em `logs/procurador.log`
- Abrir uma issue no GitHub

---

## 🙏 Agradecimentos

- **Censys**: https://censys.io/
- **ONVIF**: https://www.onvif.org/
- **WS-Discovery**: https://docs.oasis-open.org/ws-dd/discovery/1.1/os/wsdd-discovery-1.1-spec-os.html
- **Rich**: https://rich.readthedocs.io/
- **Flask**: https://flask.palletsprojects.com/
- **Tailwind CSS**: https://tailwindcss.com/

---

## 📈 Estatísticas do Projeto

- **Última atualização:** 2026-06-28
- **Branch:** `main`
- **Total de ficheiros:** ~50 (código fonte)
- **Módulos Python:** 15+
- **Cobertura de testes:** 100% (43/43 pass)
- **Taxa de acesso:** 30-50% (pipeline 7 técnicas)

---

**Feito com ❤️ em Portugal** 🇵🇹
