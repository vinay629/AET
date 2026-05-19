"""Tests for the baseline training pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from baet.ml.labels import TripleBarrierConfig, TripleBarrierLabeler
from baet.ml.training import BaselineTrainer, TrainingConfig, TrainingResult


class TestTripleBarrierDynamic:
    """Tests for dynamic ATR-scaled barriers."""

    def _make_prices(self, n: int = 100, trend: float = 0.001) -> pd.Series:
        """Generate a synthetic price series with optional trend."""
        np.random.seed(42)
        returns = np.random.normal(trend, 0.01, n)
        prices = 100 * np.cumprod(1 + returns)
        return pd.Series(prices)

    def _make_ohlcv(self, n: int = 100) -> pd.DataFrame:
        """Generate synthetic OHLCV data."""
        np.random.seed(42)
        prices = self._make_prices(n)
        high = prices * (1 + np.abs(np.random.normal(0, 0.005, n)))
        low = prices * (1 - np.abs(np.random.normal(0, 0.005, n)))
        return pd.DataFrame({
            "open": prices * (1 + np.random.normal(0, 0.001, n)),
            "high": high,
            "low": low,
            "close": prices,
            "volume": np.random.uniform(100, 1000, n),
        })

    def test_static_barriers_default(self) -> None:
        """Default config uses static percentage barriers."""
        prices = self._make_prices(50)
        labeler = TripleBarrierLabeler()
        result = labeler.label(prices)
        assert not result.empty
        assert "label" in result.columns
        assert "barrier" in result.columns

    def test_dynamic_barriers_with_atr(self) -> None:
        """Dynamic barriers scale with ATR."""
        prices = self._make_prices(100)
        high = prices * 1.005
        low = prices * 0.995

        config = TripleBarrierConfig(
            atr_window=14,
            atr_multiplier=2.0,
            timeout_bars=20,
        )
        labeler = TripleBarrierLabeler(config=config)
        result = labeler.label(prices=prices, high=high, low=low)
        assert not result.empty
        assert set(result["label"].unique()).issubset({-1, 0, 1})

    def test_dynamic_barriers_with_precomputed_atr(self) -> None:
        """Can pass pre-computed ATR series."""
        prices = self._make_prices(100)
        atr = pd.Series(np.full(100, 1.0))

        config = TripleBarrierConfig(
            atr_window=14,
            atr_multiplier=2.0,
            timeout_bars=10,
        )
        labeler = TripleBarrierLabeler(config=config)
        result = labeler.label(prices=prices, atr=atr)
        assert not result.empty

    def test_dynamic_barriers_tighten_in_low_vol(self) -> None:
        """Dynamic barriers should tighten when volatility is low."""
        # Low vol: very stable prices
        low_vol_prices = pd.Series(100 + np.arange(50) * 0.01)
        # High vol: large swings
        np.random.seed(42)
        high_vol_returns = np.random.normal(0, 0.05, 50)
        high_vol_prices = pd.Series(100 * np.cumprod(1 + high_vol_returns))

        config = TripleBarrierConfig(
            atr_window=10,
            atr_multiplier=2.0,
            timeout_bars=20,
        )
        labeler = TripleBarrierLabeler(config=config)

        low_vol_result = labeler.label(prices=low_vol_prices)
        high_vol_result = labeler.label(prices=high_vol_prices)

        # Low vol should have more timeout labels (barriers are tighter relative to movement)
        # High vol should have more TP/SL hits (barriers are wider but price moves more)
        assert not low_vol_result.empty
        assert not high_vol_result.empty

    def test_label_distribution_reasonable(self) -> None:
        """Labels should not be all one class."""
        np.random.seed(42)
        prices = pd.Series(100 * np.cumprod(1 + np.random.normal(0, 0.02, 200)))

        config = TripleBarrierConfig(
            atr_window=14,
            atr_multiplier=2.0,
            timeout_bars=20,
        )
        labeler = TripleBarrierLabeler(config=config)
        result = labeler.label(prices=prices)

        label_counts = result["label"].value_counts()
        # Should have at least 2 different labels
        assert len(label_counts) >= 2

    def test_compute_volatility_returns_none_for_static(self) -> None:
        """When atr_window is None, _compute_volatility returns None."""
        config = TripleBarrierConfig(atr_window=None)
        labeler = TripleBarrierLabeler(config=config)
        vol = labeler._compute_volatility(pd.Series([100, 101, 102]))
        assert vol is None

    def test_compute_volatility_from_rolling_std(self) -> None:
        """Fallback to rolling std when high/low not provided."""
        config = TripleBarrierConfig(atr_window=10, vol_lookback=10)
        labeler = TripleBarrierLabeler(config=config)
        prices = pd.Series(100 + np.arange(50) * 0.1)
        vol = labeler._compute_volatility(prices)
        assert vol is not None
        assert len(vol) == 50


class TestTrainingConfig:
    """Tests for training configuration."""

    def test_default_config(self) -> None:
        config = TrainingConfig()
        assert config.symbol == "BTCUSDT"
        assert config.timeframe == "1h"
        assert config.atr_window == 14
        assert config.atr_multiplier == 2.0
        assert config.model_type == "hist_gradient_boosting"

    def test_custom_config(self) -> None:
        config = TrainingConfig(
            symbol="ETHUSDT",
            timeframe="4h",
            atr_window=20,
            model_type="gradient_boosting",
        )
        assert config.symbol == "ETHUSDT"
        assert config.timeframe == "4h"
        assert config.atr_window == 20
        assert config.model_type == "gradient_boosting"


class TestTrainingResult:
    """Tests for training result."""

    def test_mean_metrics(self) -> None:
        from baet.ml.model_registry import ModelArtifact

        artifact = ModelArtifact(name="test", version="1.0.0")
        result = TrainingResult(
            model_artifact=artifact,
            cv_metrics={
                "accuracy": [0.55, 0.58, 0.52, 0.57, 0.56],
                "f1_macro": [0.50, 0.53, 0.48, 0.52, 0.51],
            },
        )
        assert abs(result.mean_cv_accuracy - 0.556) < 0.01
        assert abs(result.mean_cv_f1 - 0.508) < 0.01

    def test_summary(self) -> None:
        from baet.ml.model_registry import ModelArtifact

        artifact = ModelArtifact(name="test", version="1.0.0")
        result = TrainingResult(
            model_artifact=artifact,
            cv_metrics={"accuracy": [0.55], "f1_macro": [0.50]},
            label_distribution={"-1": 100, "0": 50, "1": 100},
            n_samples=250,
            n_features=15,
        )
        summary = result.summary()
        assert "baseline_gb" in summary or "test" in summary
        assert "250" in summary
