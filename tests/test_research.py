"""Tests for research infrastructure."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from baet.research.experiment import (
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentTracker,
)
from baet.research.walk_forward import (
    AggregateResult,
    WalkForwardValidator,
    WindowConfig,
)
from baet.research.feature_registry import (
    FeatureRegistry,
    FeatureSpec,
    FeatureValidationResult,
)
from baet.research.metrics import MetricsEngine


class TestExperimentConfig:
    def test_config_hash(self) -> None:
        config = ExperimentConfig(name="test", strategy_name="sma")
        h1 = config.config_hash
        h2 = config.config_hash
        assert h1 == h2
        assert len(h1) == 16

    def test_different_configs_different_hashes(self) -> None:
        c1 = ExperimentConfig(name="test1")
        c2 = ExperimentConfig(name="test2")
        assert c1.config_hash != c2.config_hash


class TestExperimentMetrics:
    def test_to_dict(self) -> None:
        metrics = ExperimentMetrics(
            sharpe_ratio=1.5,
            max_drawdown_pct=10.0,
            total_trades=50,
        )
        d = metrics.to_dict()
        assert d["sharpe_ratio"] == 1.5
        assert d["max_drawdown_pct"] == 10.0
        assert d["total_trades"] == 50


class TestExperimentTracker:
    def test_create_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ExperimentTracker(Path(tmp))
            config = ExperimentConfig(name="test_exp", strategy_name="sma")
            exp = tracker.create(config, tags=["test"])
            assert exp.status == "pending"
            assert "test" in exp.tags
            assert exp.experiment_id is not None

    def test_complete_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ExperimentTracker(Path(tmp))
            config = ExperimentConfig(name="test")
            exp = tracker.create(config)
            tracker.start()

            metrics = ExperimentMetrics(sharpe_ratio=1.5, total_trades=10)
            completed = tracker.complete(metrics)

            assert completed.status == "completed"
            assert completed.metrics.sharpe_ratio == 1.5

    def test_list_experiments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ExperimentTracker(Path(tmp))
            for i in range(3):
                config = ExperimentConfig(name=f"exp_{i}")
                exp = tracker.create(config)
                tracker.complete(ExperimentMetrics(), experiment_id=exp.experiment_id)

            experiments = tracker.list_experiments()
            assert len(experiments) == 3

    def test_list_by_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ExperimentTracker(Path(tmp))
            config = ExperimentConfig(name="test")
            exp = tracker.create(config)
            tracker.complete(ExperimentMetrics(), experiment_id=exp.experiment_id)

            completed = tracker.list_experiments(status="completed")
            assert len(completed) == 1
            pending = tracker.list_experiments(status="pending")
            assert len(pending) == 0

    def test_compare_experiments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ExperimentTracker(Path(tmp))
            ids = []
            for i in range(2):
                config = ExperimentConfig(name=f"exp_{i}")
                exp = tracker.create(config)
                metrics = ExperimentMetrics(sharpe_ratio=1.0 + i * 0.5)
                tracker.complete(metrics, experiment_id=exp.experiment_id)
                ids.append(exp.experiment_id)

            comparison = tracker.compare(ids)
            assert len(comparison) == 2

    def test_get_best(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ExperimentTracker(Path(tmp))
            for i in range(3):
                config = ExperimentConfig(name=f"exp_{i}")
                exp = tracker.create(config)
                metrics = ExperimentMetrics(
                    sharpe_ratio=0.5 + i * 0.5,
                    total_trades=20,
                )
                tracker.complete(metrics, experiment_id=exp.experiment_id)

            best = tracker.get_best(metric="sharpe_ratio")
            assert best is not None
            assert best.metrics.sharpe_ratio == 1.5

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ExperimentTracker(Path(tmp))
            config = ExperimentConfig(name="test", strategy_name="sma")
            exp = tracker.create(config)
            metrics = ExperimentMetrics(sharpe_ratio=1.2, total_trades=15)
            tracker.complete(metrics, experiment_id=exp.experiment_id)

            # Reload
            loaded = tracker._load(exp.experiment_id)
            assert loaded is not None
            assert loaded.metrics.sharpe_ratio == 1.2
            assert loaded.status == "completed"


class TestWalkForwardValidator:
    def test_generate_windows(self) -> None:
        validator = WalkForwardValidator(
            WindowConfig(train_period="6m", test_period="1m", step_period="1m"),
        )
        windows = validator.generate_windows("2020-01-01", "2021-01-01")
        assert len(windows) > 0
        # Each window is (train_start, train_end, test_start, test_end)
        for w in windows:
            assert len(w) == 4

    def test_window_count(self) -> None:
        validator = WalkForwardValidator(
            WindowConfig(train_period="6m", test_period="1m", step_period="1m"),
        )
        windows = validator.generate_windows("2020-01-01", "2021-01-01")
        # ~12 months, 6m train + 1m test = 7m per window, step 1m
        # Should get approximately 5-6 windows
        assert 4 <= len(windows) <= 8

    def test_aggregate_result_robustness(self) -> None:
        result = AggregateResult(
            total_windows=10,
            completed_windows=8,
            avg_sharpe=1.2,
            sharpe_std=0.3,
            pct_positive_windows=0.75,
            max_consecutive_lossing_windows=1,
        )
        assert result.is_robust is True

    def test_aggregate_not_robust_low_positive(self) -> None:
        result = AggregateResult(
            total_windows=10,
            completed_windows=8,
            avg_sharpe=0.5,
            pct_positive_windows=0.4,
        )
        assert result.is_robust is False

    def test_aggregate_not_robust_consecutive_losses(self) -> None:
        result = AggregateResult(
            total_windows=10,
            completed_windows=8,
            avg_sharpe=0.8,
            pct_positive_windows=0.7,
            max_consecutive_lossing_windows=3,
        )
        assert result.is_robust is False


class TestFeatureRegistry:
    def test_register_and_build(self) -> None:
        registry = FeatureRegistry()

        def sma_builder(data: pd.DataFrame, period: int = 20, **kwargs: Any) -> pd.Series:
            return data["close"].rolling(period).mean()

        spec = FeatureSpec(name="sma_20", lookback=20, parameters={"period": 20})
        registry.register(spec, sma_builder)

        data = pd.DataFrame({"close": np.random.randn(100).cumsum() + 50000})
        result = registry.build("sma_20", data)
        assert len(result) == 100

    def test_validate_feature(self) -> None:
        registry = FeatureRegistry()

        def good_builder(data: pd.DataFrame, **kwargs: Any) -> pd.Series:
            return data["close"].rolling(10).mean()

        spec = FeatureSpec(name="sma_10", lookback=10)
        registry.register(spec, good_builder)

        data = pd.DataFrame({"close": np.random.randn(200).cumsum() + 50000})
        result = registry.validate("sma_10", data)
        assert isinstance(result, FeatureValidationResult)

    def test_validate_detects_non_deterministic(self) -> None:
        registry = FeatureRegistry()

        call_count = [0]

        def random_builder(data: pd.DataFrame, **kwargs: Any) -> pd.Series:
            call_count[0] += 1
            return pd.Series(np.random.randn(len(data)))

        spec = FeatureSpec(name="random_feat", deterministic=False)
        registry.register(spec, random_builder)

        data = pd.DataFrame({"close": np.random.randn(50).cumsum()})
        result = registry.validate("random_feat", data)
        assert result.checks.get("deterministic") is False

    def test_list_features(self) -> None:
        registry = FeatureRegistry()
        registry.register(FeatureSpec(name="f1", category="technical"), lambda d, **k: d["close"])
        registry.register(FeatureSpec(name="f2", category="volume"), lambda d, **k: d["volume"])

        all_features = registry.list_features()
        assert len(all_features) == 2

        technical = registry.list_features(category="technical")
        assert len(technical) == 1

    def test_dependency_resolution(self) -> None:
        registry = FeatureRegistry()
        registry.register(FeatureSpec(name="base", lookback=10), lambda d, **k: d["close"])
        registry.register(
            FeatureSpec(name="derived", lookback=20, depends_on=["base"]),
            lambda d, **k: d["close"].rolling(20).mean(),
        )

        ordered = registry._resolve_dependencies(["base_v1.0.0", "derived_v1.0.0"])
        assert len(ordered) == 2


class TestMetricsEngine:
    def test_basic_metrics(self) -> None:
        engine = MetricsEngine()
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=1000, freq="h"),
            "equity": np.linspace(10000, 11000, 1000),
        })

        metrics = engine.compute(equity)
        assert metrics.total_return_pct > 0
        assert metrics.sharpe_ratio > 0
        assert metrics.max_drawdown_pct >= 0

    def test_drawdown_calculation(self) -> None:
        engine = MetricsEngine()
        # Create equity curve with known drawdown
        eq = [100, 110, 120, 115, 100, 90, 95, 100, 110, 120]
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=len(eq), freq="h"),
            "equity": eq,
        })

        metrics = engine.compute(equity, initial_cash=100)
        assert metrics.max_drawdown_pct > 0

    def test_trade_metrics(self) -> None:
        engine = MetricsEngine()
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="h"),
            "equity": np.linspace(10000, 10500, 100),
        })

        trades = pd.DataFrame({
            "side": ["BUY", "SELL", "BUY", "SELL"],
            "pnl": [100, -50, 200, -30],
            "fee": [1, 1, 1, 1],
            "units": [0.01, 0.01, 0.02, 0.02],
            "price": [50000, 49000, 51000, 48000],
        })

        metrics = engine.compute(equity, trades)
        assert metrics.total_trades == 4
        assert metrics.winning_trades == 2
        assert metrics.hit_rate == 0.5

    def test_sortino_ratio(self) -> None:
        engine = MetricsEngine()
        # Upward trending equity (positive skew)
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=500, freq="h"),
            "equity": 10000 + np.cumsum(np.random.randn(500) * 10 + 5),
        })

        metrics = engine.compute(equity)
        # Sortino should be higher than Sharpe for positively skewed returns
        assert metrics.sortino_ratio > 0

    def test_tail_risk(self) -> None:
        engine = MetricsEngine()
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=1000, freq="h"),
            "equity": 10000 + np.cumsum(np.random.randn(1000) * 50),
        })

        metrics = engine.compute(equity)
        assert metrics.var_95 < 0  # VaR should be negative (loss)
        assert metrics.cvar_95 < 0

    def test_long_short_decomposition(self) -> None:
        engine = MetricsEngine()
        equity = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="h"),
            "equity": np.linspace(10000, 10500, 100),
        })

        trades = pd.DataFrame({
            "side": ["BUY", "SELL", "BUY", "SELL"],
            "pnl": [100, -50, 200, -30],
        })

        metrics = engine.compute(equity, trades)
        assert metrics.long_return_pct != 0
        assert metrics.short_return_pct != 0
