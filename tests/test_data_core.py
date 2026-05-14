from __future__ import annotations

import pandas as pd
import pytest
from baet.data.binance import normalize_klines
from baet.data.validation import validate_candles


def _sample_payload() -> list[list[object]]:
    return [
        [
            1714953600000,
            "62000.0",
            "62500.0",
            "61800.0",
            "62400.0",
            "100.0",
            1714957199999,
            "6240000.0",
            1000,
            "55.0",
            "3432000.0",
            "0",
        ],
        [
            1714957200000,
            "62400.0",
            "62600.0",
            "62300.0",
            "62500.0",
            "110.0",
            1714960799999,
            "6875000.0",
            1100,
            "60.0",
            "3750000.0",
            "0",
        ],
    ]


def test_normalize_klines_produces_expected_columns() -> None:
    frame = normalize_klines(_sample_payload(), "BTCUSDT", "1h", "binance_rest")

    assert frame["symbol"].tolist() == ["BTCUSDT", "BTCUSDT"]
    assert "open_time" in frame.columns
    assert "close_time" in frame.columns


def test_validate_candles_rejects_duplicate_bars() -> None:
    frame = normalize_klines(_sample_payload(), "BTCUSDT", "1h", "binance_rest")
    duplicated = pd.concat([frame.iloc[[0]], frame.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="Duplicate open_time"):
        validate_candles(duplicated, "1h")
