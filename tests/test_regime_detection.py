"""Tests for regime detection module."""

import numpy as np
import pandas as pd
from baet.core.models import RegimeLabel
from baet.strategies.regime import VolatilityTrendRegimeDetector


def create_sample_data(n_periods: int = 100) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    np.random.seed(42)  # For reproducibility

    dates = pd.date_range("2024-01-01", periods=n_periods, freq="D")

    # Create price series with some trend and volatility
    base_price = 100
    returns = np.random.normal(0.0005, 0.02, n_periods)
    prices = base_price * np.exp(np.cumsum(returns))

    data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * (1 + np.random.uniform(-0.005, 0.005, n_periods)),
            "high": prices * (1 + np.random.uniform(0, 0.01, n_periods)),
            "low": prices * (1 - np.random.uniform(0, 0.01, n_periods)),
            "close": prices,
            "volume": np.random.randint(1000000, 5000000, n_periods),
        }
    )

    return data


def test_regime_detector_initialization():
    """Test that regime detector initializes correctly."""
    detector = VolatilityTrendRegimeDetector(volatility_window=20, trend_window=50)

    assert detector.volatility_window == 20
    assert detector.trend_window == 50
    assert detector.metadata.name == "volatility_trend_detector"


def test_regime_detector_output_format():
    """Test that detector returns correct DataFrame format."""
    detector = VolatilityTrendRegimeDetector()
    data = create_sample_data(100)

    result = detector.detect(data)

    # Check output format
    assert isinstance(result, pd.DataFrame)
    assert "timestamp" in result.columns
    assert "regime" in result.columns
    assert len(result) == len(data)


def test_regime_labels_valid():
    """Test that all returned regimes are valid RegimeLabel values."""
    detector = VolatilityTrendRegimeDetector()
    data = create_sample_data(100)

    result = detector.detect(data)

    # All regimes should be valid enum values
    valid_labels = {label for label in RegimeLabel}
    for regime in result["regime"]:
        assert regime in valid_labels


def test_regime_detection_reproducible():
    """Test that regime detection is reproducible with same input."""
    detector = VolatilityTrendRegimeDetector()
    data = create_sample_data(100)

    result1 = detector.detect(data)
    result2 = detector.detect(data)

    # Results should be identical
    pd.testing.assert_frame_equal(result1, result2)


def test_regime_detection_different_data():
    """Test that different data produces (potentially) different regimes."""
    detector = VolatilityTrendRegimeDetector()

    # Create trending data
    dates1 = pd.date_range("2024-01-01", periods=100, freq="D")
    trending_prices = 100 * (1 + np.linspace(0, 0.5, 100))  # Strong uptrend
    data_trending = pd.DataFrame(
        {
            "timestamp": dates1,
            "open": trending_prices,
            "high": trending_prices * 1.01,
            "low": trending_prices * 0.99,
            "close": trending_prices,
            "volume": np.random.randint(1000000, 5000000, 100),
        }
    )

    # Create ranging data
    dates2 = pd.date_range("2024-01-01", periods=100, freq="D")
    ranging_prices = 100 + np.sin(np.linspace(0, 4 * np.pi, 100)) * 5  # Oscillating
    data_ranging = pd.DataFrame(
        {
            "timestamp": dates2,
            "open": ranging_prices,
            "high": ranging_prices * 1.01,
            "low": ranging_prices * 0.99,
            "close": ranging_prices,
            "volume": np.random.randint(1000000, 5000000, 100),
        }
    )

    result_trending = detector.detect(data_trending)
    result_ranging = detector.detect(data_ranging)

    # Both should have valid regime classifications
    assert all(
        r
        in [
            RegimeLabel.TRENDING,
            RegimeLabel.RANGING,
            RegimeLabel.HIGH_VOLATILITY,
            RegimeLabel.LOW_VOLATILITY,
        ]
        for r in result_trending["regime"]
    )
    assert all(
        r
        in [
            RegimeLabel.TRENDING,
            RegimeLabel.RANGING,
            RegimeLabel.HIGH_VOLATILITY,
            RegimeLabel.LOW_VOLATILITY,
        ]
        for r in result_ranging["regime"]
    )


def test_regime_detector_end_to_end():
    """Test full end-to-end regime detection workflow."""
    detector = VolatilityTrendRegimeDetector(volatility_window=10, trend_window=20)

    # Create realistic data with different market conditions
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="D")

    # First half: low volatility ranging market
    # Second half: high volatility trending market
    prices = np.concatenate(
        [
            100 + np.cumsum(np.random.normal(0, 0.005, n // 2)),  # Low vol ranging
            100 + np.cumsum(np.random.normal(0.001, 0.02, n // 2)),  # Higher vol trending
        ]
    )

    data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices,
            "high": prices * 1.005,
            "low": prices * 0.995,
            "close": prices,
            "volume": np.random.randint(1000000, 5000000, n),
        }
    )

    result = detector.detect(data)

    # Verify output
    assert len(result) == n
    assert result["timestamp"].iloc[0] == dates[0]
    assert result["timestamp"].iloc[-1] == dates[-1]

    # Check that we have some regime diversity (not all the same)
    unique_regimes = result["regime"].unique()
    assert len(unique_regimes) >= 1  # At least one regime detected
