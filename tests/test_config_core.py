from __future__ import annotations

from pathlib import Path

import pytest
from baet.config.loader import load_settings


def test_dev_mode_loads_without_live_credentials() -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))

    assert settings.app.mode == "dev"
    assert settings.live.enabled is False
    assert settings.market.symbols


def test_live_mode_requires_explicit_enablement() -> None:
    with pytest.raises(ValueError, match="live mode requires live Binance credentials"):
        load_settings(mode="live", env_file=Path(".env.example"))
