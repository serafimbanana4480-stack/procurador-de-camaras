# 06 — FASE 2: DASHBOARD

> Duração estimada: 2-3 dias
> Objetivo: Interface TUI rica com Rich + Web dashboard com Flask

---

## 6.1 TUI Dashboard — Estrutura

### `procurador/ui/tui.py`

```python
"""
Dashboard TUI com Rich.
Mostra estatísticas, tabela de câmaras, log de atividades em tempo real.
"""
import time
import logging
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.columns import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.syntax import Syntax
from rich import box
from rich.style import Style

from procurador.core.models import ScanResult, Camera, CameraStatus

logger = logging.getLogger(__name__)

# Cores por status
STATUS_COLORS = {
    CameraStatus.LIVE: "green",
    CameraStatus.AUTH_REQUIRED: "yellow",
    CameraStatus.AUTH_FAILED: "red",
    CameraStatus.CLOSED: "dim",
    CameraStatus.ERROR: "red bold",
    CameraStatus.PENDING: "blue",
    CameraStatus.SCANNING: "cyan",
}

STATUS_ICONS = {
    CameraStatus.LIVE: "🟢",
    CameraStatus.AUTH_REQUIRED: "🟡",
    CameraStatus.AUTH_FAILED: "🔴",
    CameraStatus.CLOSED: "⚫",
    CameraStatus.ERROR: "❌",
    CameraStatus.PENDING: "⏳",
    CameraStatus.SCANNING: "🔄",
}


class ProcuradorTUI:
    """
    Dashboard TUI principal.

    Layout:
    ┌─────────────────────────────────────────────────────┐
    │  HEADER (título + stats rápidas)                    │
    ├─────────────────────────────────────────────────────┤
    │  STATS PANEL (4 métricas principais)                │
    ├─────────────────────────────────────────────────────┤
    │  TABLE: câmaras encontradas                         │
    ├─────────────────────────────────────────────────────┤
    │  LOG: últimos eventos + barra de progresso          │
    ├─────────────────────────────────────────────────────┤
    │  FOOTER: atalhos de teclado                         │
    └─────────────────────────────────────────────────────┘
    """

    def __init__(self, result: ScanResult):
        self.result = result
        self.console = Console()
        self.layout = Layout()
        self.start_time = time.time()
        self.log_lines: list[str] = []
        self.selected_index = 0
        self.mode = "main"  # main | detail | streams | map

    def run(self):
        """Iniciar dashboard TUI."""
        self._setup_layout()

        try:
            with Live(
                self._render,
                console=self.console,
                screen=True,
                auto_refresh=False,
                refresh_per_second=4,
            ) as live:
                self.live = live
                self._handle_input()
        except KeyboardInterrupt:
            pass

    def _setup_layout(self):
        """Configurar layout inicial."""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        self.layout["body"].split_row(
            Layout(name="stats", size=30),
            Layout(name="main"),
        )
        self.layout["body"]["main"].split_column(
            Layout(name="table"),
            Layout(name="log", size=8),
        )

    def _render(self) -> Layout:
        """Renderizar layout completo."""
        self.layout["header"].update(self._render_header())
        self.layout["body"]["stats"].update(self._render_stats())
        self.layout["body"]["main"]["table"].update(self._render_table())
        self.layout["body"]["main"]["log"].update(self._render_log())
        self.layout["footer"].update(self._render_footer())
        return self.layout

    def _render_header(self) -> Panel:
        """Header com título e informações gerais."""
        elapsed = time.time() - self.start_time
        elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

        title = Text()
        title.append("📹 ", style="bold")
        title.append("PROCURADOR DE CÂMERA", style="bold cyan")
        title.append(f"  v1.0", style="dim")

        info = Text()
        info.append(f"  ⏱️  {elapsed_str}", style="green")
        live_count = self.result.accessible
        info.append(f"  🟢 {live_count} live", style="green")
        info.append(f"  📡 {self.result.total_ips} IPs", style="cyan")
        info.append(f"  🌍 {len(self.result.countries)} países", style="yellow")

        content = Columns([title, info])

        return Panel(
            content,
            style="bold",
            border_style="cyan",
        )

    def _render_stats(self) -> Panel:
        """Painel de estatísticas principais."""
        stats = Table.grid(padding=(0, 2))
        stats.add_column(style="bold", width=14)
        stats.add_column(style="bold", width=8)

        stats.add_row(
            Text("📡 Total IPs", style="cyan"),
            Text(str(self.result.total_ips), style="bold white"),
        )
        stats.add_row("")
        stats.add_row(
            Text("🟢 Live", style="green"),
            Text(str(self.result.accessible), style="bold green"),
        )
        stats.add_row(
            Text("🟡 Auth", style="yellow"),
            Text(str(self.result.auth_required), style="bold yellow"),
        )
        stats.add_row(
            Text("🔴 Closed", style="red"),
            Text(str(self.result.closed), style="bold red"),
        )
        stats.add_row(
            Text("❌ Errors", style="red"),
            Text(str(self.result.errors), style="bold red"),
        )
        stats.add_row("")
        stats.add_row(
            Text("📸 Streams", style="magenta"),
            Text(str(self.result.live_streams), style="bold magenta"),
        )

        # Top vendors
        if self.result.vendors:
            stats.add_row("")
            stats.add_row(Text("🏭 FABRICANTES", style="underline cyan"))
            for vendor, count in list(self.result.vendors.items())[:6]:
                bar_len = int(count / max(self.result.vendors.values()) * 10)
                bar = "█" * bar_len + "░" * (10 - bar_len)
                stats.add_row(
                    Text(f"  {vendor[:12]}", style="white"),
                    Text(f"{bar} {count}", style="dim"),
                )

        return Panel(
            stats,
            title="📊 ESTATÍSTICAS",
            border_style="cyan",
            padding=(1, 2),
        )

    def _render_table(self) -> Panel:
        """Tabela de câmaras encontradas."""
        table = Table(
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
            show_lines=True,
            padding=(0, 1),
        )

        table.add_column("Status", width=4, no_wrap=True)
        table.add_column("IP", width=15, no_wrap=True)
        table.add_column("Fabricante", width=12, no_wrap=True)
        table.add_column("Porta", width=5, no_wrap=True)
        table.add_column("Resolução", width=10)
        table.add_column("País", width=8)
        table.add_column("Creds", width=14)

        # Mostrar primeiras 20 câmaras (LIVE primeiro, ordenado)
        sorted_cameras = sorted(
            self.result.cameras,
            key=lambda c: (
                0 if c.status == CameraStatus.LIVE else
                1 if c.status == CameraStatus.AUTH_REQUIRED else
                2 if c.status == CameraStatus.AUTH_FAILED else
                3 if c.status == CameraStatus.CLOSED else 4,
                c.ip,
            ),
        )

        for cam in sorted_cameras[:20]:
            icon = STATUS_ICONS.get(cam.status, "❓")
            color = STATUS_COLORS.get(cam.status, "white")
            vendor = cam.vendor or "Unknown"
            resolution = cam.resolution if cam.resolution != "N/A" else "?"

            country = cam.geo.country_code or (cam.geo.country[:2] if cam.geo.country else "??")
            creds = f"{cam.auth_user}:{cam.auth_pass}" if cam.auth_success else (
                "✅ default" if not cam.auth_required else "🔒 locked"
            )

            table.add_row(
                Text(icon, style=color),
                Text(cam.ip, style="bold white"),
                Text(vendor, style="cyan" if cam.vendor else "dim"),
                Text(str(cam.port), style="yellow"),
                Text(resolution, style="green" if cam.stream and cam.stream.width > 0 else "dim"),
                Text(country, style="yellow"),
                Text(creds, style="green" if cam.auth_success else "yellow" if cam.auth_required else "red"),
            )

        # Se houver mais que 20, indicar
        remaining = len(self.result.cameras) - 20
        if remaining > 0:
            table.add_row(
                "...", "...", "...", "...", "...", "...",
                Text(f"+ {remaining} mais", style="dim italic"),
            )

        return Panel(
            table,
            title="📹 CÂMARAS ENCONTRADAS",
            border_style="cyan",
            padding=(0, 1),
        )

    def _render_log(self) -> Panel:
        """Painel de log com últimos eventos."""
        now = datetime.now().strftime("%H:%M:%S")
        log_text = Text()

        # Eventos simulados (numa versão real, viriam de um buffer circular)
        events = [
            f"[{now}] ✅ Scan concluído — {self.result.accessible} live",
            f"[{now}] 📸 Screenshots: {self.result.live_streams} capturadas",
            f"[{now}] 🌍 Países: {len(self.result.countries)}",
            f"[{now}] 🏭 Fabricantes: {len(self.result.vendors)}",
        ]

        if self.result.auth_failed > 0:
            events.append(f"[{now}] 🔒 {self.result.auth_failed} câmaras sem creds válidas")

        for event in events[-6:]:
            log_text.append(event + "\n", style="dim white")

        return Panel(
            log_text,
            title="📋 ATIVIDADE",
            border_style="dim",
            padding=(0, 1),
        )

    def _render_footer(self) -> Panel:
        """Rodapé com atalhos."""
        shortcuts = Text()
        shortcuts.append(" [Ctrl+C] Sair  ", style="bold white")
        shortcuts.append(" [S] Streams  ", style="cyan")
        shortcuts.append(" [M] Mapa  ", style="green")
        shortcuts.append(" [E] Export  ", style="yellow")
        shortcuts.append(" [R] Refresh  ", style="blue")
        shortcuts.append(" [D] Detalhe  ", style="magenta")
        shortcuts.append(" [H] Help", style="dim")

        return Panel(
            Align.center(shortcuts),
            style="bold",
            border_style="cyan",
        )

    def _handle_input(self):
        """Handler de input do teclado (simplificado)."""
        # Numa versão real: usar getch ou pynput
        # Por agora: refresh automático a cada 2s
        import time as t
        while True:
            t.sleep(2)
            self.live.update(self._render)
```

---

## 6.2 TUI Stream Grid

### `procurador/ui/tui_stream.py`

```python
"""
Grid de streams TUI.
Mostra miniaturas das câmaras ao vivo com OpenCV.
Usa rich + opencv para criar um grid visual.
"""
import io
import logging
from pathlib import Path

import cv2
import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich import box

from procurador.core.models import ScanResult, CameraStatus

logger = logging.getLogger(__name__)

# Tamanho das miniaturas
THUMB_WIDTH = 160
THUMB_HEIGHT = 120


class StreamGrid:
    """
    Grid de streams ao vivo.
    Mostra 6 câmaras de cada vez (2 linhas x 3 colunas).
    """

    def __init__(self, result: ScanResult):
        self.result = result
        self.console = Console()
        self.live_cameras = [
            c for c in result.cameras
            if c.status == CameraStatus.LIVE and c.rtsp_url
        ]
        self.page = 0
        self.items_per_page = 6  # 2x3 grid

    def run(self):
        """Iniciar grid de streams."""
        total_pages = max(1, (len(self.live_cameras) + self.items_per_page - 1) // self.items_per_page)

        try:
            with Live(auto_refresh=False, console=self.console, screen=True) as live:
                while True:
                    start = self.page * self.items_per_page
                    end = start + self.items_per_page
                    page_cams = self.live_cameras[start:end]

                    grid = self._render_grid(page_cams, self.page + 1, total_pages)
                    live.update(grid)

                    # Refresh a cada 5s
                    import time as t
                    t.sleep(5)

        except KeyboardInterrupt:
            pass

    def _render_grid(self, cameras, page_num: int, total_pages: int) -> Layout:
        """Renderizar grid 2x3 de streams."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="grid"),
            Layout(name="footer", size=3),
        )

        # Header
        header = Text()
        header.append("📺 LIVE STREAMS", style="bold cyan")
        header.append(f"  Página {page_num}/{total_pages}", style="dim")
        header.append(f"  |  {len(self.live_cameras)} streams ativos", style="green")
        layout["header"].update(Panel(header, border_style="cyan"))

        # Grid 2x3
        grid_table = Table.grid(padding=(1, 2))
        grid_table.add_column()
        grid_table.add_column()
        grid_table.add_column()

        # Dividir em linhas de 3
        for row_start in range(0, len(cameras), 3):
            row_cams = cameras[row_start:row_start + 3]
            cols = []
            for cam in row_cams:
                cols.append(self._render_cam_card(cam))
            # Preencher colunas vazias se necessário
            while len(cols) < 3:
                cols.append(Panel("", border_style="dim", height=15))
            grid_table.add_row(*cols)

        layout["grid"].update(grid_table)

        # Footer
        footer = Text()
        footer.append(" [← →] Navegar página  ", style="bold")
        footer.append(" [ENTER] Ver detalhe  ", style="cyan")
        footer.append(" [S] Screenshot  ", style="green")
        footer.append(" [V] Abrir VLC  ", style="yellow")
        footer.append(" [ESC] Voltar", style="dim")
        layout["footer"].update(Panel(footer, border_style="cyan"))

        return layout

    def _render_cam_card(self, cam) -> Panel:
        """Renderizar card de uma câmara no grid."""
        # Tentar carregar screenshot se existir
        screenshot_text = "  🖼️  LIVE  \n  📹  STREAM"
        if cam.screenshot_path:
            screenshot_text = f"  📸 {Path(cam.screenshot_path).name}"

        info = Text()
        info.append(f"{cam.ip}\n", style="bold cyan")
        info.append(f"{cam.vendor or 'Unknown'}", style="white")
        info.append(f"  {cam.resolution}", style="dim")
        if cam.stream and cam.stream.fps:
            info.append(f"  {cam.stream.fps:.0f}fps", style="green")

        content = Text(f"\n{screenshot_text}\n\n", style="bold green")
        content.append(info)

        return Panel(
            Align.center(content),
            border_style="green",
            height=15,
            title=f"📹 {cam.vendor or 'Cam'}",
            title_align="left",
        )


# Helper para centralizar texto
class Align:
    """Centralizar texto num painel (simplificado)."""
    @staticmethod
    def center(text) -> str:
        return str(text)
```

---

## 6.3 Web Dashboard

### `procurador/ui/web/app.py`

```python
"""
Web dashboard com Flask + HTMX + Tailwind.

Endpoints:
  /              → Dashboard principal
  /streams       → Grid de streams
  /camera/<ip>   → Detalhe da câmara
  /map           → Mapa interativo
  /export/<fmt>  → Export (json, csv, html, m3u)
  /api/cameras   → API JSON (para HTMX)
"""
import json
import logging
from pathlib import Path
from threading import Thread

from flask import Flask, render_template, jsonify, send_file, request

from procurador.core.models import ScanResult, CameraStatus
from procurador.export.json_export import export_json
from procurador.export.html_report import export_html
from procurador.export.m3u import export_m3u
from procurador.export.csv_export import export_csv

logger = logging.getLogger(__name__)


def create_app(result: ScanResult) -> Flask:
    """Criar app Flask com os dados do scan."""
    app = Flask(__name__,
                template_folder=Path(__file__).parent / "templates",
                static_folder=Path(__file__).parent / "static")

    @app.route("/")
    def dashboard():
        """Página principal do dashboard."""
        return render_template(
            "dashboard.html",
            result=result,
            stats={
                "total": result.total_ips,
                "live": result.accessible,
                "auth": result.auth_required,
                "closed": result.closed,
                "errors": result.errors,
                "streams": result.live_streams,
                "vendors": result.vendors,
                "countries": result.countries,
            },
            cameras=[c for c in result.cameras if c.status in (
                CameraStatus.LIVE, CameraStatus.AUTH_REQUIRED
            )][:50],
        )

    @app.route("/streams")
    def streams():
        """Grid de streams ao vivo."""
        live_cams = [c for c in result.cameras if c.status == CameraStatus.LIVE]
        return render_template("streams.html", cameras=live_cams)

    @app.route("/camera/<ip>")
    def camera_detail(ip: str):
        """Detalhe de uma câmara específica."""
        cam = next((c for c in result.cameras if c.ip == ip), None)
        if not cam:
            return "Câmara não encontrada", 404
        return render_template("camera_detail.html", camera=cam)

    @app.route("/map")
    def map_view():
        """Mapa interativo com Folium."""
        from procurador.ui.web.map_export import create_map

        # Gerar mapa
        map_html = create_map(result)

        # Guardar temporariamente
        maps_dir = Path("data/maps")
        maps_dir.mkdir(parents=True, exist_ok=True)
        map_path = maps_dir / "map.html"

        with open(map_path, "w", encoding="utf-8") as f:
            f.write(map_html)

        return send_file(str(map_path))

    @app.route("/export/<fmt>")
    def export(fmt: str):
        """Exportar resultados em vários formatos."""
        export_dir = Path("data/exports")
        export_dir.mkdir(parents=True, exist_ok=True)

        if fmt == "json":
            path = export_json(result, export_dir)
            return send_file(str(path), as_attachment=True)
        elif fmt == "csv":
            path = export_csv(result, export_dir)
            return send_file(str(path), as_attachment=True)
        elif fmt == "html":
            path = export_html(result, export_dir)
            return send_file(str(path), as_attachment=True)
        elif fmt == "m3u":
            path = export_m3u(result, export_dir)
            return send_file(str(path), as_attachment=True)
        else:
            return "Formato não suportado", 400

    @app.route("/api/cameras")
    def api_cameras():
        """API JSON para HTMX refresh."""
        return jsonify([
            {
                "ip": c.ip,
                "vendor": c.vendor,
                "status": c.status.value,
                "resolution": c.resolution,
                "country": c.geo.country_code or c.geo.country,
                "auth": c.auth_success,
            }
            for c in result.cameras[:50]
        ])

    return app


def run_web(result: ScanResult, host: str = "127.0.0.1", port: int = 5000):
    """Iniciar web dashboard em background thread."""
    app = create_app(result)

    # Abrir browser automaticamente
    import webbrowser
    webbrowser.open(f"http://{host}:{port}")

    app.run(host=host, port=port, debug=False)
```

---

## 6.4 Web Templates

### `procurador/ui/web/templates/dashboard.html`

```html
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📹 Procurador de Câmara</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.6"></script>
    <script src="https://unpkg.com/alpinejs@3.13.0" defer></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

        body {
            font-family: 'JetBrains Mono', monospace;
            background: #0f1117;
            color: #e0e0e0;
        }

        .glass-card {
            background: rgba(26, 29, 39, 0.8);
            border: 1px solid #2a2d3a;
            backdrop-filter: blur(10px);
            border-radius: 12px;
        }

        .stat-card {
            @apply glass-card p-4 text-center;
            transition: transform 0.2s, border-color 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            border-color: #00d4ff;
        }

        .status-live { color: #10b981; }
        .status-auth { color: #f59e0b; }
        .status-closed { color: #6b7280; }
        .status-error { color: #ef4444; }

        .neon-border {
            border: 1px solid rgba(0, 212, 255, 0.3);
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.1);
        }

        .btn-primary {
            @apply px-4 py-2 rounded-lg font-bold text-sm;
            background: linear-gradient(135deg, #00d4ff, #0077ff);
            color: white;
            transition: all 0.2s;
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3);
        }

        /* Scrollbar custom */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1a1d27; }
        ::-webkit-scrollbar-thumb { background: #2a2d3a; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #3a3d4a; }
    </style>
</head>
<body class="p-6">
    <div class="max-w-7xl mx-auto" x-data="{ refreshInterval: 30 }">
        <!-- Header -->
        <div class="flex items-center justify-between mb-6">
            <div class="flex items-center gap-3">
                <h1 class="text-2xl font-bold text-cyan-400">📹 PROCURADOR DE CÂMERA</h1>
                <span class="text-gray-500 text-sm">v1.0</span>
            </div>
            <div class="flex items-center gap-4">
                <div class="flex items-center gap-2 text-sm">
                    <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                    <span class="text-gray-400" x-text="`A atualizar a cada ${refreshInterval}s`"></span>
                </div>
                <div class="flex gap-2">
                    <a href="/export/json" class="btn-primary">📥 JSON</a>
                    <a href="/export/html" class="btn-primary">📥 HTML</a>
                    <a href="/export/m3u" class="btn-primary">📥 M3U</a>
                </div>
            </div>
        </div>

        <!-- Stats Cards -->
        <div class="grid grid-cols-6 gap-4 mb-6">
            <div class="stat-card">
                <div class="text-3xl font-bold text-cyan-400">{{ stats.total }}</div>
                <div class="text-sm text-gray-400 mt-1">📡 IPs Descobertos</div>
            </div>
            <div class="stat-card">
                <div class="text-3xl font-bold text-green-400">{{ stats.live }}</div>
                <div class="text-sm text-gray-400 mt-1">🟢 Live</div>
            </div>
            <div class="stat-card">
                <div class="text-3xl font-bold text-yellow-400">{{ stats.auth }}</div>
                <div class="text-sm text-gray-400 mt-1">🟡 Auth</div>
            </div>
            <div class="stat-card">
                <div class="text-3xl font-bold text-gray-400">{{ stats.closed }}</div>
                <div class="text-sm text-gray-400 mt-1">⚫ Closed</div>
            </div>
            <div class="stat-card">
                <div class="text-3xl font-bold text-red-400">{{ stats.errors }}</div>
                <div class="text-sm text-gray-400 mt-1">❌ Erros</div>
            </div>
            <div class="stat-card">
                <div class="text-3xl font-bold text-cyan-400">{{ stats.streams }}</div>
                <div class="text-sm text-gray-400 mt-1">📸 Streams</div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="grid grid-cols-3 gap-6">
            <!-- Left: Camera Table -->
            <div class="col-span-2 glass-card p-4">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-lg font-bold text-cyan-400">📹 Câmaras</h2>
                    <div class="flex gap-2">
                        <select class="bg-gray-800 text-sm px-3 py-1 rounded border border-gray-700" 
                                @change="window.location = '?status=' + $event.target.value">
                            <option value="">Todos</option>
                            <option value="live">🟢 Live</option>
                            <option value="auth">🟡 Auth</option>
                        </select>
                    </div>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-gray-400 border-b border-gray-700">
                                <th class="py-2 text-left">Status</th>
                                <th class="py-2 text-left">IP</th>
                                <th class="py-2 text-left">Fabricante</th>
                                <th class="py-2 text-left">Porta</th>
                                <th class="py-2 text-left">Resolução</th>
                                <th class="py-2 text-left">País</th>
                                <th class="py-2 text-left">Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for cam in cameras %}
                            <tr class="border-b border-gray-800 hover:bg-gray-800/50 transition cursor-pointer"
                                onclick="window.location='/camera/{{ cam.ip }}'">
                                <td class="py-2">
                                    {% if cam.status.value == 'live' %}
                                    <span class="status-live">🟢</span>
                                    {% elif cam.status.value == 'auth' %}
                                    <span class="status-auth">🟡</span>
                                    {% elif cam.status.value == 'closed' %}
                                    <span class="status-closed">⚫</span>
                                    {% else %}
                                    <span class="status-error">🔴</span>
                                    {% endif %}
                                </td>
                                <td class="py-2 font-mono text-white">{{ cam.ip }}</td>
                                <td class="py-2">{{ cam.vendor or 'Unknown' }}</td>
                                <td class="py-2">{{ cam.port }}</td>
                                <td class="py-2">{{ cam.resolution }}</td>
                                <td class="py-2">
                                    {% if cam.geo.country_code %}
                                    <span title="{{ cam.geo.country }}">
                                        {{ cam.geo.country_code }}
                                    </span>
                                    {% else %}
                                    <span class="text-gray-500">??</span>
                                    {% endif %}
                                </td>
                                <td class="py-2">
                                    {% if cam.status.value == 'live' and cam.rtsp_url %}
                                    <a href="/camera/{{ cam.ip }}" 
                                       class="text-cyan-400 hover:text-cyan-300 mr-2">▶ Ver</a>
                                    {% endif %}
                                    <a href="/camera/{{ cam.ip }}" 
                                       class="text-gray-400 hover:text-white">📋</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

                {% if cameras|length == 0 %}
                <div class="text-center py-8 text-gray-500">
                    Nenhuma câmara encontrada. Inicia um scan.
                </div>
                {% endif %}
            </div>

            <!-- Right: Charts -->
            <div class="space-y-4">
                <!-- Vendor Chart -->
                <div class="glass-card p-4">
                    <h3 class="text-sm font-bold text-gray-400 mb-3">🏭 Por Fabricante</h3>
                    <canvas id="vendorChart" height="200"></canvas>
                </div>

                <!-- Country Chart -->
                <div class="glass-card p-4">
                    <h3 class="text-sm font-bold text-gray-400 mb-3">🌍 Por País</h3>
                    <canvas id="countryChart" height="200"></canvas>
                </div>

                <!-- Live Streams -->
                <div class="glass-card p-4">
                    <h3 class="text-sm font-bold text-cyan-400 mb-3">📺 Streams Live</h3>
                    <div class="grid grid-cols-2 gap-2">
                        {% for cam in cameras if cam.status.value == 'live' %}
                        {% if loop.index <= 4 %}
                        <div class="bg-gray-800 rounded p-2 text-center">
                            <div class="text-xs text-gray-400 truncate">{{ cam.ip }}</div>
                            <div class="text-xs text-cyan-400">{{ cam.resolution }}</div>
                        </div>
                        {% endif %}
                        {% endfor %}
                    </div>
                    {% if stats.streams > 4 %}
                    <div class="text-center mt-2">
                        <a href="/streams" class="text-sm text-cyan-400 hover:underline">
                            + {{ stats.streams - 4 }} mais →
                        </a>
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>

    <script>
    // Vendor Chart
    new Chart(document.getElementById('vendorChart'), {
        type: 'doughnut',
        data: {
            labels: {{ stats.vendors.keys() | list | tojson }},
            datasets: [{
                data: {{ stats.vendors.values() | list | tojson }},
                backgroundColor: [
                    '#00d4ff', '#10b981', '#f59e0b', '#ef4444',
                    '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'
                ],
                borderWidth: 0,
            }]
        },
        options: {
            plugins: {
                legend: { position: 'bottom', labels: { color: '#6b7280', font: { size: 10 } } }
            },
            maintainAspectRatio: false,
        }
    });

    // Country Chart
    new Chart(document.getElementById('countryChart'), {
        type: 'bar',
        data: {
            labels: {{ stats.countries.keys() | list | tojson }},
            datasets: [{
                label: 'Câmaras',
                data: {{ stats.countries.values() | list | tojson }},
                backgroundColor: '#00d4ff',
                borderRadius: 4,
            }]
        },
        options: {
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true, grid: { color: '#1a1d27' }, ticks: { color: '#6b7280' } },
                x: { grid: { display: false }, ticks: { color: '#6b7280' } }
            },
            maintainAspectRatio: false,
        }
    });
    </script>
</body>
</html>
```

---

## 6.5 Mapa Interativo

### `procurador/ui/web/map_export.py`

```python
"""
Gerar mapa interativo com Folium.
Mostra as câmaras encontradas num mapa mundial com clusters.
"""
import logging
from pathlib import Path

import folium
from folium.plugins import MarkerCluster, HeatMap

from procurador.core.models import ScanResult, CameraStatus

logger = logging.getLogger(__name__)


def create_map(result: ScanResult) -> str:
    """
    Criar mapa HTML interativo com todas as câmaras.

    Returns: HTML string do mapa
    """
    # Centro do mapa (médio das coordenadas ou Lisboa)
    lats = [c.geo.lat for c in result.cameras if c.geo.lat]
    lons = [c.geo.lon for c in result.cameras if c.geo.lon]

    if lats and lons:
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
    else:
        center_lat, center_lon = 39.5, -8.0  # Portugal center

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=5,
        tiles="cartodb dark_matter",
        control_scale=True,
    )

    # Marker Cluster para agrupar
    marker_cluster = MarkerCluster(
        options={
            "spiderfyOnMaxZoom": True,
            "showCoverageOnHover": False,
            "maxClusterRadius": 50,
        }
    ).add_to(m)

    # Adicionar marcadores
    for cam in result.cameras:
        if not cam.geo.lat or not cam.geo.lon:
            continue

        # Cor por status
        if cam.status == CameraStatus.LIVE:
            color = "green"
            icon = "video-camera"
        elif cam.status == CameraStatus.AUTH_REQUIRED:
            color = "orange"
            icon = "lock"
        elif cam.status == CameraStatus.AUTH_FAILED:
            color = "red"
            icon = "lock"
        else:
            color = "gray"
            icon = "question"

        popup_html = f"""
        <div style="font-family: monospace; min-width: 200px;">
            <h4 style="color: #00d4ff; margin: 0 0 8px;">📹 {cam.ip}</h4>
            <table style="font-size: 12px;">
                <tr><td><b>Fabricante:</b></td><td>{cam.vendor or 'Unknown'}</td></tr>
                <tr><td><b>Porta:</b></td><td>{cam.port}</td></tr>
                <tr><td><b>Status:</b></td><td>{cam.status.value}</td></tr>
                <tr><td><b>Resolução:</b></td><td>{cam.resolution}</td></tr>
                <tr><td><b>País:</b></td><td>{cam.geo.country or 'Unknown'}</td></tr>
                <tr><td><b>Cidade:</b></td><td>{cam.geo.city or 'Unknown'}</td></tr>
                <tr><td><b>ISP:</b></td><td>{cam.network.isp or 'Unknown'}</td></tr>
            </table>
            <div style="margin-top: 8px;">
                {'✅ ' + cam.auth_user + ':' + cam.auth_pass if cam.auth_success else ''}
            </div>
        </div>
        """

        folium.Marker(
            location=[cam.geo.lat, cam.geo.lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{cam.ip} — {cam.vendor or 'Unknown'}",
            icon=folium.Icon(color=color, icon=icon, prefix="fa"),
        ).add_to(marker_cluster)

    # Heatmap layer (opcional)
    if len(lats) > 5:
        heat_data = [[lat, lon] for lat, lon in zip(lats, lons)]
        HeatMap(
            heat_data,
            min_opacity=0.2,
            max_zoom=10,
            radius=15,
            blur=10,
        ).add_to(m)

    # Fullscreen control
    folium.plugins.Fullscreen().add_to(m)

    # Coordenadas no canto
    folium.LatLngPopup().add_to(m)

    return m.get_root().render()
```

---

## 6.6 Checklist da Fase 2

### TUI Dashboard
- [ ] `tui.py` com layout completo (header, stats, table, log, footer)
- [ ] Live update com `rich.live.Live`
- [ ] Cores por status (verde/live, amarelo/auth, vermelho/erro)
- [ ] Tabela ordenada (LIVE primeiro)
- [ ] Indicadores de fabricante, país, resolução
- [ ] Painel de estatísticas
- [ ] Suporte a teclado (Ctrl+C para sair)

### Stream Grid
- [ ] `tui_stream.py` com grid 2x3 de streams
- [ ] Screenshots das câmaras
- [ ] Informação de resolução e fps
- [ ] Paginação

### Web Dashboard
- [ ] Flask app funcional
- [ ] Template dashboard.html com Tailwind
- [ ] Cards de estatísticas
- [ ] Tabela de câmaras com filtros
- [ ] Gráficos (Chart.js) por fabricante e país
- [ ] Página de detalhe da câmara
- [ ] Mapa interativo (Folium)
- [ ] Export buttons (JSON, HTML, M3U)
- [ ] HTMX para refresh automático

---

> Seguir para o documento 07 — FASE 3: FEATURES
