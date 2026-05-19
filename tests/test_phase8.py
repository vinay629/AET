"""Tests for Phase 8 — Institutional Research Discipline."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from baet.ml.feature_store import FeatureStore, FeatureVersion
from baet.research.synthetic import (
    generate_trending,
    generate_mean_reverting,
    generate_garch,
    generate_jump_diffusion,
    generate_liquidity_shock,
    generate_flash_crash,
    generate_regime_transition,
    SyntheticConfig,
)
from baet.execution.cost_model import ExecutionCostModel, CostModelConfig


class TestFeatureStore:
    def test_compute_and_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FeatureStore(Path(tmp))

            def sma_builder(data: pd.DataFrame, period: int = 20, **kwargs: Any) -> pd.DataFrame:
                return pd.DataFrame({"sma": data["close"].rolling(period).mean()})

            data = pd.DataFrame({"close": np.random.randn(100).cumsum() + 100})
            snapshot = store.compute("sma", data, sma_builder, parameters={"period": 20})

            assert snapshot.n_samples == 100
            assert snapshot.n_features == 1
            assert snapshot.quality_score > 0

    def test_retrieve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FeatureStore(Path(tmp))

            def builder(data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
                return pd.DataFrame({"f1": data["close"] * 2})

            data = pd.DataFrame({"close": np.random.randn(50).cumsum()})
            store.compute("test_feat", data, builder)

            retrieved = store.get("test_feat")
            assert retrieved is not None
            assert retrieved.n_samples == 50

    def test_point_in_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FeatureStore(Path(tmp))

            def builder(data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
                return pd.DataFrame({
                    "timestamp": data["timestamp"],
                    "f1": data["close"],
                })

            data = pd.DataFrame({
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="h"),
                "close": np.random.randn(100).cumsum(),
            })
            store.compute("ts_feat", data, builder)

            pit = store.get_point_in_time("ts_feat", "2024-01-03")
            assert pit is not None
            assert len(pit) < 100  # Should be subset

    def test_list_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FeatureStore(Path(tmp))

            def builder(data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
                return pd.DataFrame({"f": data["close"]})

            data = pd.DataFrame({"close": np.arange(50.0)})
            store.compute("feat_a", data, builder)
            store.compute("feat_b", data, builder)

            features = store.list_features()
            assert len(features) == 2

    def test_deterministic(self) -> None:
        """Same input + params → same content hash."""
        with tempfile.TemporaryDirectory() as tmp:
            store = FeatureStore(Path(tmp))

            def builder(data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
                return pd.DataFrame({"f": data["close"]})

            data = pd.DataFrame({"close": np.arange(50.0)})
            s1 = store.compute("det_feat", data, builder, parameters={"p": 1})
            s2 = store.compute("det_feat", data, builder, parameters={"p": 1})

            assert s1.version.content_hash == s2.version.content_hash


class TestSyntheticGenerator:
    def test_trending(self) -> None:
        config = SyntheticConfig(n_bars=500, seed=42)
        df = generate_trending(config, trend_strength=0.001)
        assert len(df) == 500
        assert "close" in df.columns
        # Trending market should have positive drift
        assert df["close"].iloc[-1] > df["close"].iloc[0]

    def test_mean_reverting(self) -> None:
        config = SyntheticConfig(n_bars=500, seed=42)
        df = generate_mean_reverting(config, mean=100, speed=0.05)
        assert len(df) == 500
        # Prices should stay near mean
        assert 50 < df["close"].mean() < 150

    def test_garch(self) -> None:
        config = SyntheticConfig(n_bars=1000, seed=42)
        df = generate_garch(config)
        assert len(df) == 1000
        # GARCH should produce volatility clustering
        returns = df["close"].pct_change().dropna()
        assert returns.std() > 0

    def test_jump_diffusion(self) -> None:
        config = SyntheticConfig(n_bars=1000, seed=42)
        df = generate_jump_diffusion(config, jump_intensity=0.05)
        assert len(df) == 1000
        # Should have some large moves
        returns = df["close"].pct_change().dropna()
        assert returns.kurtosis() > 1  # Fat tails from jumps

    def test_liquidity_shock(self) -> None:
        config = SyntheticConfig(n_bars=1000, seed=42)
        df = generate_liquidity_shock(config, shock_bar=500, shock_magnitude=0.05)
        assert len(df) == 1000
        # Should see a drop around bar 500
        assert df["close"].iloc[500] < df["close"].iloc[490]

    def test_flash_crash(self) -> None:
        config = SyntheticConfig(n_bars=1000, seed=42)
        df = generate_flash_crash(config, crash_bar=500, crash_magnitude=0.15)
        assert len(df) == 1000
        # Should see rapid drop and partial recovery
        pre_crash = df["close"].iloc[495]
        post_crash = df["close"].iloc[505]
        assert post_crash < pre_crash  # Net drop

    def test_regime_transition(self) -> None:
        config = SyntheticConfig(n_bars=1000, seed=42)
        df = generate_regime_transition(
            config, transition_bar=500, from_regime="low_vol", to_regime="high_vol"
        )
        assert len(df) == 1000
        # Volatility should increase after transition
        pre_vol = df["close"].iloc[:500].pct_change().std()
        post_vol = df["close"].iloc[500:].pct_change().std()
        assert post_vol > pre_vol

    def test_deterministic(self) -> None:
        """Same seed → same output."""
        config = SyntheticConfig(n_bars=100, seed=42)
        df1 = generate_trending(config)
        df2 = generate_trending(config)
        pd.testing.assert_frame_equal(df1, df2)

    def test_ohlcv_consistency(self) -> None:
        """High >= max(Open, Close), Low <= min(Open, Close)."""
        config = SyntheticConfig(n_bars=500, seed=42)
        for gen_fn in [generate_trending, generate_mean_reverting, generate_garch]:
            df = gen_fn(config)
            assert (df["high"] >= df["open"]).all()
            assert (df["high"] >= df["close"]).all()
            assert (df["low"] <= df["open"]).all()
            assert (df["low"] <= df["close"]).all()
            assert (df["high"] >= df["low"]).all()


class TestExecutionCostModel:
    def test_basic_cost_estimation(self) -> None:
        model = ExecutionCostModel()
        cost = model.estimate_cost(
            symbol="BTCUSDT",
            side="BUY",
            quantity=1.0,
            price=50000,
            adv=10000,
            volatility=0.02,
        )
        assert cost.total_cost_bps > 0
        assert cost.fill_price > 0
        assert cost.filled_quantity > 0

    def test_spread_component(self) -> None:
        model = ExecutionCostModel(CostModelConfig(normal_spread_bps=10))
        cost = model.estimate_cost("BTC", "BUY", 1, 50000, 10000, 0.02)
        # Spread cost should be half of spread = 5 bps
        assert 4 < cost.spread_cost_bps < 6

    def test_impact_increases_with_size(self) -> None:
        model = ExecutionCostModel()
        small = model.estimate_cost("BTC", "BUY", 0.1, 50000, 10000, 0.02)
        large = model.estimate_cost("BTC", "BUY", 10, 50000, 10000, 0.02)
        assert large.impact_cost_bps > small.impact_cost_bps

    def test_impact_increases_with_volatility(self) -> None:
        model = ExecutionCostModel()
        low_vol = model.estimate_cost("BTC", "BUY", 1, 50000, 10000, 0.01)
        high_vol = model.estimate_cost("BTC", "BUY", 1, 50000, 10000, 0.05)
        assert high_vol.impact_cost_bps > low_vol.impact_cost_bps

    def test_capacity_estimation(self) -> None:
        model = ExecutionCostModel()
        capacity = model.estimate_capacity("BTC", adv=10000, volatility=0.02, target_cost_bps=10)
        assert capacity["max_participation_pct"] > 0
        assert capacity["max_quantity"] > 0

    def test_sell_side(self) -> None:
        model = ExecutionCostModel()
        cost = model.estimate_cost("BTC", "SELL", 1, 50000, 10000, 0.02)
        # Sell should have fill price below mid
        assert cost.fill_price < 50000

    def test_fee_component(self) -> None:
        model = ExecutionCostModel(CostModelConfig(
            maker_fee_bps=2, taker_fee_bps=5, maker_probability=0.5
        ))
        cost = model.estimate_cost("BTC", "BUY", 1, 50000, 10000, 0.02)
        # Expected fee: 0.5*2 + 0.5*5 = 3.5 bps
        assert 2 < cost.fee_cost_bps < 5

    def test_implementation_shortfall(self) -> None:
        model = ExecutionCostModel()
        cost = model.estimate_cost("BTC", "BUY", 1, 50000, 10000, 0.02)
        # Buy shortfall should be positive (paid more than expected)
        assert cost.implementation_shortfall_bps > 0

    def test_partial_fills(self) -> None:
        model = ExecutionCostModel(CostModelConfig(partial_fill_probability=1.0, avg_fill_ratio=0.5))
        cost = model.estimate_cost("BTC", "BUY", 1, 50000, 10000, 0.02)
        assert cost.is_partial is True
        assert cost.filled_quantity < 1.0
