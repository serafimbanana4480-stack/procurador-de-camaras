# 02 — DESIGN DO DASHBOARD

> Duas interfaces: **TUI Terminal Hacker** (primária) + **Web Dashboard** (secundária)
> Ambas partilham os mesmos dados em tempo real.

---

## 2.1 Filosofia de Design

### TUI (Terminal)
```
🎯 Objetivo: Parecer ecrã de filme (Matrix / Mission Impossible / Watch Dogs)
🎨 Paleta:  Preto (#000), Verde limão (#00FF00), Ciano (#00FFFF), Vermelho (#FF0000)
📐 Estilo:  Clean, denso, informativo, sem clutter
⚡ Vibe:    "NSA mission control no terminal"
```

### Web Dashboard
```
🎯 Objetivo: Acessível de qualquer browser, partilhável
🎨 Paleta:  Dark moderno (preto + tons azul/ciano)
📐 Estilo:  Glassmorphism + cards minimalistas
⚡ Vibe:    "Dashboard de pentest profissional"
```

---

## 2.2 TUI Dashboard — Mockup ASCII

### Ecrã Principal (ao iniciar)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  ██▓███   ██▀███   ▒█████   ▄████▄   █    ██  ██▀███   ▄▄▄       ██▓    │
│ ▓██░  ██▒▓██ ▒ ██▒▒██▒  ██▒▒██▀ ▀█   ██  ▓██▒▓██ ▒ ██▒▒████▄    ▓██▒    │
│ ▓██░ ██▓▒▓██ ░▄█ ▒▒██░  ██▒▒▓█    ▄ ▓██  ▒██░▓██ ░▄█ ▒▒██  ▀█▄  ▒██░    │
│ ▒██▄█▓▒ ▒▒██▀▀█▄  ▒██   ██░▒▓▓▄ ▄██▒▓▓█  ░██░▒██▀▀█▄  ░██▄▄▄▄██ ▒██░    │
│ ▒██▒ ░  ░░██▓ ▒██▒░ ████▓▒░▒ ▓███▀ ░▒▒█████▓ ░██▓ ▒██▒ ▓█   ▓██▒░██████▒│
│ ▒▓▒░ ░  ░░ ▒▓ ░▒▓░░ ▒░▒░▒░ ░ ░▒ ▒  ░░▒▓▒ ▒ ▒ ░ ▒▓ ░▒▓░ ▒▒   ▓▒█░░ ▒░▓  ░│
│ ░▒ ░       ░▒ ░ ▒░  ░ ▒ ▒░   ░  ▒   ░░▒░ ░ ░   ░▒ ░ ▒░  ▒   ▒▒ ░░ ░ ▒  ░│
│ ░░         ░░   ░ ░ ░ ░ ▒  ░        ░░░ ░ ░   ░░   ░   ░   ▒     ░ ░   │
│             ░         ░ ░  ░ ░        ░         ░           ░  ░    ░  ░│
│                              ░                                             │
├────────────────────────────────────────────────────────────────────────────┤
│  📡 PROCURADOR v1.0 — 2026-06-24 01:33:22              🔍 Scanning...    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─ ESTATÍSTICAS ──────────────────────────────────────────────────────┐  │
│  │  🔴 IPs descobertos:     1,247                                       │  │
│  │  🟡 Fabricantes identificados: 8                                      │  │
│  │  🟢 Streams acessíveis:   23                                          │  │
│  │  📸 Screenshots tiradas:  23                                          │  │
│  │  ⏱️  Tempo de scan:        2m 34s                                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ CÂMARAS ENCONTRADAS ─────────────────────────────────────────────────┐  │
│  │  IP               Fabricante   Porta  Auth    Resolução   Status      │  │
│  │  ───────────────────────────────────────────────────────────────────  │  │
│  │  188.81.XX.XXX    Hikvision     554    ✅     1920x1080   🟢 LIVE    │  │
│  │  188.81.XX.XXY    Dahua         554    🔒     1280x720    🟡 AUTH    │  │
│  │  85.242.XX.XXX    Axis          554    ❌     N/A         🔴 CLOSED  │  │
│  │  10.0.0.105       Reolink       554    ✅     2560x1440   🟢 LIVE    │  │
│  │  10.0.0.110       Hikvision     554    ✅     2688x1520   🟢 LIVE    │  │
│  │  85.242.XX.XXZ    TP-Link       8080   🔒     N/A         🟡 WEB-OK │  │
│  │  217.129.XX.XXX   Foscam        554    🔒     N/A         🟡 AUTH    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ ÚLTIMOS SIGHTINGS ──────────────────────────────────────────────────┐  │
│  │  [01:33:22] ✓  Hikvision @ 188.81.XX.XXX — admin:12345              │  │
│  │  [01:33:20] ✗  Dahua @ 188.81.XX.XXY  — auth required (401)         │  │
│  │  [01:33:18] ✓  Reolink @ 10.0.0.105   — admin:(empty)               │  │
│  │  [01:33:15] ✓  Axis @ 85.242.XX.XXX   — root:pass                   │  │
│  •••                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  [Ctrl+C] Sair  [R] Refresh  [S] Streams  [E] Export  [M] Mapa  [H] Help │
├────────────────────────────────────────────────────────────────────────────┤
│  🟢 23 câmaras ativas |  📍 12 países |  ⚡ 1,247 IPs escaneados          │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.3 TUI — Visão Streams (ao pressionar `S`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  📺 LIVE STREAMS — 23 câmaras acessíveis               [ESC] Voltar      │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 188.81.XX.XXX│  │ 188.81.XX.XXY│  │ 10.0.0.105   │  │ 10.0.0.110   │  │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │
│  │ │  🖼️ 📷   │ │  │ │  🖼️ 📷   │ │  │ │  🖼️ 📷   │ │  │ │  🖼️ 📷   │ │  │
│  │ │ FRAME    │ │  │ │ FRAME    │ │  │ │ FRAME    │ │  │ │ FRAME    │ │  │
│  │ │  LIVE    │ │  │ │  LIVE    │ │  │ │  LIVE    │ │  │ │  LIVE    │ │  │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │  │
│  │ Hikvision    │  │ Dahua        │  │ Reolink       │  │ Hikvision    │  │
│  │ 1920x1080    │  │ 1280x720     │  │ 4K            │  │ 2688x1520    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 85.242.XX.XXZ│  │ 217.129.XX.X │  │ 10.0.0.200   │  │ 192.168.1.64 │  │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │
│  │ │  🖼️ 📷   │ │  │ │  🖼️ 📷   │ │  │ │  🖼️ 📷   │ │  │ │  🖼️ 📷   │ │  │
│  │ │ FRAME    │ │  │ │ FRAME    │ │  │ │ FRAME    │ │  │ │ FRAME    │ │  │
│  │ │  LIVE    │ │  │ │  LIVE    │ │  │ │  LIVE    │ │  │ │  LIVE    │ │  │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │  │
│  │ TP-Link      │  │ Foscam       │  │ Bosch        │  │ Hikvision    │  │
│  │ 640x480      │  │ 1280x720     │  │ 1920x1080    │  │ 1920x1080    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                            │
│  [← →] Navegar  [ENTER] Ver fullscreen  [S] Screenshot  [ESC] Voltar     │
├────────────────────────────────────────────────────────────────────────────┤
│  📡 23 streams ativos |  ⚡ 12.4 Mbps total                               │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.4 TUI — Mapa (ao pressionar `M`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  🗺️  GLOBO 3D — Localização das câmaras                  [ESC] Voltar     │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                         ╔══════════════════╗                               │
│                    ╔════╝                  ╚════╗                          │
│                 ╔══╝         🌎  GLOBO           ╚══╗                      │
│                ╔╝           ROTATING 3D             ╚╗                     │
│               ╔╝         ● Câmara (Lisboa)           ╚╗                    │
│               ║         ● Câmara (Porto)             ║                     │
│               ║        ● Câmara (Madrid)             ║                     │
│               ║       ● Câmara (Londres)             ║                     │
│               ║      ● Câmara (Paris)               ║                     │
│                ╚╗     ● Câmara (Berlim)             ╔╝                    │
│                 ╚══╗                              ╔══╝                    │
│                    ╚════╗                    ╔════╝                       │
│                         ╚════════════════════╝                            │
│                                                                            │
│  Clusters:                                                                 │
│  ● Portugal (8 câmaras)    ● Espanha (4)    ● França (3)                  │
│  ● Reino Unido (3)         ● Alemanha (2)   ● Outros (3)                  │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  [ESC] Voltar ao dashboard principal                                      │
└────────────────────────────────────────────────────────────────────────────┘
```

> **Nota:** O mapa é gerado com Plotly ou Folium e abre no browser.
> No terminal, só aparece a tabela de clusters por país.

---

## 2.5 TUI — Detalhe da Câmara (ao pressionar ENTER numa linha)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  📹 DETALHE DA CÂMARA                              [ESC] Voltar           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  IP:           188.81.XX.XXX                                               │
│  Porta:        554                                                         │
│  Fabricante:   Hikvision DS-2CD2386G2-I                                   │
│  FW Version:   V5.7.1 build 230824                                        │
│  MAC:          2c:8a:72:XX:XX:XX                                          │
│  Localização:  Lisboa, Portugal 🇵🇹                                        │
│  Coordenadas:  38.7223° N, -9.1393° W                                     │
│  ISP:          NOS Comunicações                                            │
│                                                                            │
│  ── ACESSO ──                                                              │
│  Status:      🟢 LIVE                                                      │
│  Auth:        ✅ admin:12345 (default)                                    │
│  RTSP URL:    rtsp://admin:12345@188.81.XX.XXX:554/Streaming/Channels/101 │
│  Web admin:   http://188.81.XX.XXX                                        │
│  ONVIF:       ✅ Suportado                                                 │
│  PTZ:         ❌ Não suportado                                             │
│                                                                            │
│  ── STREAM ──                                                              │
│  Codec:       H.265                                                        │
│  Resolução:   1920x1080                                                    │
│  FPS:         25                                                           │
│  Bitrate:     4.2 Mbps                                                    │
│                                                                            │
│  ── SNAPSHOT ──                                                            │
│  ┌──────────────────────────────────────────────┐                         │
│  │                                              │                         │
│  │           🖼️  SCREENSHOT 2026-06-24          │                         │
│  │           ┌──────────────────┐               │                         │
│  │           │  IMAGEM CAPTADA  │               │                         │
│  │           │  DO STREAM RTSP  │               │                         │
│  │           └──────────────────┘               │                         │
│  │                                              │                         │
│  └──────────────────────────────────────────────┘                         │
│                                                                            │
│  [S] Screenshot  [V] Abrir no VLC  [O] OpenCV full  [C] Copy URL         │
├────────────────────────────────────────────────────────────────────────────┤
│  📸 Screenshot saved: data/screenshots/188.81.XX.XXX_2026-06-24.png       │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.6 TUI — Export Preview (ao pressionar `E`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  📤 EXPORTAR RESULTADOS                           [ESC] Voltar            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Seleciona formato:                                                        │
│                                                                            │
│  [1] JSON          → data/report.json              (dados completos)      │
│  [2] CSV           → data/report.csv              (tabela simples)        │
│  [3] HTML          → data/report.html             (relatório bonito)      │
│  [4] M3U Playlist  → data/streams.m3u             (abrir no VLC)          │
│  [5] TXT           → data/report.txt              (lista IPs)             │
│  [6] Todos os formatos                                                     │
│                                                                            │
│  ── PREVIEW (JSON) ──                                                      │
│  {                                                                         │
│    "scan_id": "2026-06-24-013322",                                         │
│    "timestamp": "2026-06-24T01:33:22Z",                                    │
│    "total_ips": 1247,                                                      │
│    "accessible": 23,                                                        │
│    "cameras": [                                                            │
│      {                                                                     │
│        "ip": "188.81.XX.XXX",                                              │
│        "port": 554,                                                        │
│        "vendor": "Hikvision",                                               │
│        "model": "DS-2CD2386G2-I",                                          │
│        "auth": true,                                                       │
│        "user": "admin",                                                    │
│        "pass": "12345",                                                    │
│        "rtsp_url": "rtsp://admin:12345@188.81.XX.XXX:554/Streaming/...",   │
│        "country": "PT",                                                    │
│        "city": "Lisbon",                                                   │
│        "lat": 38.7223,                                                     │
│        "lon": -9.1393,                                                     │
│        "resolution": "1920x1080",                                          │
│        "codec": "H.265",                                                   │
│        "fps": 25                                                           │
│      },                                                                    │
│      ...                                                                   │
│    ]                                                                       │
│  }                                                                         │
│                                                                            │
│  [ENTER] Exportar  [1-6] Formato  [ESC] Voltar                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.7 Web Dashboard — Design

### Layout Geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🦾 PROCURADOR  v1.0          [Scanning...]    ⚡ 1247 IPs  📍 12 países  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  📹 Câmaras  │  │  🔓 Acessos  │  │  🚫 Bloqueadas│  │  ⏱️ Tempo    │   │
│  │     1,247    │  │      23      │  │     1,224     │  │   2m 34s     │   │
│  │  Descobertas  │  │  Live agora  │  │  Sem acesso  │  │  Scan total  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  🌍 MAPA INTERATIVO                 [Filtros: 🇵🇹 Portugal ▼]       │   │
│  │                                                                     │   │
│  │        ╔═══════════════════════════════════════════╗                │   │
│  │        ║                                           ║                │   │
│  │        ║           MAPA FOLIUM                     ║                │   │
│  │        ║    Com marcadores de câmaras              ║                │   │
│  │        ║    Clusters por densidade                 ║                │   │
│  │        ║    Click no marcador → detalhe            ║                │   │
│  │        ║                                           ║                │   │
│  │        ╚═══════════════════════════════════════════╝                │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─ Tabela de Câmaras (10 por página) ─────────────────────────────────┐   │
│  │  IP            Fabricante   Porta  Status    Resolução   Ações      │   │
│  │  ─────────────────────────────────────────────────────────────────  │   │
│  │  188.81.XX.XXX Hikvision    554    🟢 LIVE   1920x1080  [▶] [📸]   │   │
│  │  188.81.XX.XXY Dahua        554    🟡 AUTH   1280x720   [▶] [📸]   │   │
│  │  85.242.XX.XXX Axis         554    🔴 DOWN   N/A        [▶] [📸]   │   │
│  │  ...                                                                  │   │
│  │                                                                     │   │
│  │  [<< Anterior]  1  2  3 ... 25  [Seguinte >>]                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─ Gráficos ─────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  🔵 Câmaras por Fabricante     🟢 Câmaras por País                │   │
│  │  ┌──────────────────────┐     ┌──────────────────────┐            │   │
│  │  │  Hikvision ████████  │     │  Portugal ██████████ │            │   │
│  │  │  Dahua     ██████    │     │  Espanha  ████       │            │   │
│  │  │  Axis      ████      │     │  França   ███        │            │   │
│  │  │  Reolink   ██        │     │  UK       ██         │            │   │
│  │  │  TP-Link   ██        │     │  Outros   ██         │            │   │
│  │  └──────────────────────┘     └──────────────────────┘            │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  📡 A atualizar a cada 30s  |  📤 Export: [JSON] [CSV] [HTML] [M3U]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.8 Web Dashboard — Página de Streams

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📺 LIVE STREAMS    23 acessíveis     ⏺ A gravar 0                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                   │
│  │  ▶   │ │  ▶   │ │  ▶   │ │  ▶   │ │  ▶   │ │  ▶   │                   │
│  │ img1 │ │ img2 │ │ img3 │ │ img4 │ │ img5 │ │ img6 │                   │
│  │Hikv. │ │Dahua │ │Reol. │ │Axis  │ │TpLnk │ │Fosc. │                   │
│  │1080p │ │720p  │ │4K    │ │1080p │ │480p  │ │720p  │                   │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                   │
│                                                                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                   │
│  │  ▶   │ │  ▶   │ │  ▶   │ │  ▶   │ │  ▶   │ │  ▶   │                   │
│  │ img7 │ │ img8 │ │ img9 │ │ img10│ │ img11│ │ img12│                   │
│  │Bosch │ │Hikv. │ │Dahua │ │Hikv. │ │Axis  │ │Reol. │                   │
│  │1080p │ │4K    │ │720p  │ │1080p │ │720p  │ │1080p │                   │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                   │
│                                                                             │
│  [Ver todas] [Screenshots] [Exportar playlist M3U]                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.9 Web Dashboard — Detalhe da Câmara

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📹 Detalhe da Câmara: 188.81.XX.XXX  ← Voltar                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────────────────────────────────┐   │
│  │                  │  │  📍 Localização:  Lisboa, Portugal 🇵🇹       │   │
│  │   🖼️ LIVE VIEW   │  │  📡 ISP:          NOS Comunicações          │   │
│  │                  │  │  🏭 Fabricante:    Hikvision DS-2CD2386G2-I │   │
│  │   Frame atual    │  │  🔢 IP:            188.81.XX.XXX            │   │
│  │   do stream      │  │  🚪 Porta:         554                      │   │
│  │   RTSP           │  │  🔐 Auth:          admin:12345              │   │
│  │                  │  │  📺 Resolução:      1920x1080 @ 25 FPS      │   │
│  └──────────────────┘  │  🎞️ Codec:          H.265                   │   │
│                        │  💾 Bitrate:        4.2 Mbps                │   │
│                        │                                              │   │
│                        │  ── Ações ──                                 │   │
│                        │  [▶] Abrir stream   [📸] Screenshot          │   │
│                        │  [📋] Copiar URL    [🌐] Web admin          │   │
│                        │  [⬇] Download       [📤] Export             │   │
│                        └──────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─ RTSP URL ──────────────────────────────────────────────────────────┐   │
│  │  rtsp://admin:12345@188.81.XX.XXX:554/Streaming/Channels/101       │   │
│  │  [📋 Copiar]                                                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─ Screenshots ───────────────────────────────────────────────────────┐   │
│  │  [2026-06-24 01:33:22]  [2026-06-24 01:33:52]  [2026-06-24 01:34:22]│   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2.10 Paleta de Cores

### TUI
```css
--bg:        #0a0a0a     (fundo preto profundo)
--fg:        #00ff00     (verde matrix para texto normal)
--fg-bright: #00ff66     (verde claro para destaque)
--accent:    #00ffff     (ciano para bordas, separadores)
--warn:      #ffaa00     (laranja para AVISO)
--error:     #ff3333     (vermelho para ERRO)
--success:   #00ff44     (verde para SUCESSO)
--muted:     #555555     (cinza para metadados)
--highlight: #ffffff     (branco para títulos)
```

### Web
```css
--bg-dark:     #0f1117     (fundo escuro)
--bg-card:     #1a1d27     (cards)
--bg-card-hov: #242736     (cards hover)
--border:      #2a2d3a     (bordas)
--text:        #e0e0e0     (texto principal)
--text-dim:    #6b7280     (texto secundário)
--primary:     #00d4ff     (azul ciano primário)
--success:     #10b981     (verde)
--warning:     #f59e0b     (laranja)
--danger:      #ef4444     (vermelho)
--glass:       rgba(255,255,255,0.03)  (efeito glass)
```

---

## 2.11 Ícones/Emojis Usados

```
📡  Scan / Rede
📹  Câmara
🖼️  Frame / Screenshot
✅  Acesso OK
🔒  Precisa auth
❌  Bloqueado/Fechado
🟢  Live / Online
🟡  AUTH / Precisa creds
🔴  Down / Offline
🌐  Web admin
📍  Localização
🇵🇹  Bandeira do país
▶   Play stream
📸  Screenshot
📋  Copiar
⚡  Métrica
🎞️  Codec / Vídeo
💾  Disco / Bitrate
🔍  Busca / Scan
🗺️  Mapa
📤  Export
🏭  Fabricante
```

---

> Seguir para o documento 03 — ARQUITETURA
