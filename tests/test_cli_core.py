from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from baet import cli as cli_module
from baet.backtest import pipeline as backtest_pipeline_module
from baet.data import ingestion as ingestion_module
from click.testing import CliRunner


def _fake_load_config(_config_path: str | None = None) -> SimpleNamespace:
    return SimpleNamespace()


def test_ingest_command_runs_with_data_ingester(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeIngester:
        def __init__(self, settings: Any) -> None:
            self.settings = settings

        def fetch_historical(self, symbol: str, timeframe: str, days: int) -> list[object]:
            return [symbol, timeframe, days]

        def save_raw(self, _frame: Any, symbol: str, timeframe: str) -> Path:
            return Path(f"data/raw/{symbol}/{timeframe}/candles.parquet")

    monkeypatch.setattr(cli_module, "_load_config", _fake_load_config)
    monkeypatch.setattr(ingestion_module, "DataIngester", FakeIngester)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["ingest", "--symbols", "BTCUSDT", "--days", "7"])

    assert result.exit_code == 0
    assert "Ingestion complete" in result.output
    assert "BTCUSDT" in result.output


def test_backtest_command_runs_with_backtest_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePipeline:
        def __init__(self, settings: Any) -> None:
            self.settings = settings

        def run(
            self,
            strategy_name: str,
            start_date: str | None,
            end_date: str | None,
            symbols: Any,
        ) -> dict[str, float]:
            assert strategy_name == "sma_crossover"
            assert start_date is None
            assert end_date is None
            assert symbols is None
            return {
                "total_return": 0.12,
                "sharpe_ratio": 1.5,
                "max_drawdown": -0.08,
                "total_trades": 6,
                "win_rate": 0.5,
            }

    monkeypatch.setattr(cli_module, "_load_config", _fake_load_config)
    monkeypatch.setattr(backtest_pipeline_module, "BacktestPipeline", FakePipeline)

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["backtest", "--strategy", "sma_crossover"])

    assert result.exit_code == 0
    assert "Backtest Results" in result.output
    assert "Total Return: 12.00%" in result.output
    assert "Total Trades: 6" in result.output
