from pathlib import Path

from baet.config.loader import load_settings


def test_stage1_settings_defaults_are_available() -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))

    assert settings.binance.historical_limit == 1000
    assert settings.binance.live_stream_enabled is False
    assert settings.backtest.execution_price == "next_open"
    assert settings.reporting.backtests_dir.as_posix() == "data/results/backtests"
