"""
Sistema de alertas do Procurador de Câmara.

Suporta:
- Telegram Bot API
- Discord Webhook
- Log file

Usa a base de dados para não duplicar alertas.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)


# =====================================================================
# Alertas
# =====================================================================

@dataclass
class Alert:
    """Estrutura de um alerta."""
    camera_ip: str
    scan_id: str
    alert_type: str  # 'new_camera', 'status_change', 'new_live', 'error'
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AlertManager:
    """Gerir envio de alertas via múltiplos canais."""

    def __init__(
        self,
        telegram_token: str | None = None,
        telegram_chat_id: str | None = None,
        discord_webhook: str | None = None,
    ):
        self.telegram_token = (
            telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN") or ""
        )
        self.telegram_chat_id = (
            telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID") or ""
        )
        self.discord_webhook = (
            discord_webhook or os.environ.get("DISCORD_WEBHOOK") or ""
        )

    @property
    def is_configured(self) -> bool:
        """Há pelo menos um canal configurado."""
        return bool(self.telegram_token and self.telegram_chat_id) or bool(self.discord_webhook)

    # ── Telegram ──────────────────────────────────────────────────

    def send_telegram(self, message: str) -> bool:
        """Enviar mensagem via Telegram Bot API."""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.debug("Telegram não configurado")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        try:
            r = requests.post(
                url,
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            if r.status_code == 200:
                logger.debug("Telegram: mensagem enviada")
                return True
            else:
                logger.warning(f"Telegram: erro {r.status_code} — {r.text[:100]}")
                return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Telegram: erro de rede — {e}")
            return False

    # ── Discord ───────────────────────────────────────────────────

    def send_discord(self, message: str) -> bool:
        """Enviar mensagem via Discord Webhook."""
        if not self.discord_webhook:
            logger.debug("Discord não configurado")
            return False

        try:
            r = requests.post(
                self.discord_webhook,
                json={
                    "content": message,
                    "username": "Procurador de Câmara",
                },
                timeout=10,
            )
            if r.status_code in (200, 204):
                logger.debug("Discord: mensagem enviada")
                return True
            else:
                logger.warning(f"Discord: erro {r.status_code} — {r.text[:100]}")
                return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Discord: erro de rede — {e}")
            return False

    # ── Enviar alerta ─────────────────────────────────────────────

    def send(self, alert: Alert) -> bool:
        """Enviar alerta para todos os canais configurados."""
        message = self._format_alert(alert)
        sent = False

        if self.send_telegram(message):
            sent = True
        if self.send_discord(message):
            sent = True

        # Log sempre
        logger.info(f"🔔 Alerta [{alert.alert_type}]: {alert.message}")

        return sent

    def send_batch(self, alerts: list[Alert]) -> int:
        """Enviar lote de alertas. Devolve quantos foram enviados."""
        sent = 0
        for alert in alerts:
            if self.send(alert):
                sent += 1
        return sent

    @staticmethod
    def _format_alert(alert: Alert) -> str:
        """Formatar alerta para texto."""
        icons = {
            "new_camera": "📷",
            "new_live": "🟢",
            "status_change": "🔄",
            "error": "❌",
        }
        icon = icons.get(alert.alert_type, "🔔")

        lines = [
            f"{icon} <b>Procurador de Câmara</b>",
            f"<b>Tipo:</b> {alert.alert_type}",
            f"<b>IP:</b> <code>{alert.camera_ip}</code>",
            f"<b>Mensagem:</b> {alert.message}",
        ]

        meta = alert.metadata
        if meta.get("vendor"):
            lines.append(f"<b>Fabricante:</b> {meta['vendor']}")
        if meta.get("country"):
            lines.append(f"<b>País:</b> {meta['country']}")
        if meta.get("rtsp_url"):
            lines.append(f"<b>Stream:</b> <code>{meta['rtsp_url'][:80]}</code>")

        return "\n".join(lines)
