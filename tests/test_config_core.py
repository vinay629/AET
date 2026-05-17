"""Core tests for BAET configuration loader and models.

All config tests load from `.env.example` (which has no live credential overrides
and `BAET_MODE=dev`), so every assertion below is deterministic and immune to
the developer's personal `.env` settings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
ENV_EXAMPLE = ROOT / ".env.example"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))  # noqa: E402

from baet.config.loader import load_settings  # noqa: E402
from baet.config.models import (  # noqa: E402
    AppConfig,
    BacktestConfig,
    DashboardConfig,
    LiveConfig,
    MarketConfig,
    PaperTradingConfig,
    SecretsConfig,
    Settings,
    StorageConfig,
)
from baet.core.enums import AppMode  # noqa: E402


def _from_example() -> Settings:
    """Load settings using .env.example so the BAET_MODE=dev in that file sticks."""
    return load_settings(env_file=ENV_EXAMPLE)


# ===========================================================================
# Model-default tests
# ===========================================================================


class TestModelDefaults:
    def test_app_name(self) -> None:
        assert AppConfig().name == "baet"

    def test_app_mode_dev(self) -> None:
        assert AppConfig().mode == AppMode.DEV

    def test_market_symbols(self) -> None:
        assert MarketConfig().symbols == ["BTCUSDT", "ETHUSDT"]

    def test_storage_paths(self) -> None:
        s = StorageConfig()
        assert s.raw_data_dir == Path("data/raw")
        assert s.results_dir == Path("data/results")

    def test_paper_initial_balance(self) -> None:
        assert PaperTradingConfig().initial_balance == 10_000.0

    def test_live_enabled_false(self) -> None:
        assert LiveConfig().enabled is False

    def test_live_testnet_true(self) -> None:
        assert LiveConfig().testnet is True

    def test_backtest_fee_rate(self) -> None:
        assert BacktestConfig().fee_rate == pytest.approx(0.001)

    def test_backtest_execution_price(self) -> None:
        assert BacktestConfig().execution_price == "next_open"

    def test_dashboard_port(self) -> None:
        assert DashboardConfig().port == 8501

    def test_secrets_all_empty(self) -> None:
        s = SecretsConfig()
        assert s.binance_api_key.get_secret_value() == ""
        assert s.live_binance_api_key.get_secret_value() == ""

    def test_settings_has_all_sections(self) -> None:
        s = Settings()
        for attr in (
            "app",
            "market",
            "storage",
            "paper",
            "live",
            "binance",
            "risk",
            "features",
            "backtest",
            "reporting",
            "dashboard",
            "notifications",
            "secrets",
        ):
            assert getattr(s, attr) is not None, f"Settings missing section: {attr}"


# ===========================================================================
# AppMode enum
# ===========================================================================


class TestAppModeEnum:
    def test_values(self) -> None:
        assert AppMode.DEV == "dev"
        assert AppMode.PAPER == "paper"
        assert AppMode.LIVE == "live"

    def test_iteration(self) -> None:
        assert {m.value for m in AppMode} == {"dev", "paper", "live"}


# ===========================================================================
# load_settings integration  — use .env.example so assertions are deterministic
# ===========================================================================


class TestLoadSettings:
    def test_returns_settings(self) -> None:
        assert isinstance(_from_example(), Settings)

    def test_mode_is_dev(self) -> None:
        """`.env.example` specifies `BAET_MODE=dev`."""
        assert _from_example().app.mode.value == "dev"

    def test_market_symbols_present(self) -> None:
        assert "BTCUSDT" in _from_example().market.symbols

    def test_paper_initial_balance(self) -> None:
        assert _from_example().paper.initial_balance == 10_000.0

    def test_live_enabled_false(self) -> None:
        """`live.yaml` (not live-mode) should have enabled=false; .env.example has dev mode."""
        assert _from_example().live.enabled is False

    def test_live_testnet_true(self) -> None:
        assert _from_example().live.testnet is True

    def test_binance_url_contains_binance(self) -> None:
        assert "binance" in _from_example().binance.rest_base_url

    def test_backtest_initial_cash(self) -> None:
        assert _from_example().backtest.initial_cash == 10_000.0

    def test_dashboard_port(self) -> None:
        assert _from_example().dashboard.port == 8501

    def test_log_ignored_when_not_set_in_env_example(self) -> None:
        """If .env.example doesn't override BAET_LOG_LEVEL, use INFO from base.yaml."""
        assert _from_example().app.logging_level == "INFO"

    def test_all_sections_loaded(self) -> None:
        s = _from_example()
        for attr in (
            "app",
            "market",
            "storage",
            "paper",
            "live",
            "binance",
            "risk",
            "features",
            "backtest",
            "reporting",
            "dashboard",
            "notifications",
            "secrets",
        ):
            assert hasattr(s, attr)

    def test_paper_mode_via_env_file(self, tmp_path, monkeypatch) -> None:
        """A fully self-contained env file (with BAET_MODE) must result in paper mode."""
        monkeypatch.setenv("BAET_MODE", "paper")
        monkeypatch.setenv("BAET_BINANCE_API_KEY", "test_key")
        monkeypatch.setenv("BAET_BINANCE_API_SECRET", "test_secret")
        env_file = tmp_path / "dev.env"
        env_file.write_text("BAET_MODE=dev\n")
        # With BAET_MODE=paper already in process env, load_settings uses that
        # regardless of the custom .env (override=False for existing env vars).
        # This test verifies that live-mode-specific requirements don't fire in paper.
        s = load_settings()
        assert s.paper.enabled is True

    def test_secrets_default_empty_from_example(self) -> None:
        """`.env.example` has empty API keys → all SecretStr values empty."""
        s = _from_example()
        assert s.secrets.binance_api_key.get_secret_value() == ""
        assert s.secrets.live_binance_api_key.get_secret_value() == ""
