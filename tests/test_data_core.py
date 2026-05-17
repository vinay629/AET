"""Core tests for BAET data layer.

Covers:
- CANONICAL_CANDLE_COLUMNS schema contract
- normalize_klines with full payload, empty payload, string floats, and sorting
- ParquetMarketDataStore round-trip (write → read → compare)
- BinanceHistoricalProvider implementation of HistoricalDataProvider ABC
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))  # noqa: E402

from baet.data.interfaces import HistoricalDataProvider, MarketDataStore  # noqa: E402
from baet.data.schemas import CANONICAL_CANDLE_COLUMNS, CandleSchema  # noqa: E402
from baet.data.storage import ParquetMarketDataStore  # noqa: E402

# ---------------------------------------------------------------------------
# Schema contract tests
# ---------------------------------------------------------------------------


class TestCanonicalSchema:
    def test_columns_present(self) -> None:
        required = {
            "symbol",
            "timeframe",
            "open_time",
            "close_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }
        assert required.issubset(set(CANONICAL_CANDLE_COLUMNS))

    def test_no_duplicate_columns(self) -> None:
        assert len(CANONICAL_CANDLE_COLUMNS) == len(set(CANONICAL_CANDLE_COLUMNS))

    def test_schema_frozen_dataclass(self) -> None:
        cs = CandleSchema(symbol="BTCUSDT", timeframe="1h", source="test")
        assert cs.symbol == "BTCUSDT"
        assert cs.timeframe == "1h"
        assert cs.source == "test"
        with pytest.raises(AttributeError):
            cs.symbol = "ETHUSDT"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# normalize_klines tests
# ---------------------------------------------------------------------------


def _make_klines(n: int = 3) -> list[list]:
    base_ts = 1_700_000_000_000
    rows = []
    for i in range(n):
        o, h, l, c, vq = 40_000, 41_000, 39_000, 40_500, 425_000.0  # noqa: E741
        t = base_ts + i * 3_600_000
        rows.append(
            [
                t,
                str(o),
                str(h),
                str(l),
                str(c),
                str(vq),
                t + 3_500_000,
                str(vq),
                42,
                str(vq * 0.5),
                str(212_500.0),
                "0",
            ]
        )
    return rows


class TestNormalizeKlines:
    def test_returns_dataframe(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(), "BTCUSDT", "1h", "test")
        assert isinstance(r, pd.DataFrame)

    def test_canonical_columns(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(), "BTCUSDT", "1h", "test")
        assert list(r.columns) == CANONICAL_CANDLE_COLUMNS

    def test_symbol_column_set(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(), "ETHUSDT", "4h", "test")
        assert (r["symbol"] == "ETHUSDT").all()

    def test_timeframe_column_set(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(), "BTCUSDT", "1h", "test")
        assert (r["timeframe"] == "1h").all()

    def test_numeric_columns_float64(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(), "BTCUSDT", "1h", "test")
        for col in (
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ):
            assert pd.api.types.is_float_dtype(r[col]), f"{col} must be float64"

    def test_trade_count_int(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(), "BTCUSDT", "1h", "test")
        assert pd.api.types.is_integer_dtype(r["trade_count"])

    def test_timestamps_datetime(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(), "BTCUSDT", "1h", "test")
        assert pd.api.types.is_datetime64_any_dtype(r["open_time"])

    def test_empty_payload_empty_frame(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines([], "BTCUSDT", "1h", "test")
        assert r.empty
        assert list(r.columns) == CANONICAL_CANDLE_COLUMNS

    def test_row_count_matches(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(7), "BTCUSDT", "1h", "test")
        assert len(r) == 7

    def test_sorted_by_open_time(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(list(reversed(_make_klines(5))), "BTCUSDT", "1h", "test")
        assert r["open_time"].is_monotonic_increasing

    def test_source_column(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(), "BTCUSDT", "1h", "binance_rest")
        assert (r["source"] == "binance_rest").all()

    def test_close_matches_input(self) -> None:
        from baet.data.binance import normalize_klines

        r = normalize_klines(_make_klines(1), "BTCUSDT", "1h", "test")
        assert r.iloc[0]["close"] == pytest.approx(40_500.0)


# ---------------------------------------------------------------------------
# ParquetMarketDataStore tests
# ---------------------------------------------------------------------------


class TestParquetMarketDataStore:
    @pytest.fixture()
    def store(self, tmp_path: Path) -> ParquetMarketDataStore:
        from baet.config.models import Settings, StorageConfig

        settings = Settings(
            storage=StorageConfig(
                raw_data_dir=tmp_path / "raw",
                processed_data_dir=tmp_path / "processed",
                results_dir=tmp_path / "results",
                logs_dir=tmp_path / "logs",
                artifacts_dir=tmp_path / "artifacts",
                models_dir=tmp_path / "models",
            )
        )
        return ParquetMarketDataStore(settings)

    def test_implements_market_data_store(self, store) -> None:
        assert isinstance(store, MarketDataStore)

    @pytest.fixture()
    def candle_frame(self):
        idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
        return pd.DataFrame(
            [
                {
                    "symbol": "BTCUSDT",
                    "timeframe": "1h",
                    "open_time": idx[0],
                    "close_time": idx[0],
                    "open": 40_000.0,
                    "high": 41_000.0,
                    "low": 39_000.0,
                    "close": 40_500.0,
                    "volume": 100.0,
                    "quote_volume": 4_050_000.0,
                    "trade_count": 10,
                    "taker_buy_base_volume": 50.0,
                    "taker_buy_quote_volume": 2_025_000.0,
                    "source": "test",
                }
            ]
            * 3
        )

    def test_write_raw_creates_file(self, store, tmp_path: Path) -> None:
        frame = pd.DataFrame(
            [
                {
                    "symbol": "BTCUSDT",
                    "timeframe": "1h",
                    "open_time": pd.Timestamp("2024-01-01"),
                    "close_time": pd.Timestamp("2024-01-01"),
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 1.0,
                    "quote_volume": 1.0,
                    "trade_count": 1,
                    "taker_buy_base_volume": 0.5,
                    "taker_buy_quote_volume": 0.5,
                    "source": "test",
                }
            ]
        )
        store.write_raw_candles(frame, "BTCUSDT", "1h")
        expected = tmp_path / "raw" / "BTCUSDT" / "1h" / "candles.parquet"
        assert expected.exists()

    def test_read_raw_returns_dataframe(self, store) -> None:
        frame = pd.DataFrame(
            [
                {
                    "symbol": "BTCUSDT",
                    "timeframe": "1h",
                    "open_time": pd.Timestamp("2024-01-01T00:00:00Z"),
                    "close_time": pd.Timestamp("2024-01-01T01:00:00Z"),
                    "open": 40_000.0,
                    "high": 41_000.0,
                    "low": 39_000.0,
                    "close": 40_500.0,
                    "volume": 100.0,
                    "quote_volume": 4_050_000.0,
                    "trade_count": 10,
                    "taker_buy_base_volume": 50.0,
                    "taker_buy_quote_volume": 2_025_000.0,
                    "source": "test",
                }
            ]
        )
        store.write_raw_candles(frame, "BTCUSDT", "1h")
        result = store.read_raw_candles("BTCUSDT", "1h")
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert result.iloc[0]["close"] == pytest.approx(40_500.0)

    def test_write_features_roundtrip(self, store, tmp_path: Path) -> None:  # noqa: ARG002
        feat = pd.DataFrame(
            [
                {
                    "symbol": "BTCUSDT",
                    "timeframe": "1h",
                    "sma_20": 42_000.0,
                    "rsi_14": 55.0,
                }
            ]
        )
        store.write_features(feat, "BTCUSDT", "1h")
        result = store.read_features("BTCUSDT", "1h")
        assert not result.empty
        assert result.iloc[0]["sma_20"] == pytest.approx(42_000.0)

    def test_write_backtest_artifacts_creates_files(self, store) -> None:
        equity = pd.DataFrame({"timestamp": [pd.Timestamp("2024-01-01")], "equity": [10_100.0]})
        trades = pd.DataFrame(columns=["timestamp", "side"])
        sym_ret = pd.DataFrame(columns=["timestamp", "symbol_key", "return"])
        metrics = pd.DataFrame(columns=["metric", "value"])
        store.write_backtest_artifacts(equity, trades, sym_ret, metrics, "core_test")
        store.write_metadata({"run_name": "core_test"}, "core_test")
        run_dir = store.backtests_root / "core_test"
        assert (run_dir / "equity_curve.parquet").exists()
        assert (run_dir / "trades.parquet").exists()
        assert (run_dir / "metadata.json").exists()


# ---------------------------------------------------------------------------
# BinanceHistoricalProvider ABC tests
# ---------------------------------------------------------------------------


class TestBinanceHistoricalProviderABC:
    def test_class_is_historical_provider(self) -> None:
        from baet.data.binance import BinanceHistoricalProvider

        assert issubclass(BinanceHistoricalProvider, HistoricalDataProvider)

    def test_fetch_klines_returns_dataframe(self) -> None:
        """Patch urlopen to avoid real network calls, keeping context-manager contract."""
        from baet.data.binance import BinanceHistoricalProvider

        fake_rows = [
            [
                1_700_000_000_000,
                "40000",
                "41000",
                "39000",
                "40500",
                "1000",
                1_700_000_500_000,
                "4_050_000",
                42,
                "500",
                "2_025_000",
                "0",
            ]
        ]

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_rows).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("baet.data.binance.urlopen", return_value=mock_resp):
            from baet.config.models import Settings

            s = Settings()
            prov = BinanceHistoricalProvider(s)
            df = prov.fetch_klines(
                "BTCUSDT",
                "1h",
                datetime(2023, 11, 15, tzinfo=datetime.UTC),
                datetime(2023, 11, 16, tzinfo=datetime.UTC),
            )

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert df.iloc[0]["symbol"] == "BTCUSDT"
        assert df.iloc[0]["close"] == pytest.approx(40_500.0)
        assert pd.api.types.is_datetime64_any_dtype(df["open_time"])

    def test_fetch_klines_empty_payload(self) -> None:
        from baet.data.binance import BinanceHistoricalProvider

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_resp.__enter__.return_value = mock_resp

        with patch("baet.data.binance.urlopen", return_value=mock_resp):
            from baet.config.models import Settings

            s = Settings()
            prov = BinanceHistoricalProvider(s)
            df = prov.fetch_klines(
                "BTCUSDT",
                "1h",
                datetime(2023, 11, 15, tzinfo=datetime.UTC),
                datetime(2023, 11, 16, tzinfo=datetime.UTC),
            )

        assert df.empty
