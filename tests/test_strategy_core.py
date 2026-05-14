from __future__ import annotations

import pandas as pd
from baet.strategies import SIGNAL_COLUMNS, discover_strategies


def _frame() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=30, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "symbol": ["BTCUSDT"] * len(index),
            "timeframe": ["1h"] * len(index),
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


def test_discovered_strategies_emit_canonical_signal_shape() -> None:
    strategies = discover_strategies()
    frame = _frame()

    assert strategies
    strategy = strategies[0]
    signals = strategy.generate_signals(frame)

    assert list(signals.columns) == SIGNAL_COLUMNS
    assert signals["strategy_name"].nunique() == 1
