"""Notification system for BAET.

Supports Telegram and Discord notifications for trading events,
risk breaches, emergency stops, and daily summaries.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from baet.config.models import NotificationConfig

logger = logging.getLogger(__name__)


@dataclass
class NotificationMessage:
    """A notification message to be sent."""

    title: str
    body: str
    level: str = "info"  # info, warning, error, critical
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_telegram_text(self) -> str:
        """Format as Telegram message text."""
        emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
        prefix = emoji.get(self.level, "ℹ️")
        text = f"{prefix} *{self.title}*\n\n{self.body}"
        if self.metadata:
            text += "\n\n📊 Details:\n"
            for key, value in self.metadata.items():
                text += f"  • {key}: {value}\n"
        return text

    def to_discord_embed(self) -> dict:
        """Format as Discord embed payload."""
        color_map = {
            "info": 0x3498DB,  # Blue
            "warning": 0xF39C12,  # Orange
            "error": 0xE74C3C,  # Red
            "critical": 0x992D22,  # Dark red
        }
        return {
            "embeds": [
                {
                    "title": f"BAET: {self.title}",
                    "description": self.body,
                    "color": color_map.get(self.level, 0x3498DB),
                    "timestamp": self.timestamp,
                    "fields": [
                        {"name": k, "value": str(v), "inline": True}
                        for k, v in self.metadata.items()
                    ],
                }
            ]
        }


class NotificationService:
    """Sends notifications via Telegram and/or Discord."""

    def __init__(self, config: NotificationConfig | None = None):
        self.config = config or NotificationConfig()
        self._last_error: str | None = None

    @property
    def is_configured(self) -> bool:
        """Check if any notification channel is configured."""
        has_telegram = (
            self.config.telegram_bot_token.get_secret_value() != ""
            and self.config.telegram_chat_id != ""
        )
        has_discord = self.config.discord_webhook_url != ""
        return self.config.enabled and (has_telegram or has_discord)

    def send(self, message: NotificationMessage) -> bool:
        """Send a notification via all configured channels.

        Args:
            message: The notification message to send.

        Returns:
            True if at least one channel succeeded.
        """
        if not self.config.enabled:
            return False

        success = False

        # Telegram
        if self.config.telegram_bot_token.get_secret_value() and self.config.telegram_chat_id:
            try:
                self._send_telegram(message)
                success = True
            except Exception as e:
                logger.warning(f"Telegram notification failed: {e}")
                self._last_error = str(e)

        # Discord
        if self.config.discord_webhook_url:
            try:
                self._send_discord(message)
                success = True
            except Exception as e:
                logger.warning(f"Discord notification failed: {e}")
                self._last_error = str(e)

        return success

    def _send_telegram(self, message: NotificationMessage) -> None:
        """Send notification via Telegram Bot API."""
        token = self.config.telegram_bot_token.get_secret_value()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": message.to_telegram_text(),
            "parse_mode": "Markdown",
        }
        self._post_json(url, payload)

    def _send_discord(self, message: NotificationMessage) -> None:
        """Send notification via Discord webhook."""
        payload = message.to_discord_embed()
        self._post_json(self.config.discord_webhook_url, payload)

    def _post_json(self, url: str, payload: dict) -> None:
        """POST JSON data to a URL."""
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=10) as resp:
                if resp.status not in (200, 204):
                    raise URLError(f"HTTP {resp.status}")
        except Exception as e:
            raise URLError(f"Request to {url} failed: {e}") from e

    # Convenience methods for common events

    def notify_trade(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        pnl: float | None = None,
    ) -> bool:
        """Send trade notification."""
        if not self.config.notify_on_trade:
            return False
        pnl_text = f"\nP&L: ${pnl:+.2f}" if pnl is not None else ""
        msg = NotificationMessage(
            title=f"Trade: {action} {symbol}",
            body=f"Executed {action} {quantity} {symbol} @ ${price:,.2f}{pnl_text}",
            level="info",
            metadata={
                "Symbol": symbol,
                "Action": action,
                "Quantity": quantity,
                "Price": f"${price:,.2f}",
                **({"P&L": f"${pnl:+.2f}"} if pnl is not None else {}),
            },
        )
        return self.send(msg)

    def notify_risk_breach(
        self,
        limit_type: str,
        current_value: float,
        limit_value: float,
        action_taken: str,
    ) -> bool:
        """Send risk limit breach notification."""
        if not self.config.notify_on_risk_breach:
            return False
        msg = NotificationMessage(
            title=f"Risk Breach: {limit_type}",
            body=(
                f"⚠️ Risk limit breached!\n"
                f"Current: ${current_value:.2f} | Limit: ${limit_value:.2f}\n"
                f"Action: {action_taken}"
            ),
            level="warning",
            metadata={
                "Limit Type": limit_type,
                "Current Value": f"${current_value:.2f}",
                "Limit Value": f"${limit_value:.2f}",
                "Action Taken": action_taken,
            },
        )
        return self.send(msg)

    def notify_emergency_stop(self, reason: str) -> bool:
        """Send emergency stop notification."""
        if not self.config.notify_on_emergency_stop:
            return False
        msg = NotificationMessage(
            title="🚨 EMERGENCY STOP",
            body=f"Trading has been halted!\nReason: {reason}",
            level="critical",
            metadata={"Reason": reason},
        )
        return self.send(msg)

    def notify_daily_summary(
        self,
        total_trades: int,
        winning_trades: int,
        daily_pnl: float,
        portfolio_value: float,
    ) -> bool:
        """Send daily summary notification."""
        if not self.config.notify_on_daily_summary:
            return False
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        emoji = "📈" if daily_pnl >= 0 else "📉"
        msg = NotificationMessage(
            title=f"{emoji} Daily Summary",
            body=(
                f"Trades: {total_trades} | Win Rate: {win_rate:.1f}%\n"
                f"P&L: ${daily_pnl:+.2f} | Portfolio: ${portfolio_value:,.2f}"
            ),
            level="info" if daily_pnl >= 0 else "warning",
            metadata={
                "Total Trades": total_trades,
                "Winning Trades": winning_trades,
                "Win Rate": f"{win_rate:.1f}%",
                "Daily P&L": f"${daily_pnl:+.2f}",
                "Portfolio Value": f"${portfolio_value:,.2f}",
            },
        )
        return self.send(msg)

    def notify_error(self, error_type: str, message: str, component: str = "") -> bool:
        """Send error notification."""
        if not self.config.notify_on_error:
            return False
        msg = NotificationMessage(
            title=f"Error: {error_type}",
            body=f"{message}\nComponent: {component}" if component else message,
            level="error",
            metadata={
                "Error Type": error_type,
                "Component": component,
            },
        )
        return self.send(msg)
