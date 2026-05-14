from __future__ import annotations

from pathlib import Path

import pandas as pd
from baet.config.loader import load_settings
from baet.execution.backtest import PortfolioBacktestEngine
from baet.strategies.baselines import BuyAndHoldStrategy


def _market_frame(symbol: str, timeframe: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=24, freq="1h", tz="UTC")
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


def test_backtester_runs_with_order_intent_signals() -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))
    engine = PortfolioBacktestEngine(settings.backtest)
    strategy = BuyAndHoldStrategy()
    market = _market_frame("BTCUSDT", "1h")

    artifacts = engine.run_order_intent(
        market_frames={("BTCUSDT", "1h"): market},
        signals={("BTCUSDT", "1h"): strategy.generate_signals(market)},
        run_name="smoke",
    )

    assert not artifacts.equity_curve.empty
    assert "final_equity" in artifacts.metrics["metric"].tolist()
