"""Tests for hardened configuration system."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from baet.config.hardened import (
    ConfigSnapshot,
    ConfigValidationError,
    ConfigValidator,
    load_hardened_config,
)
from baet.config.models import Settings, AppMode


class TestConfigValidator:
    def test_dev_validation(self) -> None:
        config = Settings(app={"mode": AppMode.DEV, "name": "baet", "logging_level": "INFO"})
        warnings = ConfigValidator.validate_dev(config)
        assert isinstance(warnings, list)

    def test_dev_warns_on_live_enabled(self) -> None:
        config = Settings(
            app={"mode": AppMode.DEV, "name": "baet", "logging_level": "INFO"},
            live={"enabled": True, "simulation_mode": True, "testnet": True, "require_explicit_confirmation": True, "safety": {}, "order_submission": {}, "account_touchpoints": []},
        )
        warnings = ConfigValidator.validate_dev(config)
        assert len(warnings) > 0

    def test_paper_validation_passes(self) -> None:
        config = Settings(
            app={"mode": AppMode.PAPER, "name": "baet", "logging_level": "INFO"},
            paper={"enabled": True, "initial_balance": 10000},
            live={"enabled": False, "simulation_mode": True, "testnet": True, "require_explicit_confirmation": True, "safety": {}, "order_submission": {}, "account_touchpoints": []},
        )
        errors = ConfigValidator.validate_paper(config)
        assert len(errors) == 0

    def test_paper_rejects_disabled(self) -> None:
        config = Settings(
            app={"mode": AppMode.PAPER, "name": "baet", "logging_level": "INFO"},
            paper={"enabled": False},
            live={"enabled": False, "simulation_mode": True, "testnet": True, "require_explicit_confirmation": True, "safety": {}, "order_submission": {}, "account_touchpoints": []},
        )
        errors = ConfigValidator.validate_paper(config)
        assert len(errors) > 0

    def test_live_rejects_simulation_mode(self) -> None:
        from baet.config.models import LiveConfig, AppConfig, SecretsConfig
        from pydantic import SecretStr
        config = Settings(
            app=AppConfig(mode=AppMode.LIVE),
            live=LiveConfig(
                enabled=True, simulation_mode=True, testnet=False,
                require_explicit_confirmation=False,
                safety={"max_daily_trades": 5, "max_position_value": 100},
                order_submission={"enabled": True},
                account_touchpoints=[],
            ),
            secrets=SecretsConfig(
                live_binance_api_key=SecretStr("test_key"),
                live_binance_api_secret=SecretStr("test_secret"),
            ),
        )
        errors = ConfigValidator.validate_live(config)
        assert any("simulation_mode" in e for e in errors)

    def test_live_rejects_testnet(self) -> None:
        from baet.config.models import LiveConfig, AppConfig, SecretsConfig
        from pydantic import SecretStr
        config = Settings(
            app=AppConfig(mode=AppMode.LIVE),
            live=LiveConfig(
                enabled=True, simulation_mode=False, testnet=True,
                require_explicit_confirmation=False,
                safety={"max_daily_trades": 5, "max_position_value": 100},
                order_submission={"enabled": True},
                account_touchpoints=[],
            ),
            secrets=SecretsConfig(
                live_binance_api_key=SecretStr("test_key"),
                live_binance_api_secret=SecretStr("test_secret"),
            ),
        )
        errors = ConfigValidator.validate_live(config)
        assert any("testnet" in e for e in errors)

    def test_live_validator_checks_safety_limits(self) -> None:
        """Live validator should check safety limits are positive."""
        from baet.config.models import LiveConfig, AppConfig, SecretsConfig
        from pydantic import SecretStr
        config = Settings(
            app=AppConfig(mode=AppMode.LIVE),
            live=LiveConfig(
                enabled=True, simulation_mode=False, testnet=False,
                require_explicit_confirmation=False,
                safety={"max_daily_trades": 0, "max_position_value": 0},
                order_submission={"enabled": True},
                account_touchpoints=[],
            ),
            secrets=SecretsConfig(
                live_binance_api_key=SecretStr("test_key"),
                live_binance_api_secret=SecretStr("test_secret"),
            ),
        )
        errors = ConfigValidator.validate_live(config)
        assert any("max_daily_trades" in e for e in errors)
        assert any("max_position_value" in e for e in errors)


class TestConfigSnapshot:
    def test_is_frozen(self) -> None:
        config = Settings()
        snapshot = ConfigSnapshot(
            settings=config,
            raw_config={},
            content_hash="abc123",
            mode="dev",
            env="test",
            config_dir=Path("."),
            loaded_at="2026-01-01",
        )
        with pytest.raises(AttributeError):
            snapshot.mode = "live"  # type: ignore

    def test_to_safe_dict_redacts_secrets(self) -> None:
        config = Settings()
        snapshot = ConfigSnapshot(
            settings=config,
            raw_config={},
            content_hash="abc123def456",
            mode="dev",
            env="test",
            config_dir=Path("."),
            loaded_at="2026-01-01",
        )
        safe = snapshot.to_safe_dict()
        assert "secrets" not in safe
        assert safe["mode"] == "dev"
        assert safe["content_hash"] == "abc123def456"[:12]


class TestLoadHardenedConfig:
    def test_load_dev_config(self) -> None:
        snapshot = load_hardened_config(mode="dev", strict=False)
        assert snapshot.mode == "dev"
        assert snapshot.content_hash is not None

    def test_load_paper_config(self) -> None:
        snapshot = load_hardened_config(mode="paper", strict=False)
        assert snapshot.mode == "paper"

    def test_load_live_config_strict_fails(self) -> None:
        with pytest.raises(ConfigValidationError):
            load_hardened_config(mode="live", strict=True)

    def test_load_live_config_non_strict(self) -> None:
        # Should not raise, but will have errors
        snapshot = load_hardened_config(mode="live", strict=False)
        assert snapshot.mode == "live"
