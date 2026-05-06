from pathlib import Path

import pytest

from baet.config.loader import load_settings
from baet.core.enums import AppMode


def test_dev_mode_loads_defaults() -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))

    assert settings.app.mode == AppMode.DEV
    assert settings.market.symbols == ["BTCUSDT", "ETHUSDT"]
    assert settings.paper.enabled is False
    assert settings.live.enabled is False


def test_paper_mode_enables_paper_profile() -> None:
    settings = load_settings(mode="paper", env_file=Path(".env.example"))

    assert settings.app.mode == AppMode.PAPER
    assert settings.paper.enabled is True
    assert settings.live.enabled is False


def test_live_mode_requires_explicit_enable() -> None:
    with pytest.raises(ValueError, match="live mode requires live.enabled=true"):
        load_settings(mode="live", env_file=Path(".env.example"))
