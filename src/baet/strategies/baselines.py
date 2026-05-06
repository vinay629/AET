from __future__ import annotations

import pandas as pd


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
