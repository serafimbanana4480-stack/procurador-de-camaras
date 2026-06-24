# 📑 Índice Completo do Planeamento

> **Projeto:** PROCURADOR DE CÂMERA
> **Data:** 2026-06-24
> **Versão:** 1.0

---

## Documentos

| # | Ficheiro | Descrição |
|---|----------|-----------|
| 00 | `00-INDICE.md` | Este índice |
| 01 | `01-VISAO-GERAL.md` | Visão geral, objetivos, stack tecnológica |
| 02 | `02-DASHBOARD-DESIGN.md` | Design completo do dashboard (TUI + Web) com mockups ASCII |
| 03 | `03-ARQUITETURA.md` | Arquitetura full stack, fluxos de dados, componentes |
| 04 | `04-FASE-0-PESQUISA.md` | Setup do projeto, contas API, ambiente dev |
| 05 | `05-FASE-1-CORE.md` | Motor principal: Censys integration, scanner RTSP, brute engine |
| 06 | `06-FASE-2-DASHBOARD.md` | Implementação do dashboard TUI Rich + Web dashboard |
| 07 | `07-FASE-3-FEATURES.md` | Features avançadas: GeoIP, Shodan, ONVIF, export, VLC playlists |
| 08 | `08-FASE-4-POLISH.md` | Polimento, packaging, deploy, documentação, melhorias |
| 09 | `09-MELHORES-PRATICAS.md` | Boas práticas, segurança, performance, troubleshooting |
| 10 | `10-CODIGO-EXEMPLO.md` | Exemplos de código para cada componente |
| 11 | `11-CHECKLIST.md` | Checklist final de implementação |

---

## Fases do Projeto

```
FASE 0: PESQUISA + SETUP (1 dia)
  ├── Contas API (Censys, Shodan, GeoIP)
  ├── Ambiente Python (venv + dependências)
  ├── Estrutura de pastas
  └── Teste de conectividade APIs

FASE 1: CORE ENGINE (2-3 dias)
  ├── Módulo Censys (query + parse)
  ├── Scanner RTSP (socket DESCRIBE)
  ├── Brute engine (default creds + threads)
  ├── ONVIF probe (WS-Discovery)
  └── Modelos de dados (dataclasses)

FASE 2: DASHBOARD (2-3 dias)
  ├── TUI Rich (tabelas, painéis, live update)
  ├── Stream viewer (OpenCV grid)
  ├── Web dashboard (Flask + HTMX)
  ├── GeoIP + mapa
  └── Export (JSON, CSV, HTML report, M3U)

FASE 3: FEATURES (2 dias)
  ├── Shodan integration
  ├── Scan local (ARP + multicast ONVIF)
  ├── Playlist export (.m3u para VLC)
  ├── Screenshot automation
  └── Optional: PTZ control, motion detection

FASE 4: POLISH (1-2 dias)
  ├── Error handling
  ├── Logging
  ├── Config file
  ├── Packaging (pip installable / EXE)
  ├── Documentação
  └── Testes
```

---

## Stack Tecnológica

```
Frontend TUI:     Rich + Textual (opcional)
Frontend Web:     Flask + HTMX + Alpine.js + Tailwind
Streaming:        OpenCV + ffmpeg
APIs:             Censys, Shodan, geoip2, ipinfo
Scanners:         scapy (LAN), socket (RTSP probe)
Dados:            JSON (local), SQLite (persistência)
Mapa:             Folium / Plotly
Build:            pyinstaller (EXE opcional)
```

---

**Total estimado:** 7-10 dias de desenvolvimento
**Linhas de código estimadas:** 2000-3500
**Dependências:** ~15 pacotes Python

---

> Seguir ordem dos documentos. Cada fase depende da anterior.
