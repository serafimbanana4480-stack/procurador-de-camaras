"""
Dashboard TUI do Procurador de Câmara.

Usa Rich (Layout, Panel, Table, Live) para mostrar:
- Stats principais
- Tabela de câmaras
- Top fabricantes
- Top países
- Log de atividades
"""

from __future__ import annotations

import time

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from procurador.core.models import CameraStatus, ScanResult

# Cores por status
STATUS_COLORS: dict[CameraStatus, str] = {
    CameraStatus.LIVE: "green",
    CameraStatus.AUTH_REQUIRED: "yellow",
    CameraStatus.AUTH_FAILED: "red",
    CameraStatus.CLOSED: "dim",
    CameraStatus.ERROR: "red bold",
    CameraStatus.PENDING: "blue",
    CameraStatus.SCANNING: "cyan",
    CameraStatus.WEB_ONLY: "magenta",
}

STATUS_ICONS: dict[CameraStatus, str] = {
    CameraStatus.LIVE: "🟢",
    CameraStatus.AUTH_REQUIRED: "🟡",
    CameraStatus.AUTH_FAILED: "🔴",
    CameraStatus.CLOSED: "⚫",
    CameraStatus.ERROR: "⚠️ ",
    CameraStatus.PENDING: "🔵",
    CameraStatus.SCANNING: "🔄",
    CameraStatus.WEB_ONLY: "🌐",
}


def _make_header(result: ScanResult) -> Panel:
    """Header com título e stats rápidas."""
    elapsed = time.time() - (result.started_at or time.time())
    elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

    title = Text()
    title.append("🦾 ", style="bold")
    title.append("PROCURADOR DE CÂMARA", style="bold cyan")
    title.append("  v1.0  ", style="dim")
    title.append(f"  scan={result.scan_id}", style="dim")

    info = Text()
    info.append(f" ⏱ {elapsed_str}", style="green")
    info.append(f"  🟢 {result.accessible} live", style="green")
    info.append(f"  🟡 {result.auth_required} auth", style="yellow")
    info.append(f"  🌐 {result.web_only} web", style="magenta")
    info.append(f"  📊 {result.total_ips} IPs", style="cyan")

    return Panel(
        Columns([title, info], align="left"),
        border_style="cyan",
        height=3,
    )


def _make_stats(result: ScanResult) -> Panel:
    """Painel de stats principais (lateral esquerda)."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold", width=18)
    table.add_column(style="bold", width=8)

    def _row(label: str, value: str, color: str) -> None:
        table.add_row(Text(label, style=color), Text(value, style=f"bold {color}"))

    _row("Total IPs", str(result.total_ips), "cyan")
    table.add_row("")
    _row("🟢 LIVE", str(result.accessible), "green")
    _row("🟡 AUTH", str(result.auth_required), "yellow")
    _row("🌐 WEB", str(result.web_only), "magenta")
    _row("🔴 FAIL", str(result.auth_failed), "red")
    _row("⚫ CLOSED", str(result.closed), "dim")
    _row("⚠️  ERROS", str(result.errors), "red")
    table.add_row("")
    _row("📺 Streams", str(result.live_streams), "magenta")

    # Top vendors
    if result.vendors:
        table.add_row("")
        table.add_row(Text("━━━ FABRICANTES ━━━", style="bold cyan"))
        max_v = max(result.vendors.values()) if result.vendors else 1
        for vendor, count in list(result.vendors.items())[:6]:
            bar_len = int(count / max_v * 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            table.add_row(
                Text(f"  {vendor[:14]}", style="white"),
                Text(f"{bar} {count}", style="cyan"),
            )

    return Panel(table, title="[bold]Stats", border_style="green")


def _make_table(result: ScanResult) -> Panel:
    """Tabela de câmaras (lado direito)."""
    table = Table(
        expand=True,
        show_lines=False,
        header_style="bold cyan",
        title="[bold]📷 Câmaras encontradas",
    )
    table.add_column("Status", style="bold", width=4)
    table.add_column("IP:Porta", style="cyan", no_wrap=True)
    table.add_column("Vendor", style="white")
    table.add_column("País", style="yellow")
    table.add_column("Cidade", style="white")
    table.add_column("Resolução", style="magenta")
    table.add_column("Auth", style="dim")
    table.add_column("Método", style="dim")
    table.add_column("ONVIF", style="blue")

    # Ordenar: LIVE primeiro, depois AUTH, depois outros
    status_order = {
        CameraStatus.LIVE: 0,
        CameraStatus.AUTH_REQUIRED: 1,
        CameraStatus.WEB_ONLY: 2,
        CameraStatus.AUTH_FAILED: 3,
        CameraStatus.CLOSED: 4,
        CameraStatus.PENDING: 5,
        CameraStatus.SCANNING: 6,
        CameraStatus.ERROR: 7,
    }
    cameras = sorted(
        result.cameras,
        key=lambda c: (status_order.get(c.status, 99), c.ip),
    )

    # Limitar a 100 linhas para performance
    for cam in cameras[:100]:
        icon = STATUS_ICONS.get(cam.status, "?")
        color = STATUS_COLORS.get(cam.status, "white")

        auth = "—"
        if cam.auth_user:
            auth = f"{cam.auth_user}:{cam.auth_pass or ''}"[:20]
        elif cam.access_method and cam.access_method.value == "rtsp_no_auth":
            auth = "no-auth"

        table.add_row(
            Text(icon, style=color),
            f"{cam.ip}:{cam.port}",
            (cam.vendor or "?")[:15],
            f"{cam.geo.country or '?'} {cam.country_flag}",
            (cam.geo.city or "?")[:18],
            cam.resolution,
            auth,
            cam.access_method.value if cam.access_method else "—",
            "✓" if cam.onvif_supported else "",
        )

    if len(cameras) > 100:
        table.add_row(
            Text("…", style="dim"),
            f"+{len(cameras) - 100} mais",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )

    return Panel(table, border_style="cyan")


def _make_log(result: ScanResult) -> Panel:
    """Log de eventos (rodapé)."""
    log_text = Text()
    log_text.append(f"  🦾 Scan ID: {result.scan_id}\n", style="cyan")
    log_text.append("  ⏱  Iniciado: ", style="dim")
    import datetime

    if result.started_at:
        log_text.append(
            datetime.datetime.fromtimestamp(result.started_at).strftime("%H:%M:%S"), style="white"
        )
    log_text.append("  |  Terminado: ", style="dim")
    if result.finished_at:
        log_text.append(
            datetime.datetime.fromtimestamp(result.finished_at).strftime("%H:%M:%S"), style="white"
        )
    log_text.append("  |  Duração: ", style="dim")
    if result.finished_at and result.started_at:
        log_text.append(f"{result.finished_at - result.started_at:.1f}s", style="white")
    log_text.append("\n")
    log_text.append(f"  📊 {result.total_ips} IPs  ", style="cyan")
    log_text.append(f"🟢 {result.accessible} live  ", style="green")
    log_text.append(f"🟡 {result.auth_required} auth  ", style="yellow")
    log_text.append(f"🌐 {result.web_only} web  ", style="magenta")
    log_text.append(f"⚫ {result.closed} closed", style="dim")

    return Panel(log_text, title="[bold]Sumário", border_style="green", height=5)


def render_dashboard(result: ScanResult) -> Layout:
    """Renderiza o dashboard TUI completo."""
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="log", size=5),
    )
    layout["body"].split_row(
        Layout(name="stats", size=30),
        Layout(name="table"),
    )
    layout["header"].update(_make_header(result))
    layout["body"]["stats"].update(_make_stats(result))
    layout["body"]["table"].update(_make_table(result))
    layout["log"].update(_make_log(result))
    return layout


def run_tui(result: ScanResult, refresh_per_second: int = 2) -> None:
    """Corre o dashboard TUI.

    Args:
        result: ScanResult com câmaras.
        refresh_per_second: Refresh rate.
    """
    console = Console()
    try:
        with Live(
            render_dashboard(result),
            console=console,
            screen=False,
            auto_refresh=False,
            refresh_per_second=refresh_per_second,
        ) as live:
            try:
                while True:
                    live.update(render_dashboard(result))
                    time.sleep(1.0 / refresh_per_second)
            except KeyboardInterrupt:
                console.print("\n[yellow]Saindo do TUI...[/yellow]")
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Fallback: render estático
        console.print(f"[red]Erro TUI: {e}[/red]")
        console.print(render_dashboard(result))
