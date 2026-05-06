from __future__ import annotations

import pandas as pd

from baet.strategies.contracts import SIGNAL_COLUMNS


def normalize_order_intent_signals(frame: pd.DataFrame) -> pd.DataFrame:
    missing_columns = set(SIGNAL_COLUMNS) - set(frame.columns)
    if missing_columns:
        raise ValueError(f"Missing signal columns: {sorted(missing_columns)}")
    normalized = frame[SIGNAL_COLUMNS].copy()
    normalized["target_position"] = normalized["target_position"].astype("float64")
    normalized["confidence"] = normalized["confidence"].astype("float64")
    normalized["size_hint"] = normalized["size_hint"].astype("float64")
    return normalized


def adapt_order_intent_to_backtest_signals(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_order_intent_signals(frame)
    adapted = normalized.rename(columns={"timestamp": "close_time"})
    adapted["signal"] = (adapted["target_position"] > 0.0).astype("int64")
    return adapted[["symbol", "timeframe", "close_time", "signal"]]
