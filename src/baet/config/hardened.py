"""Hardened configuration system for BAET.

Improvements over the basic loader:
- Immutable runtime config snapshot (frozen after load)
- Strict validation per environment (no silent defaults in live)
- Environment separation (dev/paper/live)
- Startup validation with clear error messages
- Config hash for change detection

Usage:
    config = load_hardened_config(mode="paper")
    # config is immutable — any mutation attempt raises TypeError
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from baet.config.loader import _deep_merge, _read_yaml, CONFIG_DIR
from baet.config.models import Settings, AppMode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfigSnapshot:
    """
    Immutable runtime configuration snapshot.

    Once created at startup, this cannot be modified.
    Any attempt to mutate raises TypeError.

    Contains:
    - The validated Settings object
    - The raw merged config dict (for debugging)
    - A content hash (for change detection)
    - The mode and environment info
    """
    settings: Settings
    raw_config: dict[str, Any]
    content_hash: str
    mode: str
    env: str
    config_dir: Path
    loaded_at: str

    def to_safe_dict(self) -> dict[str, Any]:
        """
        Return config as dict with secrets redacted.
        Safe for logging and dashboard display.
        """
        return {
            "mode": self.mode,
            "env": self.env,
            "content_hash": self.content_hash[:12],
            "loaded_at": self.loaded_at,
            "app": {
                "name": self.settings.app.name,
                "mode": self.settings.app.mode.value,
                "logging_level": self.settings.app.logging_level,
            },
            "market": {
                "symbols": self.settings.market.symbols,
                "timeframes": self.settings.market.timeframes,
            },
            "paper": {
                "enabled": self.settings.paper.enabled,
                "initial_balance": self.settings.paper.initial_balance,
            },
            "live": {
                "enabled": self.settings.live.enabled,
                "simulation_mode": self.settings.live.simulation_mode,
                "testnet": self.settings.live.testnet,
            },
            "risk": {
                "max_risk_per_trade": self.settings.risk.max_risk_per_trade,
                "max_portfolio_exposure": self.settings.risk.max_portfolio_exposure,
            },
            "dashboard": {
                "enabled": self.settings.dashboard.enabled,
                "port": self.settings.dashboard.port,
            },
        }


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigValidator:
    """Validates configuration for a specific environment."""

    @staticmethod
    def validate_dev(config: Settings) -> list[str]:
        """Validate dev config — minimal checks."""
        warnings = []
        if config.live.enabled:
            warnings.append("live.enabled=true in dev mode — will use testnet")
        return warnings

    @staticmethod
    def validate_paper(config: Settings) -> list[str]:
        """Validate paper trading config."""
        errors = []
        if not config.paper.enabled:
            errors.append("paper.enabled must be true for paper mode")
        if config.paper.initial_balance <= 0:
            errors.append("paper.initial_balance must be positive")
        if config.live.enabled:
            errors.append("live.enabled must be false in paper mode")
        return errors

    @staticmethod
    def validate_live(config: Settings) -> list[str]:
        """Validate live trading config — strict checks, no silent defaults."""
        errors = []

        # Must explicitly enable live
        if not config.live.enabled:
            errors.append("live.enabled must be true for live mode")

        # Must NOT be in simulation mode
        if config.live.simulation_mode:
            errors.append(
                "live.simulation_mode must be false for live trading. "
                "Use paper mode for simulation."
            )

        # Must have testnet=false for real trading
        if config.live.testnet:
            errors.append(
                "live.testnet must be false for live trading. "
                "Use testnet mode only for testing."
            )

        # Must have API credentials
        live_key = config.secrets.live_binance_api_key.get_secret_value()
        live_secret = config.secrets.live_binance_api_secret.get_secret_value()
        if not live_key or live_key == "":
            errors.append(
                "BAET_LIVE_BINANCE_API_KEY must be set for live trading. "
                "Do NOT use the paper/testnet key."
            )
        if not live_secret or live_secret == "":
            errors.append(
                "BAET_LIVE_BINANCE_API_SECRET must be set for live trading."
            )

        # Must have explicit confirmation disabled (we're explicitly starting live)
        if config.live.require_explicit_confirmation:
            errors.append(
                "live.require_explicit_confirmation must be false when starting live. "
                "This is a safety check — set it to false only when you intend to trade."
            )

        # Safety limits must be set
        safety = config.live.safety
        if safety.get("max_daily_trades", 0) <= 0:
            errors.append("live.safety.max_daily_trades must be positive")
        if safety.get("max_position_value", 0) <= 0:
            errors.append("live.safety.max_position_value must be positive")

        # Risk limits
        if config.risk.max_risk_per_trade <= 0:
            errors.append("risk.max_risk_per_trade must be positive")
        if config.risk.max_portfolio_exposure <= 0:
            errors.append("risk.max_portfolio_exposure must be positive")

        return errors


def load_hardened_config(
    mode: str | None = None,
    env_file: Path | None = None,
    strict: bool = True,
) -> ConfigSnapshot:
    """
    Load and validate configuration with hardening.

    Args:
        mode: Configuration mode (dev/paper/live). Defaults to BAET_MODE env var.
        env_file: Path to .env file. Defaults to .env in project root.
        strict: If True, raise on validation errors. If False, log warnings.

    Returns:
        Immutable ConfigSnapshot.

    Raises:
        ConfigValidationError: If validation fails in strict mode.
    """
    from datetime import datetime, timezone

    # Determine mode
    selected_mode = mode or os.getenv("BAET_MODE", "dev")
    env = os.getenv("ENV", selected_mode)

    logger.info(f"Loading hardened config: mode={selected_mode}, env={env}")

    # Load YAML configs
    base_config = _read_yaml(CONFIG_DIR / "base.yaml")
    mode_config = _read_yaml(CONFIG_DIR / f"{selected_mode}.yaml")
    merged = _deep_merge(base_config, mode_config)

    # Override mode from config
    if "app" not in merged:
        merged["app"] = {}
    merged["app"]["mode"] = selected_mode

    # Build Settings (this runs Pydantic validation)
    from baet.config.loader import _load_secret_settings
    secrets = _load_secret_settings()

    # Create a temporary Settings for validation
    try:
        settings = Settings(**merged, secrets=secrets)
    except Exception as e:
        raise ConfigValidationError(f"Config validation failed: {e}") from e

    # Mode-specific validation
    validator = ConfigValidator()
    mode_validators = {
        "dev": validator.validate_dev,
        "paper": validator.validate_paper,
        "live": validator.validate_live,
    }

    errors = []
    if selected_mode in mode_validators:
        errors = mode_validators[selected_mode](settings)

    if errors:
        error_msg = f"Config validation failed for mode '{selected_mode}':\n" + \
                    "\n".join(f"  ❌ {e}" for e in errors)
        if strict:
            raise ConfigValidationError(error_msg)
        else:
            for e in errors:
                logger.warning(f"Config warning: {e}")

    # Compute content hash
    config_json = json.dumps(merged, sort_keys=True, default=str)
    content_hash = hashlib.sha256(config_json.encode()).hexdigest()

    # Create immutable snapshot
    snapshot = ConfigSnapshot(
        settings=settings,
        raw_config=merged,
        content_hash=content_hash,
        mode=selected_mode,
        env=env,
        config_dir=CONFIG_DIR,
        loaded_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(
        f"Config loaded: mode={selected_mode}, hash={content_hash[:12]}, "
        f"errors={len(errors)}"
    )

    return snapshot
