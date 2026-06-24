# 11 — CHECKLIST FINAL DE IMPLEMENTAÇÃO

> Checklist completa para implementar o Procurador de Câmara do zero.
> Usa esta lista para seguir o progresso dia a dia.

---

## 📋 DIA 1 — Setup + Censys + Probe RTSP

### Setup (2h)
- [ ] Criar conta Censys (censys.io)
- [ ] Criar conta ipinfo.io
- [ ] `python -m venv venv` + ativar
- [ ] `pip install -r requirements.txt`
- [ ] `$env:CENSYS_API_ID = "..."` (ou .env)
- [ ] `$env:CENSYS_SECRET = "..."`
- [ ] `$env:IPINFO_TOKEN = "..."`
- [ ] Testar: `python -c "from censys.search import CensysHosts; print('OK')"`

### Models (1h)
- [ ] `procurador/core/models.py` — Camera, CameraStatus, ScanResult
- [ ] Camera.to_dict() para JSON
- [ ] Camera.resolution property
- [ ] Camera.location_str property
- [ ] ScanResult.calculate_stats()

### Censys Module (2h)
- [ ] `procurador/sources/censys.py` — search_censys()
- [ ] identify_vendor() — deteção de fabricante por banner
- [ ] query_builder() — construção de queries
- [ ] Testar com API real: `python -c "from procurador.sources.censys import search_censys; list(search_censys(ScanConfig()))"`

### RTSP Probe (2h)
- [ ] `procurador/core/scanner.py` — probe_rtsp() com socket
- [ ] OPTIONS + DESCRIBE requests
- [ ] Extrair métodos RTSP, server header, SDP
- [ ] scan_camera() — testa paths RTSP
- [ ] scan_batch() — ThreadPoolExecutor
- [ ] Lista completa de RTSP_PATHS por fabricante
- [ ] Testar com câmara real ou mock

### Fim do Dia 1
- [ ] `python -m procurador` corre sem --tui
- [ ] Resultados guardados em data/scan_*.json
- [ ] Logging no terminal

---

## 📋 DIA 2 — Brute + GeoIP + Stream

### Brute Force (2h)
- [ ] `procurador/core/brute.py` — DEFAULT_CREDS por fabricante
- [ ] get_creds_for_vendor() — wordlist específica + genérica
- [ ] try_creds() — DESCRIBE com Basic auth
- [ ] brute_camera() — tenta creds em paralelo
- [ ] brute_batch() — processa câmaras AUTH_REQUIRED
- [ ] Testar com câmara real

### GeoIP (1h)
- [ ] `procurador/core/geoip.py` — GeoIPResolver
- [ ] ipinfo.io integration
- [ ] MaxMind fallback (opcional)
- [ ] Cache LRU com TTL
- [ ] resolve_batch()

### Stream Capture (2h)
- [ ] `procurador/core/stream.py` — capture_stream()
- [ ] OpenCV VideoCapture + screenshot
- [ ] Extrair codec, resolução, fps
- [ ] capture_batch() — ThreadPoolExecutor
- [ ] Guardar screenshots em data/screenshots/

### Main Pipeline (1h)
- [ ] `procurador/__main__.py` — pipeline completo
- [ ] Argumentos CLI (--country, --query, --tui, --web)
- [ ] Fases: collect → probe → brute → geoip → stream → save
- [ ] Graceful shutdown (Ctrl+C)

### Fim do Dia 2
- [ ] Pipeline completo funcional (sem UI)
- [ ] Resultados com GeoIP
- [ ] Screenshots guardadas
- [ ] `python -m procurador --country PT` encontra câmaras

---

## 📋 DIA 3 — TUI Dashboard

### TUI Layout (2h)
- [ ] `procurador/ui/tui.py` — ProcuradorTUI class
- [ ] Layout: header, stats, table, log, footer
- [ ] _render_header() — título + métricas rápidas
- [ ] _render_stats() — painel de 4-6 métricas
- [ ] _render_table() — tabela de câmaras
- [ ] _render_log() — últimos eventos
- [ ] _render_footer() — atalhos de teclado

### TUI Features (2h)
- [ ] Cores por status (Live=🟢, Auth=🟡, Closed=⚫, Error=❌)
- [ ] Tabela ordenada (LIVE primeiro)
- [ ] Máximo 20 câmaras na tabela (+ "X mais")
- [ ] Painel de fabricantes com barras
- [ ] Live update com rich.live.Live
- [ ] Scroll de logs

### TUI Stream Grid (2h)
- [ ] `procurador/ui/tui_stream.py` — StreamGrid
- [ ] Grid 2x3 de streams
- [ ] Informação: IP, fabricante, resolução
- [ ] Paginação

### Fim do Dia 3
- [ ] `python -m procurador --country PT --tui` abre dashboard
- [ ] Tabela com cores
- [ ] Live update funcional
- [ ] Ctrl+C fecha corretamente

---

## 📋 DIA 4 — Web Dashboard

### Flask App (2h)
- [ ] `procurador/ui/web/app.py` — create_app()
- [ ] Rota / — dashboard principal
- [ ] Rota /camera/<ip> — detalhe
- [ ] Rota /streams — grid
- [ ] Rota /api/cameras — JSON
- [ ] Rota /export/<fmt> — download
- [ ] run_web() — start em background

### Templates (2h)
- [ ] dashboard.html — Tailwind + Chart.js
- [ ] Cards de estatísticas (6 métricas)
- [ ] Tabela com filtros
- [ ] Gráfico de fabricantes (doughnut chart)
- [ ] Gráfico de países (bar chart)
- [ ] Grid de streams live
- [ ] camera_detail.html — página de detalhe

### Mapa (1h)
- [ ] `procurador/ui/web/map_export.py` — create_map()
- [ ] Folium dark theme
- [ ] MarkerCluster
- [ ] Popups com info da câmara
- [ ] HeatMap layer

### Fim do Dia 4
- [ ] `python -m procurador --country PT --web` abre browser
- [ ] Dashboard web funcional
- [ ] Mapa com marcadores
- [ ] Export buttons funcionam

---

## 📋 DIA 5 — Export + Features

### Export Modules (1h)
- [ ] `procurador/export/json_export.py` — JSON completo
- [ ] `procurador/export/csv_export.py` — CSV tabela
- [ ] `procurador/export/html_report.py` — relatório HTML
- [ ] `procurador/export/m3u.py` — playlist VLC
- [ ] Todos os exports testados

### Scan Local (1.5h)
- [ ] `procurador/sources/local.py` — ARP scan com scapy
- [ ] Fallback para arp -a
- [ ] ONVIF WS-Discovery
- [ ] scan_local() generator

### ONVIF (1h)
- [ ] `procurador/core/onvif.py` — probe_onvif()
- [ ] Device info (modelo, firmware)
- [ ] Media profiles (streams RTSP)
- [ ] PTZ detection

### Config File (0.5h)
- [ ] `config.toml` completo
- [ ] `procurador/config.py` — load_config()
- [ ] Env vars override

### Fim do Dia 5
- [ ] `python -m procurador --local` escaneia LAN
- [ ] `python -m procurador --country PT --tui` full pipeline
- [ ] Export JSON/CSV/HTML/M3U funcional
- [ ] Config file carregado corretamente

---

## 📋 DIA 6 — Polimento

### Error Handling (1h)
- [ ] try/except em todas as funções públicas
- [ ] retry() decorator com backoff
- [ ] Graceful shutdown em todos os modos
- [ ] Timeouts consistentes

### Logging (1h)
- [ ] `procurador/utils/logger.py` — setup_logger()
- [ ] Logging em todos os módulos
- [ ] Níveis corretos (INFO para progresso, DEBUG para detalhes)
- [ ] Sem passwords/tokens nos logs

### Testes (2h)
- [ ] `tests/test_models.py` — Camera, CameraStatus, ScanResult
- [ ] `tests/test_scanner.py` — probe_rtsp(), scan_camera()
- [ ] Testes com mocks
- [ ] `pytest` passa 100%

### Lint + Format (1h)
- [ ] `ruff check procurador/` — limpo
- [ ] `ruff format procurador/` — formatado
- [ ] `mypy procurador/` — sem erros (ou ignorar opcionais)

### Fim do Dia 6
- [ ] `pytest` — 100% passed
- [ ] `ruff check` — 0 errors
- [ ] `mypy` — 0 errors
- [ ] All edge cases handled

---

## 📋 DIA 7 — Documentação + Packaging

### README (1h)
- [ ] Instalação passo a passo
- [ ] Configuração de API keys
- [ ] Exemplos de uso (--country, --tui, --web)
- [ ] Aviso legal

### Git (0.5h)
- [ ] `.gitignore` completo
- [ ] Primeiro commit
- [ ] Estrutura limpa (sem dados de teste)

### Packaging (2h)
- [ ] `pyproject.toml` completo
- [ ] `pip install -e .` funciona
- [ ] `procurador --help` funciona
- [ ] (Opcional) `pyinstaller --onefile --console ...`
- [ ] EXE funcional em Windows

### Quality Check Final (0.5h)
- [ ] `python -m procurador --help` bonito
- [ ] `python -m procurador --country PT` sem erros
- [ ] `python -m procurador --country PT --tui` sem erros
- [ ] `python -m procurador --country PT --web` sem erros
- [ ] `python -m procurador --local` sem erros

### Fim do Dia 7 — 🚀 RELEASE!
- [ ] Tag v1.0.0
- [ ] Release notes
- [ ] (Opcional) Publicar no GitHub

---

## 📊 RESUMO

| Dia | Foco | Horas | Ficheiros |
|-----|------|-------|-----------|
| 1 | Setup + Models + Censys + Probe | ~7h | 6 |
| 2 | Brute + GeoIP + Stream + Pipeline | ~6h | 4 |
| 3 | TUI Dashboard | ~6h | 2 |
| 4 | Web Dashboard + Mapa | ~5h | 4 |
| 5 | Export + Local + ONVIF + Config | ~4h | 6 |
| 6 | Error handling + Logging + Testes | ~5h | 2 |
| 7 | Doc + Packaging + Release | ~4h | 3 |

**Total:** ~37 horas (1 semana full-time)
**Total ficheiros:** ~25-30
**Total linhas:** ~3000-4000

---

## 🎯 PROGRESSO (copia e cola para acompanhar)

```
Início: [__/__/____]

FASE 0 - Setup:       [░░░░░░░░░░]  0%
FASE 1 - Core Engine: [░░░░░░░░░░]  0%
FASE 2 - Dashboard:   [░░░░░░░░░░]  0%
FASE 3 - Features:    [░░░░░░░░░░]  0%
FASE 4 - Polish:      [░░░░░░░░░░]  0%

TOTAL:                [░░░░░░░░░░]  0%
```

---

> **Boa sorte! 🦾**
> Qualquer dúvida durante a implementação, chama.
