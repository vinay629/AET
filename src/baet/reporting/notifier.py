"""Notification module using Apprise for multi-channel alerts.

Inspired by: https://github.com/ccxt/binance-trade-bot

Supports Telegram, Discord, Slack, and 50+ notification services.
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class Notifier:
    """
    Sends notifications to configured channels using Apprise.

    Configuration is done via a list of notification URLs:
    - Telegram: tgram://<bot_token>/<chat_id>
    - Discord: discord://<webhook_id>/<webhook_token>
    - Slack: slack://<token>/<channel>
    - Email: mailto://<user>:<pass>@<domain>
    """

    def __init__(self, urls: Optional[List[str]] = None):
        self.urls = urls or []
        self._apprise = None

        if self.urls:
            try:
                import apprise

                self._apprise = apprise.Apprise()
                for url in self.urls:
                    self._apprise.add(url)
                logger.info(f"Notifier configured with {len(self.urls)} channels")
            except ImportError:
                logger.warning(
                    "Apprise not installed. Notifications disabled. "
                    "Install with: pip install apprise"
                )
            except Exception as e:
                logger.error(f"Failed to configure notifier: {e}")

    def notify(self, title: str, body: str) -> bool:
        """Send a notification to all configured channels."""
        if not self._apprise:
            return False

        try:
            self._apprise.notify(title=title, body=body)
            return True
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def notify_trade(self, trade_info: dict) -> bool:
        """Send a trade notification."""
        title = f"🔄 Trade: {trade_info.get('from_coin', '?')} → {trade_info.get('to_coin', '?')}"
        body = (
            f"Action: {trade_info.get('action', 'N/A')}\n"
            f"Amount: {trade_info.get('amount', 'N/A')}\n"
            f"Price: {trade_info.get('price', 'N/A')}\n"
            f"State: {trade_info.get('state', 'N/A')}"
        )
        return self.notify(title, body)

    def notify_error(self, error: str) -> bool:
        """Send an error notification."""
        return self.notify("❌ BAET Error", error)

    def notify_status(self, status: str) -> bool:
        """Send a status update notification."""
        return self.notify("📊 BAET Status", status)
