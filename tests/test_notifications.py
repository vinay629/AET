"""Tests for the notification system."""

import json
from unittest.mock import patch

import pytest

from baet.config.models import NotificationConfig
from baet.notifications import NotificationMessage, NotificationService


@pytest.fixture
def notification_config():
    """Create a notification config with test values."""
    return NotificationConfig(
        enabled=True,
        telegram_bot_token="test_token_12345",
        telegram_chat_id="123456",
        discord_webhook_url="https://discord.com/api/webhooks/test",
    )


@pytest.fixture
def disabled_config():
    """Create a disabled notification config."""
    return NotificationConfig(enabled=False)


@pytest.fixture
def service(notification_config):
    """Create a notification service."""
    return NotificationService(config=notification_config)


class TestNotificationMessage:
    """Test NotificationMessage formatting."""

    def test_to_telegram_text_info(self):
        msg = NotificationMessage(title="Test", body="Hello", level="info")
        text = msg.to_telegram_text()
        assert "ℹ️" in text
        assert "*Test*" in text
        assert "Hello" in text

    def test_to_telegram_text_critical(self):
        msg = NotificationMessage(title="Alert", body="Critical!", level="critical")
        text = msg.to_telegram_text()
        assert "🚨" in text

    def test_to_telegram_text_with_metadata(self):
        msg = NotificationMessage(
            title="Trade",
            body="BUY BTC",
            metadata={"Symbol": "BTCUSDT", "Price": "$42,000"},
        )
        text = msg.to_telegram_text()
        assert "Symbol: BTCUSDT" in text
        assert "Price: $42,000" in text

    def test_to_discord_embed(self):
        msg = NotificationMessage(title="Test", body="Hello", level="warning")
        embed = msg.to_discord_embed()
        assert "embeds" in embed
        assert len(embed["embeds"]) == 1
        assert embed["embeds"][0]["title"] == "BAET: Test"
        assert embed["embeds"][0]["description"] == "Hello"

    def test_to_discord_embed_color_map(self):
        levels_colors = {
            "info": 0x3498DB,
            "warning": 0xF39C12,
            "error": 0xE74C3C,
            "critical": 0x992D22,
        }
        for level, expected_color in levels_colors.items():
            msg = NotificationMessage(title="T", body="B", level=level)
            embed = msg.to_discord_embed()
            assert embed["embeds"][0]["color"] == expected_color


class TestNotificationService:
    """Test NotificationService functionality."""

    def test_is_configured_with_telegram(self):
        config = NotificationConfig(
            enabled=True,
            telegram_bot_token="token",
            telegram_chat_id="123",
        )
        service = NotificationService(config=config)
        assert service.is_configured is True

    def test_is_configured_with_discord(self):
        config = NotificationConfig(
            enabled=True,
            discord_webhook_url="https://discord.com/api/webhooks/test",
        )
        service = NotificationService(config=config)
        assert service.is_configured is True

    def test_is_not_configured_when_disabled(self):
        config = NotificationConfig(enabled=False)
        service = NotificationService(config=config)
        assert service.is_configured is False

    def test_is_not_configured_without_credentials(self):
        config = NotificationConfig(enabled=True)
        service = NotificationService(config=config)
        assert service.is_configured is False

    def test_send_returns_false_when_disabled(self, disabled_config):
        service = NotificationService(config=disabled_config)
        msg = NotificationMessage(title="Test", body="Hello")
        assert service.send(msg) is False

    @patch("baet.notifications.urlopen")
    def test_send_telegram_success(self, mock_urlopen, service):
        mock_resp = type("Response", (), {"status": 200})()
        mock_urlopen.return_value.__enter__ = lambda s: mock_resp
        mock_urlopen.return_value.__exit__ = lambda s, *args: None

        msg = NotificationMessage(title="Test", body="Hello")
        result = service.send(msg)
        assert result is True

    @patch("baet.notifications.urlopen")
    def test_send_discord_success(self, mock_urlopen, service):
        mock_resp = type("Response", (), {"status": 204})()
        mock_urlopen.return_value.__enter__ = lambda s: mock_resp
        mock_urlopen.return_value.__exit__ = lambda s, *args: None

        msg = NotificationMessage(title="Test", body="Hello")
        result = service.send(msg)
        assert result is True

    @patch("baet.notifications.urlopen")
    def test_send_handles_telegram_failure(self, mock_urlopen, service):
        # First call (telegram) fails, second (discord) succeeds
        from unittest.mock import MagicMock

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Telegram down")
            mock_resp = MagicMock()
            mock_resp.status = 204
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        mock_urlopen.side_effect = side_effect

        msg = NotificationMessage(title="Test", body="Hello")
        result = service.send(msg)
        assert result is True  # Discord succeeded

    def test_notify_trade(self, service):
        with patch.object(service, "send", return_value=True) as mock_send:
            result = service.notify_trade("BTCUSDT", "BUY", 0.1, 42000.0, pnl=50.0)
            assert result is True
            mock_send.assert_called_once()
            msg = mock_send.call_args[0][0]
            assert msg.title == "Trade: BUY BTCUSDT"
            assert "$+50.00" in msg.body

    def test_notify_risk_breach(self, service):
        with patch.object(service, "send", return_value=True) as mock_send:
            result = service.notify_risk_breach("daily_loss", -11.0, 10.0, "BLOCKED")
            assert result is True
            msg = mock_send.call_args[0][0]
            assert "Risk Breach" in msg.title
            assert msg.level == "warning"

    def test_notify_emergency_stop(self, service):
        with patch.object(service, "send", return_value=True) as mock_send:
            result = service.notify_emergency_stop("Daily loss limit reached")
            assert result is True
            msg = mock_send.call_args[0][0]
            assert "EMERGENCY STOP" in msg.title
            assert msg.level == "critical"

    def test_notify_daily_summary_positive(self, service):
        with patch.object(service, "send", return_value=True) as mock_send:
            result = service.notify_daily_summary(5, 3, 15.5, 1015.5)
            assert result is True
            msg = mock_send.call_args[0][0]
            assert "📈" in msg.title
            assert msg.level == "info"

    def test_notify_daily_summary_negative(self, service):
        with patch.object(service, "send", return_value=True) as mock_send:
            result = service.notify_daily_summary(5, 1, -8.0, 992.0)
            assert result is True
            msg = mock_send.call_args[0][0]
            assert "📉" in msg.title
            assert msg.level == "warning"

    def test_notify_error(self, service):
        with patch.object(service, "send", return_value=True) as mock_send:
            result = service.notify_error("ConnectionError", "API timeout", "binance_client")
            assert result is True
            msg = mock_send.call_args[0][0]
            assert "Error" in msg.title
            assert msg.level == "error"

    def test_respects_notify_flags(self):
        config = NotificationConfig(
            enabled=True,
            telegram_bot_token="token",
            telegram_chat_id="123",
            notify_on_trade=False,
            notify_on_risk_breach=False,
            notify_on_emergency_stop=False,
            notify_on_daily_summary=False,
            notify_on_error=False,
        )
        service = NotificationService(config=config)

        assert service.notify_trade("BTC", "BUY", 0.1, 42000) is False
        assert service.notify_risk_breach("test", -1, 1, "stop") is False
        assert service.notify_emergency_stop("test") is False
        assert service.notify_daily_summary(0, 0, 0, 0) is False
        assert service.notify_error("err", "msg") is False
