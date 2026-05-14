from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from baet import cli as cli_module
from baet.data import ingestion as ingestion_module
from click.testing import CliRunner


def _fake_load_config(_config_path: str | None = None) -> SimpleNamespace:
    settings = SimpleNamespace()
    settings.market = SimpleNamespace(symbols=["BTCUSDT"], timeframes=["1h"])
    settings.backtest = SimpleNamespace(
        initial_cash=10000.0,
        fee_rate=0.001,
        slippage_rate=0.0005,
        execution_price="next_open",
        allocation_per_signal=0.5,
    )
    return settings


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


def test_backtest_command_runs_with_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        def fetch_klines(self, symbol: str, timeframe: str, start: Any, end: Any) -> pd.DataFrame:
            index = pd.date_range("2024-01-01", periods=24, freq="1h", tz="UTC")
            return pd.DataFrame(
                {
                    "symbol": [symbol] * 24,
                    "timeframe": [timeframe] * 24,
                    "open_time": index,
                    "close_time": index + pd.Timedelta(minutes=59, seconds=59),
                    "open": [100.0 + i for i in range(24)],
                    "high": [101.0 + i for i in range(24)],
                    "low": [99.0 + i for i in range(24)],
                    "close": [100.5 + i for i in range(24)],
                    "volume": [10.0 + i for i in range(24)],
                    "quote_volume": [1000.0 + i for i in range(24)],
                    "trade_count": [100 + i for i in range(24)],
                    "taker_buy_base_volume": [5.0 + i for i in range(24)],
                    "taker_buy_quote_volume": [500.0 + i for i in range(24)],
                    "source": ["fixture"] * 24,
                }
            )

    class FakeEngine:
        def __init__(self, config: Any) -> None:
            pass

        def run(self, market_frames: Any, signals: Any, run_name: str) -> SimpleNamespace:
            equity_curve = pd.DataFrame({"equity": [10000.0, 10500.0]})
            trades = pd.DataFrame({"side": ["BUY", "SELL"]})
            return SimpleNamespace(
                equity_curve=equity_curve,
                trades=trades,
                symbol_returns=pd.DataFrame(),
                metrics=pd.DataFrame(),
                metadata={},
            )

    class FakeStrategy:
        def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "timestamp": frame["close_time"],
                    "symbol": frame["symbol"],
                    "timeframe": frame["timeframe"],
                    "action": ["BUY"] * len(frame),
                    "target_position": [1.0] * len(frame),
                    "confidence": [1.0] * len(frame),
                    "size_hint": [1.0] * len(frame),
                    "strategy_name": ["buy_and_hold"] * len(frame),
                    "reason": ["always_long"] * len(frame),
                }
            )

    monkeypatch.setattr(cli_module, "_load_config", _fake_load_config)
    monkeypatch.setattr(
        "baet.data.binance.BinanceHistoricalProvider", FakeProvider
    )
    monkeypatch.setattr(
        "baet.execution.backtest.PortfolioBacktestEngine", FakeEngine
    )
    monkeypatch.setattr(
        "baet.strategies.baselines.BuyAndHoldStrategy", lambda: FakeStrategy()
    )

    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["backtest", "--strategy", "sma_crossover"])

    assert result.exit_code == 0
    assert "Backtest Results" in result.output
    assert "Total Trades: 2" in result.output
