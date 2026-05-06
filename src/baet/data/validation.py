from __future__ import annotations

import pandas as pd

from baet.data.schemas import CANONICAL_CANDLE_COLUMNS


def validate_candles(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    missing_columns = set(CANONICAL_CANDLE_COLUMNS) - set(frame.columns)
    if missing_columns:
        raise ValueError(f"Missing candle columns: {sorted(missing_columns)}")

    if frame.empty:
        return frame.copy()

    validated = frame.copy().sort_values("open_time").reset_index(drop=True)
    if validated["open_time"].duplicated().any():
        raise ValueError("Duplicate open_time values found")
    if not validated["open_time"].is_monotonic_increasing:
        raise ValueError("open_time must be monotonically increasing")
    if (validated["close_time"] <= validated["open_time"]).any():
        raise ValueError("close_time must be greater than open_time")

    expected_delta = pd.Timedelta(timeframe)
    deltas = validated["open_time"].diff().dropna()
    if not deltas.empty and (deltas < expected_delta).any():
        raise ValueError("Detected overlapping or undersized candle intervals")

    return validated


def summarize_data_quality(frame: pd.DataFrame, timeframe: str) -> dict[str, object]:
    if frame.empty:
        return {
            "row_count": 0,
            "duplicate_rows": 0,
            "missing_intervals": 0,
            "start": None,
            "end": None,
        }

    expected_delta = pd.Timedelta(timeframe)
    deltas = frame["open_time"].diff().dropna()
    missing_intervals = int((deltas > expected_delta).sum())
    return {
        "row_count": int(len(frame)),
        "duplicate_rows": int(frame["open_time"].duplicated().sum()),
        "missing_intervals": missing_intervals,
        "start": frame["open_time"].min().isoformat(),
        "end": frame["open_time"].max().isoformat(),
    }
