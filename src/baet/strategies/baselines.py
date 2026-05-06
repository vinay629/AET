from __future__ import annotations

import pandas as pd

from baet.core.models import StrategyMetadata
from baet.strategies.contracts import SIGNAL_COLUMNS, StrategyContract


def build_buy_and_hold_signals(frame: pd.DataFrame) -> pd.DataFrame:
    signals = frame[["symbol", "timeframe", "close_time"]].copy()
    signals["signal"] = 1
    return signals


def build_sma_crossover_signals(frame: pd.DataFrame, fast: int = 5, slow: int = 20) -> pd.DataFrame:
    signals = frame[["symbol", "timeframe", "close_time"]].copy()
    fast_sma = frame["close"].rolling(fast).mean()
    slow_sma = frame["close"].rolling(slow).mean()
    signals["signal"] = (fast_sma > slow_sma).astype("int64")
    return signals


class BuyAndHoldStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="buy_and_hold",
        category="baseline",
        version="1.0.0",
        description="Always targets a long position for supported bars.",
    )

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        signals = frame[["symbol", "timeframe", "close_time"]].copy()
        signals = signals.rename(columns={"close_time": "timestamp"})
        signals["action"] = "BUY"
        signals["target_position"] = 1.0
        signals["confidence"] = 1.0
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "always_long"
        return signals[SIGNAL_COLUMNS]


class SmaCrossoverStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="sma_crossover",
        category="baseline",
        version="1.0.0",
        description="Simple moving-average crossover baseline strategy.",
    )

    def __init__(self, fast: int = 5, slow: int = 20) -> None:
        self.fast = fast
        self.slow = slow

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        fast_sma = frame["close"].rolling(self.fast).mean()
        slow_sma = frame["close"].rolling(self.slow).mean()
        long_mask = fast_sma > slow_sma

        signals = frame[["symbol", "timeframe", "close_time"]].copy()
        signals = signals.rename(columns={"close_time": "timestamp"})
        signals["action"] = long_mask.map({True: "BUY", False: "HOLD"})
        signals["target_position"] = long_mask.astype("float64")
        signals["confidence"] = (fast_sma - slow_sma).abs().fillna(0.0)
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "fast_above_slow"
        return signals[SIGNAL_COLUMNS]


STRATEGY_CLASSES = [BuyAndHoldStrategy, SmaCrossoverStrategy]
