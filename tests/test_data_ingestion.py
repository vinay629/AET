from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from baet.config.loader import load_settings
from baet.data.binance import BinanceLiveStream, normalize_klines
from baet.data.validation import summarize_data_quality, validate_candles


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


def test_normalize_klines_produces_canonical_schema() -> None:
    frame = normalize_klines(_sample_payload(), "BTCUSDT", "1h", "binance_rest")

    assert list(frame.columns)[0:4] == ["symbol", "timeframe", "open_time", "close_time"]
    assert frame["symbol"].tolist() == ["BTCUSDT", "BTCUSDT"]
    assert str(frame["open_time"].dtype).startswith("datetime64")


def test_validate_candles_rejects_duplicates() -> None:
    frame = normalize_klines(_sample_payload(), "BTCUSDT", "1h", "binance_rest")
    duplicated = pd.concat([frame.iloc[[0]], frame.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="Duplicate open_time"):
        validate_candles(duplicated, "1h")


def test_data_quality_summary_detects_gap() -> None:
    frame = normalize_klines(_sample_payload(), "BTCUSDT", "1h", "binance_rest")
    frame.loc[1, "open_time"] = datetime(2024, 5, 6, 3, tzinfo=UTC)
    summary = summarize_data_quality(frame.sort_values("open_time"), "1h")

    assert summary["missing_intervals"] == 1


def test_live_stream_builds_expected_url() -> None:
    settings = load_settings(mode="paper", env_file=Path(".env.example"))
    stream = BinanceLiveStream(settings, "BTCUSDT", "1h")

    assert stream.stream_name == "btcusdt@kline_1h"
    assert stream.stream_url.endswith("/btcusdt@kline_1h")
