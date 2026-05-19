"""Tests for derivatives feature pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from baet.config.models import DerivativesConfig
from baet.data.features import DerivativesFeatureBuilder


@pytest.fixture
def sample_candles() -> pd.DataFrame:
    """Generate sample OHLCV candles."""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    prices = 100 * np.cumprod(1 + np.random.normal(0.001, 0.01, n))
    return pd.DataFrame({
        "close_time": dates,
        "open": prices * (1 + np.random.normal(0, 0.002, n)),
        "high": prices * (1 + np.abs(np.random.normal(0, 0.005, n))),
        "low": prices * (1 - np.abs(np.random.normal(0, 0.005, n))),
        "close": prices,
        "volume": np.random.uniform(100, 1000, n),
    })


@pytest.fixture
def sample_oi() -> pd.DataFrame:
    """Generate sample open interest data."""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    oi = 10000 + np.cumsum(np.random.normal(0, 50, n))
    return pd.DataFrame({
        "timestamp": dates,
        "open_interest": oi,
    })


@pytest.fixture
def sample_funding() -> pd.DataFrame:
    """Generate sample funding rate data."""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    fr = np.random.normal(0.0001, 0.0005, n)
    return pd.DataFrame({
        "timestamp": dates,
        "funding_rate": fr,
    })


@pytest.fixture
def sample_liquidations() -> pd.DataFrame:
    """Generate sample liquidation data."""
    np.random.seed(42)
    n = 50
    dates = pd.date_range("2026-01-01", periods=n, freq="2h", tz="UTC")
    sides = np.random.choice(["BUY", "SELL"], n)
    return pd.DataFrame({
        "timestamp": dates,
        "side": sides,
        "qty": np.random.uniform(0.1, 10.0, n),
    })


class TestDerivativesConfig:
    """Tests for derivatives configuration."""

    def test_default_config(self) -> None:
        config = DerivativesConfig()
        assert config.enabled is True
        assert config.oi_change_windows == [1, 3, 6]
        assert config.fr_zscore_window == 120
        assert config.fr_extreme_threshold == 2.0
        assert config.liq_lookback_window == 24
        assert config.liq_spike_threshold == 3.0

    def test_custom_config(self) -> None:
        config = DerivativesConfig(
            oi_change_windows=[1, 5],
            fr_zscore_window=60,
            liq_lookback_window=12,
        )
        assert config.oi_change_windows == [1, 5]
        assert config.fr_zscore_window == 60
        assert config.liq_lookback_window == 12


class TestOIFeatures:
    """Tests for open interest feature engineering."""

    def test_oi_change_computed(self, sample_candles, sample_oi) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_oi_features(sample_candles, sample_oi)
        assert "oi_change_1" in result.columns
        assert "oi_change_3" in result.columns
        assert "oi_change_6" in result.columns

    def test_oi_change_values(self, sample_candles, sample_oi) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_oi_features(sample_candles, sample_oi)
        # First value should be NaN (no previous OI)
        assert pd.isna(result["oi_change_1"].iloc[0])
        # Subsequent values should be finite
        valid = result["oi_change_1"].dropna()
        assert np.isfinite(valid).all()

    def test_oi_price_divergence(self, sample_candles, sample_oi) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_oi_features(sample_candles, sample_oi)
        assert "oi_price_divergence" in result.columns
        # Correlation should be between -1 and 1
        valid = result["oi_price_divergence"].dropna()
        assert (valid >= -1.1).all() and (valid <= 1.1).all()

    def test_oi_price_signal(self, sample_candles, sample_oi) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_oi_features(sample_candles, sample_oi)
        assert "oi_price_signal" in result.columns
        valid_signals = result["oi_price_signal"].dropna()
        expected = {"aggressive_long", "short_adding", "short_covering", "long_liquidating", "neutral"}
        assert set(valid_signals.unique()).issubset(expected)

    def test_oi_merge_preserves_candles(self, sample_candles, sample_oi) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_oi_features(sample_candles, sample_oi)
        assert len(result) == len(sample_candles)
        assert "close" in result.columns
        assert "volume" in result.columns


class TestFundingRateFeatures:
    """Tests for funding rate feature engineering."""

    def test_funding_rate_merged(self, sample_candles, sample_funding) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_funding_rate_features(sample_candles, sample_funding)
        assert "funding_rate" in result.columns

    def test_fr_zscore_computed(self, sample_candles, sample_funding) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_funding_rate_features(sample_candles, sample_funding)
        assert "fr_zscore" in result.columns
        # Z-score should be roughly in [-3, 3] for normal data
        valid = result["fr_zscore"].dropna()
        assert (valid.abs() < 10).all()  # Very loose bound

    def test_fr_extreme_flag(self, sample_candles, sample_funding) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_funding_rate_features(sample_candles, sample_funding)
        assert "fr_extreme" in result.columns
        assert set(result["fr_extreme"].dropna().unique()).issubset({0, 1})

    def test_fr_trend(self, sample_candles, sample_funding) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_funding_rate_features(sample_candles, sample_funding)
        assert "fr_trend" in result.columns
        valid = result["fr_trend"].dropna()
        assert set(valid.unique()).issubset({-1, 0, 1})


class TestLiquidationFeatures:
    """Tests for liquidation feature engineering."""

    def test_liquidation_volumes(self, sample_candles, sample_liquidations) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_liquidation_features(sample_candles, sample_liquidations)
        assert "liq_long_volume" in result.columns
        assert "liq_short_volume" in result.columns

    def test_liq_ratio(self, sample_candles, sample_liquidations) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_liquidation_features(sample_candles, sample_liquidations)
        assert "liq_ratio" in result.columns

    def test_liq_spike(self, sample_candles, sample_liquidations) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_liquidation_features(sample_candles, sample_liquidations)
        assert "liq_spike" in result.columns
        assert set(result["liq_spike"].dropna().unique()).issubset({0, 1})

    def test_liq_imbalance(self, sample_candles, sample_liquidations) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.add_liquidation_features(sample_candles, sample_liquidations)
        assert "liq_imbalance" in result.columns

    def test_no_liquidations(self, sample_candles) -> None:
        """Empty liquidation data should not crash."""
        builder = DerivativesFeatureBuilder()
        empty_liq = pd.DataFrame(columns=["timestamp", "side", "qty"])
        result = builder.add_liquidation_features(sample_candles, empty_liq)
        assert "liq_long_volume" in result.columns
        assert (result["liq_long_volume"] == 0).all()


class TestDerivativesBuild:
    """Tests for the combined build method."""

    def test_build_all(
        self, sample_candles, sample_oi, sample_funding, sample_liquidations
    ) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.build(
            candles=sample_candles,
            open_interest=sample_oi,
            funding_rates=sample_funding,
            liquidations=sample_liquidations,
        )
        # Should have all derivative feature columns
        assert "oi_change_1" in result.columns
        assert "fr_zscore" in result.columns
        assert "liq_ratio" in result.columns
        # Should preserve original candle columns
        assert "close" in result.columns
        assert "volume" in result.columns
        assert len(result) == len(sample_candles)

    def test_build_oi_only(self, sample_candles, sample_oi) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.build(candles=sample_candles, open_interest=sample_oi)
        assert "oi_change_1" in result.columns
        assert "fr_zscore" not in result.columns

    def test_build_no_derivatives(self, sample_candles) -> None:
        builder = DerivativesFeatureBuilder()
        result = builder.build(candles=sample_candles)
        assert len(result) == len(sample_candles)
        assert "close" in result.columns
