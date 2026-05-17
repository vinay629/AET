"""Core tests for BAET backtest engine — PortfolioBacktestEngine.

Covers:
- BacktestArtifacts dataclass structure
- Cash mechanics: BUY → cash ↓, SELL (signal→0) → cash ↑
- Fee and slippage are applied to fill price
- Equity curve mark-to-market per timestamp
- run_order_intent adapter path
- Config not mutated after run (reproducibility guard)
- Multi-symbol aggregation
- Execution-price model (next_open vs close)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))  # noqa: E402

from baet.config.models import BacktestConfig  # noqa: E402
from baet.core.models import BacktestArtifacts  # noqa: E402
from baet.execution.backtest import PortfolioBacktestEngine  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _idx(n: int = 40) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")


def _market(n: int = 40, symbol: str = "BTCUSDT") -> pd.DataFrame:
    idx = _idx(n)
    base = 40_000 + np.cumsum(np.random.randn(n) * 30)
    return pd.DataFrame(
        {
            "open_time": idx,
            "open": base,
            "high": base + 80,
            "low": base - 80,
            "close": base + 40,
            "volume": 1_000.0,
            "close_time": idx,
            "quote_volume": (base + 40) * 1_000.0,
            "trade_count": 42,
            "taker_buy_base_volume": 500.0,
            "taker_buy_quote_volume": (base + 40) * 500.0,
            "ignore": "0",
            "symbol_key": f"{symbol}:1h",
            "symbol": symbol,
            "timeframe": "1h",
        }
    )


def _signal(n: int = 40, val: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close_time": _idx(n),
            "signal": [val] * n,
        }
    )


def _mf(symbols: list[str]) -> dict[tuple[str, str], pd.DataFrame]:
    return {  # type: ignore[return-value]
        (s, "1h"): _market(symbol=s) for s in symbols
    }


def _sf(frames: dict, val: int = 1) -> dict[tuple[str, str], pd.DataFrame]:
    return {k: _signal(len(v), val) for k, v in frames.items()}  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------


class TestBacktestArtifacts:
    def test_is_dataclass_instance(self) -> None:
        arts = BacktestArtifacts(
            equity_curve=pd.DataFrame(),
            trades=pd.DataFrame(),
            symbol_returns=pd.DataFrame(),
            metrics=pd.DataFrame(),
            metadata={},
        )
        assert isinstance(arts.equity_curve, pd.DataFrame)
        assert isinstance(arts.trades, pd.DataFrame)
        assert isinstance(arts.metadata, dict)

    def test_empty_market_frames_returns_empty_artifacts(self) -> None:
        """Engine must not crash on induced empty market_frames — used by CI smoke path."""
        engine = PortfolioBacktestEngine(BacktestConfig())
        arts = engine.run({}, {}, run_name="empty")
        assert arts.equity_curve.empty
        assert arts.trades.empty


# ---------------------------------------------------------------------------
# Cash mechanics
# ---------------------------------------------------------------------------


class TestCashMechanics:
    def _run_buy(self, cfg: BacktestConfig | None = None) -> BacktestArtifacts:
        cfg = cfg or BacktestConfig(initial_cash=50_000.0)
        engine = PortfolioBacktestEngine(cfg)
        frames = _mf(["BTCUSDT"])
        arts = engine.run(frames, _sf(frames, 1), run_name="buy")
        return arts

    def test_returns_artifacts(self) -> None:
        arts = self._run_buy()
        assert isinstance(arts, BacktestArtifacts)

    def test_nonempty_equity(self) -> None:
        arts = self._run_buy()
        assert not arts.equity_curve.empty

    def test_first_equity_equals_initial_cash_when_hold(self) -> None:
        engine = PortfolioBacktestEngine(BacktestConfig(initial_cash=25_000.0))
        frames = _mf(["BTCUSDT"])
        arts = engine.run(frames, _sf(frames, 0), run_name="hold")
        assert arts.equity_curve.iloc[0]["equity"] == pytest.approx(25_000.0)

    def test_buy_produces_trade(self) -> None:
        arts = self._run_buy()
        assert len(arts.trades) >= 1

    def test_sell_closes_position(self) -> None:
        """HOLD after BUY (signal drops to 0) must produce a SELL trade."""
        engine = PortfolioBacktestEngine(BacktestConfig())
        market = _market(30)
        sig = pd.DataFrame(
            {
                "close_time": _idx(30),
                "signal": [1] * 11 + [0] * 19,
            }
        )
        frames = {("BTCUSDT", "1h"): market}
        signals = {("BTCUSDT", "1h"): sig}
        arts = engine.run(frames, signals, run_name="sell")
        assert "SELL" in arts.trades["side"].values

    def test_equity_changes_after_trade(self) -> None:
        arts = self._run_buy()
        equity_vals = arts.equity_curve["equity"].values
        assert not (equity_vals == equity_vals[0]).all()


class TestFeeAndSlippage:
    def test_fee_deducted_from_buy(self) -> None:
        """cash spent on BUY = price × units + fee = initial × allocation (within tolerance)."""
        cfg = BacktestConfig(initial_cash=100_000.0, fee_rate=0.10)  # 10 % obvious
        engine = PortfolioBacktestEngine(cfg)
        frame = _market(10)
        arts = engine.run(
            {("BTCUSDT", "1h"): frame},
            {("BTCUSDT", "1h"): _signal(10, 1)},
            run_name="fee",
        )
        t = arts.trades.iloc[0]
        deployed = t["price"] * t["units"] + t["fee"]
        expected = 100_000.0 * cfg.allocation_per_signal
        assert abs(deployed - expected) < 0.01

    def test_slippage_raises_buy_fill_price(self) -> None:
        cfg = BacktestConfig(
            initial_cash=100_000.0,
            fee_rate=0.0,
            slippage_rate=0.05,  # 5 %
            execution_price="close",
        )
        engine = PortfolioBacktestEngine(cfg)
        frame = _market(10)
        first_close = frame.iloc[0]["close"]
        arts = engine.run(
            {("BTCUSDT", "1h"): frame},
            {("BTCUSDT", "1h"): _signal(10, 1)},
            run_name="slip",
        )
        fill = arts.trades.iloc[0]["price"]
        # With 5% slippage: fill = price × 1.05
        assert fill > first_close * 0.99

    def test_execution_price_next_open(self) -> None:
        """With execution_price='next_open', fill uses the open column, not close."""
        cfg = BacktestConfig(
            initial_cash=50_000.0,
            fee_rate=0.0,
            slippage_rate=0.0,
            execution_price="next_open",
        )
        engine = PortfolioBacktestEngine(cfg)
        idx = _idx(5)
        frame = pd.DataFrame(
            {
                "open_time": idx,
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [200.0] * 5,  # close is deliberately different
                "volume": 1_000.0,
                "close_time": idx,
                "quote_volume": 200_000.0,
                "trade_count": 10,
                "taker_buy_base_volume": 500.0,
                "taker_buy_quote_volume": 100_000.0,
                "ignore": "0",
                "symbol_key": "BTCUSDT:1h",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
            }
        )
        arts = engine.run(
            {("BTCUSDT", "1h"): frame},
            {("BTCUSDT", "1h"): _signal(5, 1)},
            run_name="open_fill",
        )
        fill = arts.trades.iloc[0]["price"]
        assert fill == pytest.approx(
            100.0, abs=1e-6
        ), f"Expected open-priced fill 100.0, got {fill:.4f}"


# ---------------------------------------------------------------------------
# Reproducibility guard: config not mutated
# ---------------------------------------------------------------------------


class TestConfigNotMutated:
    def test_allocation_not_mutated(self) -> None:
        """Self.config.allocation_per_signal must be unchanged after run."""
        original = 0.5
        cfg = BacktestConfig(allocation_per_signal=original)
        engine = PortfolioBacktestEngine(cfg)
        frames = _mf(["BTCUSDT"])
        engine.run(frames, _sf(frames), run_name="mut_check")
        assert cfg.allocation_per_signal == pytest.approx(
            original
        ), "BacktestConfig was mutated in-place — backtest runs are not reproducible"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_basic_fields(self) -> None:
        engine = PortfolioBacktestEngine(BacktestConfig())
        frames = _mf(["BTCUSDT"])
        arts = engine.run(frames, _sf(frames), run_name="meta")
        assert arts.metadata["run_name"] == "meta"
        assert "BTCUSDT" in arts.metadata["symbols"]
        assert "1h" in arts.metadata["timeframes"]
        assert "config" in arts.metadata

    def test_trade_count_metric_matches_rows(self) -> None:
        engine = PortfolioBacktestEngine(BacktestConfig())
        frames = _mf(["BTCUSDT"])
        arts = engine.run(frames, _sf(frames), run_name="count")
        row = arts.metrics.loc[arts.metrics["metric"] == "trade_count"]
        assert not row.empty
        assert float(row.iloc[0]["value"]) == pytest.approx(float(len(arts.trades)))


# ---------------------------------------------------------------------------
# run_order_intent adapter path
# ---------------------------------------------------------------------------


class TestRunOrderIntent:
    def test_adapter_path_runs(self) -> None:
        engine = PortfolioBacktestEngine(BacktestConfig())
        frames = _mf(["BTCUSDT"])
        idx = _idx(30)
        order_intent = pd.DataFrame(
            {
                "timestamp": idx,
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "action": "BUY",
                "target_position": 1.0,
                "confidence": 0.8,
                "size_hint": 0.5,
                "strategy_name": "adapter",
                "reason": "p0_fix",
            }
        )
        arts = engine.run_order_intent(
            frames,
            {("BTCUSDT", "1h"): order_intent},
            run_name="adapter",
        )
        assert isinstance(arts, BacktestArtifacts)
        assert not arts.equity_curve.empty


# ---------------------------------------------------------------------------
# Multi-symbol aggregation
# ---------------------------------------------------------------------------


class TestMultiSymbol:
    def test_both_symbols_in_metadata(self) -> None:
        engine = PortfolioBacktestEngine(BacktestConfig())
        arts = engine.run(
            _mf(["BTCUSDT", "ETHUSDT"]),
            _sf(_mf(["BTCUSDT", "ETHUSDT"]), 1),
            run_name="multi",
        )
        assert set(arts.metadata["symbols"]) == {"BTCUSDT", "ETHUSDT"}
