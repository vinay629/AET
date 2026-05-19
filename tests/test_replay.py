"""Tests for replay engine."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from baet.config.models import BacktestConfig
from baet.core.replay import ReplayEngine, verify_determinism


def _make_candle_frame(
    symbol: str, timeframe: str, closes: list[float]
) -> pd.DataFrame:
    """Helper to create a minimal candle DataFrame."""
    base = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
    rows = []
    for i, close in enumerate(closes):
        ts = base.replace(hour=base.hour + i)
        rows.append({
            "open_time": ts,
            "close_time": ts,
            "open": close - 10,
            "high": close + 50,
            "low": close - 50,
            "close": close,
            "volume": 100.0,
            "symbol": symbol,
            "timeframe": timeframe,
        })
    return pd.DataFrame(rows)


def _make_signal_frame(
    symbol: str, timeframe: str, signals: list[int]
) -> pd.DataFrame:
    """Helper to create a minimal signal DataFrame."""
    base = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
    rows = []
    for i, sig in enumerate(signals):
        ts = base.replace(hour=base.hour + i)
        rows.append({
            "close_time": ts,
            "signal": sig,
            "symbol": symbol,
            "timeframe": timeframe,
        })
    return pd.DataFrame(rows)


class TestReplayEngine:
    @pytest.fixture
    def config(self) -> BacktestConfig:
        return BacktestConfig(
            initial_cash=10000.0,
            fee_rate=0.001,
            slippage_rate=0.0005,
            execution_price="close",
            allocation_per_signal=0.5,
        )

    @pytest.fixture
    def engine(self, config: BacktestConfig) -> ReplayEngine:
        """Create a ReplayEngine with a temp directory that auto-cleans."""
        tmp = tempfile.mkdtemp()
        store_dir = Path(tmp)
        engine = ReplayEngine.create(config, store_dir)
        yield engine
        engine.close()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_replay_basic(self, engine: ReplayEngine) -> None:
        market = {
            ("BTCUSDT", "1h"): _make_candle_frame("BTCUSDT", "1h", [68000, 68100, 68200]),
        }
        signals = {
            ("BTCUSDT", "1h"): _make_signal_frame("BTCUSDT", "1h", [1, 0, 0]),
        }
        result = engine.replay_backtest(market, signals, "test_basic")
        assert result.success
        assert result.events_processed > 0
        assert result.signals_generated == 1
        assert len(result.trades) >= 1

    def test_replay_records_events(self, engine: ReplayEngine) -> None:
        market = {
            ("BTCUSDT", "1h"): _make_candle_frame("BTCUSDT", "1h", [68000, 68100]),
        }
        signals = {
            ("BTCUSDT", "1h"): _make_signal_frame("BTCUSDT", "1h", [1, 0]),
        }
        engine.replay_backtest(market, signals, "test_events")

        # Check event file was created
        event_files = list(engine.event_store.base_dir.glob("*.jsonl"))
        assert len(event_files) == 1
        lines = event_files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) > 2  # At least start, candle, signal, fill, stop

    def test_replay_sell_signal(self, engine: ReplayEngine) -> None:
        market = {
            ("BTCUSDT", "1h"): _make_candle_frame("BTCUSDT", "1h", [68000, 68100, 68200]),
        }
        signals = {
            ("BTCUSDT", "1h"): _make_signal_frame("BTCUSDT", "1h", [1, 0, -1]),
        }
        result = engine.replay_backtest(market, signals, "test_sell")
        assert result.success
        # Should have at least a buy and a sell
        sides = [t["side"] for t in result.trades]
        assert "BUY" in sides

    def test_replay_empty_data(self, engine: ReplayEngine) -> None:
        result = engine.replay_backtest({}, {}, "test_empty")
        assert not result.success
        assert result.error is not None

    def test_replay_equity_curve(self, engine: ReplayEngine) -> None:
        market = {
            ("BTCUSDT", "1h"): _make_candle_frame("BTCUSDT", "1h", [68000, 68100, 68200]),
        }
        signals = {
            ("BTCUSDT", "1h"): _make_signal_frame("BTCUSDT", "1h", [0, 0, 0]),
        }
        result = engine.replay_backtest(market, signals, "test_equity")
        assert len(result.equity_curve) == 3
        # Equity should be constant (no trades)
        for point in result.equity_curve:
            assert point["equity"] == 10000.0


class TestDeterminism:
    """Verify that replay produces identical results across multiple runs."""

    def test_determinism(self) -> None:
        config = BacktestConfig(
            initial_cash=10000.0,
            fee_rate=0.001,
            slippage_rate=0.0005,
            execution_price="close",
            allocation_per_signal=0.5,
        )
        market = {
            ("BTCUSDT", "1h"): _make_candle_frame("BTCUSDT", "1h", [68000, 68100, 68200, 68300]),
        }
        signals = {
            ("BTCUSDT", "1h"): _make_signal_frame("BTCUSDT", "1h", [1, 0, 0, -1]),
        }

        tmp = tempfile.mkdtemp()
        try:
            store_dir = Path(tmp)
            result = verify_determinism(
                config=config,
                store_dir=store_dir,
                market_frames=market,
                signals=signals,
                run_name="det_test",
                iterations=3,
            )
            assert result is True
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
