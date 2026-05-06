from pathlib import Path

import pandas as pd

from baet.config.loader import load_settings
from baet.data.features import PandasFeatureBuilder
from baet.data.storage import ParquetMarketDataStore


def _sample_frame() -> pd.DataFrame:
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


def test_parquet_store_round_trip(tmp_path: Path) -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))
    settings.storage.raw_data_dir = tmp_path / "raw"
    settings.storage.processed_data_dir = tmp_path / "processed"
    settings.reporting.backtests_dir = tmp_path / "results" / "backtests"
    store = ParquetMarketDataStore(settings)

    frame = _sample_frame()
    store.write_raw_candles(frame, "BTCUSDT", "1h")
    loaded = store.read_raw_candles("BTCUSDT", "1h")

    pd.testing.assert_frame_equal(loaded, frame)


def test_feature_builder_is_deterministic() -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))
    builder = PandasFeatureBuilder(settings.features)
    frame = _sample_frame()

    first = builder.build(frame)
    second = builder.build(frame)

    pd.testing.assert_frame_equal(first, second)
    assert "atr_like_14" in first.columns
    assert "relative_volume_5" in first.columns
