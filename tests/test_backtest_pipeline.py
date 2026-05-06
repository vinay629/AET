from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from baet.config.loader import load_settings
from baet.data.interfaces import HistoricalDataProvider
from baet.data.pipeline import ResearchPipeline
from baet.data.storage import ParquetMarketDataStore
from baet.execution.backtest import PortfolioBacktestEngine
from baet.strategies import BuyAndHoldStrategy, adapt_order_intent_to_backtest_signals
from baet.strategies.baselines import build_buy_and_hold_signals


def _market_frame(symbol: str, timeframe: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=24, freq=timeframe, tz="UTC")
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(index),
            "timeframe": [timeframe] * len(index),
            "open_time": index,
            "close_time": index + pd.Timedelta(minutes=59, seconds=59),
            "open": [100.0 + i for i in range(len(index))],
            "high": [101.0 + i for i in range(len(index))],
            "low": [99.0 + i for i in range(len(index))],
            "close": [100.5 + i for i in range(len(index))],
            "volume": [10.0 + i for i in range(len(index))],
            "quote_volume": [1000.0 + i for i in range(len(index))],
            "trade_count": [100 + i for i in range(len(index))],
            "taker_buy_base_volume": [5.0 + i for i in range(len(index))],
            "taker_buy_quote_volume": [500.0 + i for i in range(len(index))],
            "source": ["fixture"] * len(index),
        }
    )


class FixtureHistoricalProvider(HistoricalDataProvider):
    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        return _market_frame(symbol, timeframe)


def test_backtester_outputs_expected_artifacts() -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))
    engine = PortfolioBacktestEngine(settings.backtest)
    btc = _market_frame("BTCUSDT", "1h")
    eth = _market_frame("ETHUSDT", "1h")

    artifacts = engine.run(
        market_frames={("BTCUSDT", "1h"): btc, ("ETHUSDT", "1h"): eth},
        signals={
            ("BTCUSDT", "1h"): build_buy_and_hold_signals(btc),
            ("ETHUSDT", "1h"): build_buy_and_hold_signals(eth),
        },
        run_name="baseline",
    )

    assert not artifacts.equity_curve.empty
    assert not artifacts.metrics.empty
    assert "final_equity" in artifacts.metrics["metric"].tolist()


def test_order_intent_adapter_preserves_stage1_backtest_path() -> None:
    market = _market_frame("BTCUSDT", "1h")
    strategy = BuyAndHoldStrategy()
    order_intent = strategy.generate_signals(market)
    adapted = adapt_order_intent_to_backtest_signals(order_intent)

    assert adapted["signal"].eq(1).all()
    assert list(adapted.columns) == ["symbol", "timeframe", "close_time", "signal"]


def test_fee_and_slippage_reduce_results() -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))
    market = _market_frame("BTCUSDT", "1h")
    signal = build_buy_and_hold_signals(market)

    baseline_engine = PortfolioBacktestEngine(settings.backtest)
    baseline = baseline_engine.run(
        market_frames={("BTCUSDT", "1h"): market},
        signals={("BTCUSDT", "1h"): signal},
        run_name="baseline",
    )

    settings.backtest.fee_rate = 0.01
    settings.backtest.slippage_rate = 0.01
    costly_engine = PortfolioBacktestEngine(settings.backtest)
    costly = costly_engine.run(
        market_frames={("BTCUSDT", "1h"): market},
        signals={("BTCUSDT", "1h"): signal},
        run_name="costly",
    )

    baseline_equity = float(
        baseline.metrics.loc[
            baseline.metrics["metric"] == "final_equity",
            "value",
        ].iloc[0]
    )
    costly_equity = float(
        costly.metrics.loc[
            costly.metrics["metric"] == "final_equity",
            "value",
        ].iloc[0]
    )
    assert costly_equity < baseline_equity


def test_end_to_end_pipeline(tmp_path: Path) -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))
    settings.storage.raw_data_dir = tmp_path / "raw"
    settings.storage.processed_data_dir = tmp_path / "processed"
    settings.reporting.backtests_dir = tmp_path / "results" / "backtests"
    settings.market.timeframes = ["1h", "4h"]

    pipeline = ResearchPipeline(
        settings,
        FixtureHistoricalProvider(),
        ParquetMarketDataStore(settings),
    )
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 2, tzinfo=timezone.utc)

    for symbol in settings.market.symbols:
        for timeframe in settings.market.timeframes:
            ingestion_summary = pipeline.ingest_symbol_timeframe(symbol, timeframe, start, end)
            feature_summary = pipeline.build_features(symbol, timeframe)
            ingestion = ingestion_summary["ingestion"]
            assert isinstance(ingestion, dict)
            assert int(ingestion["rows"]) > 0
            feature_count = feature_summary["feature_count"]
            assert isinstance(feature_count, int)
            assert feature_count > 0

    artifacts, summary = pipeline.run_baseline_backtest(run_name="stage1-e2e")
    assert not artifacts.equity_curve.empty
    assert "final_equity" in summary
