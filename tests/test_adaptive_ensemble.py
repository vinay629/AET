"""Tests for adaptive ensemble with performance-based weight updates."""

import numpy as np
import pandas as pd

from baet.strategies.adaptive_ensemble import AdaptiveEnsemble, PerformanceTracker
from baet.strategies.ensemble import EnsembleConfig


def create_sample_returns(n_periods: int = 30) -> pd.DataFrame:
    """Create sample market returns for testing."""
    dates = pd.date_range("2024-01-01", periods=n_periods, freq="D")
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, n_periods)

    return pd.DataFrame({"timestamp": dates, "return": returns})


def create_strategy_signals(
    strategy_name: str, n_periods: int = 30, action_pattern: str = "buy"
) -> pd.DataFrame:
    """Create sample strategy signals."""
    dates = pd.date_range("2024-01-01", periods=n_periods, freq="D")

    signals = []
    for i, date in enumerate(dates):
        if action_pattern == "buy":
            action = "BUY"
            target = 1.0
        elif action_pattern == "sell":
            action = "SELL"
            target = -1.0
        else:  # alternating
            action = "BUY" if i % 2 == 0 else "SELL"
            target = 1.0 if action == "BUY" else -1.0

        signals.append(
            {
                "timestamp": date,
                "symbol": "BTCUSDT",
                "timeframe": "1d",
                "action": action,
                "target_position": target,
                "confidence": 0.7,
                "size_hint": 0.1,
                "strategy_name": strategy_name,
                "reason": f"{strategy_name} signal",
            }
        )

    return pd.DataFrame(signals)


def test_performance_tracker_initialization():
    """Test PerformanceTracker initializes correctly."""
    tracker = PerformanceTracker(window=10)

    assert tracker.window == 10
    assert len(tracker.metrics) == 0


def test_performance_tracker_update():
    """Test that performance tracker updates correctly."""
    tracker = PerformanceTracker(window=20)

    signals = create_strategy_signals("test_strategy", 10)
    returns = create_sample_returns(10)

    tracker.update("test_strategy", signals, returns)

    assert "test_strategy" in tracker.metrics
    assert len(tracker.metrics["test_strategy"]) == 10
    assert "return" in tracker.metrics["test_strategy"].columns
    assert "cumulative_return" in tracker.metrics["test_strategy"].columns


def test_performance_tracker_sharpe():
    """Test Sharpe ratio calculation."""
    tracker = PerformanceTracker(window=30)

    # Create signals and returns
    signals = create_strategy_signals("strategy_a", 30)
    returns = create_sample_returns(30)

    # Initial Sharpe should be 0 (not enough data or just initialized)
    tracker.get_sharpe("strategy_a")

    # Update tracking
    tracker.update("strategy_a", signals, returns)

    sharpe_after = tracker.get_sharpe("strategy_a")
    # Sharpe should be a finite number
    assert np.isfinite(sharpe_after)


def test_performance_tracker_sortino():
    """Test Sortino ratio calculation."""
    tracker = PerformanceTracker(window=30)

    signals = create_strategy_signals("strategy_b", 30)
    returns = create_sample_returns(30)

    tracker.update("strategy_b", signals, returns)

    sortino = tracker.get_sortino("strategy_b")
    assert np.isfinite(sortino)


def test_adaptive_ensemble_initialization():
    """Test AdaptiveEnsemble initializes correctly."""
    config = EnsembleConfig(name="adaptive_test")
    ensemble = AdaptiveEnsemble(config, performance_window=10)

    assert ensemble.config.name == "adaptive_test"
    assert ensemble.performance_tracker.window == 10
    assert len(ensemble.historical_weights) == 0


def test_adaptive_ensemble_update_weights():
    """Test that adaptive ensemble updates weights based on performance."""
    config = EnsembleConfig(name="adaptive_test")
    ensemble = AdaptiveEnsemble(config, performance_window=20)

    # Create two strategies with different performance
    signals_a = create_strategy_signals("strategy_a", 30, "buy")
    signals_b = create_strategy_signals("strategy_b", 30, "sell")

    # Create returns (positive for buy strategy, negative for sell)
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    returns = pd.DataFrame(
        {
            "timestamp": dates,
            "return": np.random.normal(0.001, 0.01, 30),  # Positive bias
        }
    )

    strategy_signals = {"strategy_a": signals_a, "strategy_b": signals_b}

    # Update weights
    weights = ensemble.update_weights(strategy_signals, returns)

    assert "strategy_a" in weights
    assert "strategy_b" in weights
    # Weights should sum to approximately 1
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_adaptive_ensemble_combine_signals():
    """Test adaptive ensemble signal combination."""
    config = EnsembleConfig(name="adaptive_test")
    ensemble = AdaptiveEnsemble(config, performance_window=20)

    signals_a = create_strategy_signals("strategy_a", 10, "buy")
    signals_b = create_strategy_signals("strategy_b", 10, "sell")

    returns = create_sample_returns(10)

    strategy_signals = {"strategy_a": signals_a, "strategy_b": signals_b}

    # Combine with adaptive weights
    combined = ensemble.combine_signals_adaptive(strategy_signals, returns)

    assert len(combined) == 20  # Both strategies
    assert "strategy_name" in combined.columns


def test_adaptive_ensemble_weight_history():
    """Test that weight history is tracked."""
    config = EnsembleConfig(name="adaptive_test")
    ensemble = AdaptiveEnsemble(config, performance_window=20)

    signals_a = create_strategy_signals("strategy_a", 30, "buy")
    signals_b = create_strategy_signals("strategy_b", 30, "sell")
    returns = create_sample_returns(30)

    strategy_signals = {"strategy_a": signals_a, "strategy_b": signals_b}

    # Update weights multiple times
    for _ in range(3):
        ensemble.update_weights(strategy_signals, returns)

    history = ensemble.get_weight_history()

    assert len(history) == 3  # Three updates
    assert "timestamp" in history.columns
    assert "strategy_a" in history.columns
    assert "strategy_b" in history.columns


def test_adaptive_ensemble_deterministic():
    """Test that weight updates are deterministic."""
    config = EnsembleConfig(name="adaptive_test")
    ensemble1 = AdaptiveEnsemble(config, performance_window=20)
    ensemble2 = AdaptiveEnsemble(config, performance_window=20)

    signals_a = create_strategy_signals("strategy_a", 30, "buy")
    signals_b = create_strategy_signals("strategy_b", 30, "sell")
    returns = create_sample_returns(30)

    strategy_signals = {"strategy_a": signals_a, "strategy_b": signals_b}

    # Both ensembles should produce same weights with same input
    weights1 = ensemble1.update_weights(strategy_signals.copy(), returns.copy())
    weights2 = ensemble2.update_weights(strategy_signals.copy(), returns.copy())

    assert abs(weights1["strategy_a"] - weights2["strategy_a"]) < 0.001
    assert abs(weights1["strategy_b"] - weights2["strategy_b"]) < 0.001


def test_adaptive_ensemble_end_to_end():
    """Test full end-to-end adaptive ensemble workflow."""
    config = EnsembleConfig(name="full_adaptive_test")
    ensemble = AdaptiveEnsemble(config, performance_window=20)

    # Simulate 60 periods of data
    n_periods = 60

    # Strategy A: trend following (does well in trending markets)
    signals_a = create_strategy_signals("strategy_a", n_periods, "buy")

    # Strategy B: mean reversion (does well in ranging markets)
    signals_b = create_strategy_signals("strategy_b", n_periods, "sell")

    # Create returns with some trend
    dates = pd.date_range("2024-01-01", periods=n_periods, freq="D")
    trend = np.linspace(0, 0.5, n_periods)  # Upward trend
    noise = np.random.normal(0, 0.02, n_periods)
    returns_values = np.diff(trend) / trend[:-1] + noise[1:] if len(trend) > 1 else noise
    returns_values = np.insert(returns_values, 0, 0)  # First return is 0

    returns = pd.DataFrame({"timestamp": dates, "return": returns_values})

    strategy_signals = {"strategy_a": signals_a, "strategy_b": signals_b}

    # Run adaptive ensemble
    combined = ensemble.combine_signals_adaptive(strategy_signals, returns)

    assert len(combined) == n_periods * 2

    # Make decisions
    decisions = ensemble.make_decisions(combined)

    assert len(decisions) == n_periods
    assert all(decisions["strategy_name"] == "full_adaptive_test")

    # Check weight history was recorded
    history = ensemble.get_weight_history()
    assert len(history) > 0
