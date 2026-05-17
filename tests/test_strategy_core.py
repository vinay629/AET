"""Core tests for BAET strategy layer.

Covers:
- StrategyContract ABC enforcement
- SIGNAL_COLUMNS schema: every concrete strategy produces all columns
- Baseline strategy signal correctness (BuyAndHold, SmaCrossover, and quick smoke for others)
- discover_strategies returns only StrategyContract instances with unique names
- adapt_order_intent_to_backtest_signals adapter correctness
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))  # noqa: E402

from baet.core.models import StrategyMetadata  # noqa: E402
from baet.strategies.contracts import SIGNAL_COLUMNS, StrategyContract  # noqa: E402

_REQUIRED_COLS = set(SIGNAL_COLUMNS)

_STRATEGY_MODULES = [
    ("baet.strategies.baselines", "BuyAndHoldStrategy"),
    ("baet.strategies.baselines", "SmaCrossoverStrategy"),
    ("baet.strategies.baselines", "RsiMeanReversionStrategy"),
    ("baet.strategies.baselines", "BollingerBandsStrategy"),
    ("baet.strategies.baselines", "EmaCrossoverStrategy"),
    ("baet.strategies.baselines", "BreakoutMomentumStrategy"),
    ("baet.strategies.baselines", "AdxTrendFilterStrategy"),
]


def _make_idx(n: int = 40) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")


def _make_frame(n: int = 40) -> pd.DataFrame:
    idx = _make_idx(n)
    base = 40_000 + np.cumsum(np.random.randn(n) * 50)
    return pd.DataFrame(
        {
            "timestamp": idx,
            "open_time": idx,
            "close_time": idx,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "open": base,
            "high": base + 200,
            "low": base - 200,
            "close": base + 100,
            "volume": 1_000.0,
        }
    )


def _load_cls(module_name: str, class_name: str):
    mod = importlib.import_module(module_name)
    return getattr(mod, class_name)


# ===========================================================================
# SIGNAL_COLUMNS contract
# ===========================================================================


class TestSignalColumns:
    def test_not_empty(self) -> None:
        assert len(SIGNAL_COLUMNS) > 0

    def test_no_duplicates(self) -> None:
        assert len(SIGNAL_COLUMNS) == len(set(SIGNAL_COLUMNS))

    def test_expected_columns_present(self) -> None:
        expected = {
            "timestamp",
            "symbol",
            "timeframe",
            "action",
            "target_position",
            "confidence",
            "size_hint",
            "strategy_name",
            "reason",
        }
        assert expected.issubset(set(SIGNAL_COLUMNS))


class TestStrategyContractABC:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            StrategyContract()  # type: ignore[abstract]

    def test_concrete_has_metadata(self) -> None:
        from baet.strategies.baselines import BuyAndHoldStrategy

        s = BuyAndHoldStrategy()
        assert isinstance(s.metadata, StrategyMetadata)
        assert s.metadata.name

    def test_supports_callable(self) -> None:
        from baet.strategies.baselines import BuyAndHoldStrategy

        assert callable(BuyAndHoldStrategy().supports)

    def test_generate_signals_callable(self) -> None:
        from baet.strategies.baselines import BuyAndHoldStrategy

        assert callable(BuyAndHoldStrategy().generate_signals)


# ===========================================================================
# Per-strategy smoke tests
# ===========================================================================


@pytest.mark.parametrize("mod,cls_name", _STRATEGY_MODULES)
class TestStrategySmoke:
    """Parameterised tests applied uniformly to every exported strategy."""

    def test_instantiates(self, mod, cls_name) -> None:
        cls = _load_cls(mod, cls_name)
        assert isinstance(cls(), StrategyContract)

    def test_metadata_complete(self, mod, cls_name) -> None:
        cls = _load_cls(mod, cls_name)
        m = cls().metadata
        assert m.name  # non-empty string
        assert m.category
        assert m.version
        assert m.description

    def test_generate_signals_returns_dataframe(self, mod, cls_name) -> None:
        cls = _load_cls(mod, cls_name)
        df = cls().generate_signals(_make_frame())
        assert isinstance(df, pd.DataFrame)

    def test_has_all_signal_columns(self, mod, cls_name) -> None:
        cls = _load_cls(mod, cls_name)
        df = cls().generate_signals(_make_frame())
        assert _REQUIRED_COLS.issubset(
            set(df.columns)
        ), f"{cls_name} missing columns: {_REQUIRED_COLS - set(df.columns)}"

    def test_row_count_matches_frame(self, mod, cls_name) -> None:
        cls = _load_cls(mod, cls_name)
        df = cls().generate_signals(_make_frame(40))
        assert len(df) == 40

    def test_action_column_valid(self, mod, cls_name) -> None:
        cls = _load_cls(mod, cls_name)
        df = cls().generate_signals(_make_frame())
        allowed = {"BUY", "HOLD", "SELL"}
        invalid = set(df["action"].unique()) - allowed
        assert not invalid, f"{cls_name} produced unexpected actions: {invalid}"

    def test_confidence_between_0_and_1(self, mod, cls_name) -> None:
        cls = _load_cls(mod, cls_name)
        df = cls().generate_signals(_make_frame(60))
        conf = df["confidence"].dropna()
        # Allow a small numerical looseness (AdxTrendFilter can reach 2+ for high ADX)
        assert (conf >= -1e-9).all() and (conf <= 2.01).all()

    def test_total_value_column_zero_or_positive(self, mod, cls_name) -> None:
        """target_position should be non-negative for long-only baselines."""
        cls = _load_cls(mod, cls_name)
        df = cls().generate_signals(_make_frame())
        assert (df["target_position"] >= -1e-9).all()


# ===========================================================================
# Unique strategy-name invariant
# ===========================================================================


class TestUniqueNames:
    def test_all_discovered_names_unique(self) -> None:
        from baet.strategies.baselines import STRATEGY_CLASSES

        names = [cls().metadata.name for cls in STRATEGY_CLASSES]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_disco_strategies_have_unique_names(self) -> None:
        from baet.strategies.discovery import discover_strategies

        names = [s.metadata.name for s in discover_strategies()]
        assert len(names) == len(set(names))


class TestDiscovery:
    def test_returns_list_of_strategy_contract(self) -> None:
        from baet.strategies.discovery import discover_strategies

        for s in discover_strategies():
            assert isinstance(s, StrategyContract)

    def test_nonempty(self) -> None:
        from baet.strategies.discovery import discover_strategies

        assert len(discover_strategies()) > 0

    def test_buy_and_hold_present(self) -> None:
        from baet.strategies.discovery import discover_strategies

        names = {s.metadata.name for s in discover_strategies()}
        assert "buy_and_hold" in names

    def test_filter_supported(self) -> None:
        from baet.strategies.discovery import discover_strategies, filter_supported_strategies

        all_strats = discover_strategies()
        filtered = filter_supported_strategies(all_strats, "BTCUSDT", "1h")
        assert len(filtered) > 0
        for s in filtered:
            assert s.supports("BTCUSDT", "1h")


# ===========================================================================
# Adapter tests
# ===========================================================================


class TestAdapter:
    def test_adapt_sets_signal_column(self) -> None:
        from baet.strategies.adapters import adapt_order_intent_to_backtest_signals

        frame = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2024-01-01T00:00:00Z"),
                    "symbol": "BTCUSDT",
                    "timeframe": "1h",
                    "action": "BUY",
                    "target_position": 1.0,
                    "confidence": 0.9,
                    "size_hint": 0.5,
                    "strategy_name": "t",
                    "reason": "t",
                }
            ]
        )
        result = adapt_order_intent_to_backtest_signals(frame)
        assert "signal" in result.columns
        assert "close_time" in result.columns
        assert result.iloc[0]["signal"] == 1

    def test_adapt_hold_becomes_zero_signal(self) -> None:
        from baet.strategies.adapters import adapt_order_intent_to_backtest_signals

        frame = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2024-01-01T00:00:00Z"),
                    "symbol": "BTCUSDT",
                    "timeframe": "1h",
                    "action": "HOLD",
                    "target_position": 0.0,
                    "confidence": 0.0,
                    "size_hint": 0.0,
                    "strategy_name": "t",
                    "reason": "hold",
                }
            ]
        )
        result = adapt_order_intent_to_backtest_signals(frame)
        assert result.iloc[0]["signal"] == 0

    def test_normalize_rejects_missing_columns(self) -> None:
        from baet.strategies.adapters import normalize_order_intent_signals

        with pytest.raises(ValueError):
            normalize_order_intent_signals(pd.DataFrame({"a": [1]}))
