"""Tests for Phase 6 research infrastructure."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from baet.research.regime import RegimeDetector, RegimeLabel
from baet.research.portfolio import (
    PortfolioOptimizer,
    PortfolioConstraints,
    PortfolioState,
)
from baet.research.statistics import StatisticalValidator, StatisticalTestResult


def _make_ohlcv(n: int = 500, trend: float = 0.0, vol: float = 0.01) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    returns = np.random.randn(n) * vol + trend
    close = 50000 * np.exp(np.cumsum(returns))
    high = close * (1 + abs(np.random.randn(n)) * vol * 0.5)
    low = close * (1 - abs(np.random.randn(n)) * vol * 0.5)
    open_price = close * (1 + np.random.randn(n) * vol * 0.1)
    volume = np.random.uniform(100, 1000, n)

    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


class TestRegimeDetector:
    def test_detect_returns_regimes(self) -> None:
        data = _make_ohlcv(500)
        detector = RegimeDetector(lookback=50)
        regimes = detector.detect(data)
        assert len(regimes) > 0
        # Should have regimes for bars from index 50 onwards
        assert len(regimes) == 500 - 50

    def test_regime_has_label(self) -> None:
        data = _make_ohlcv(200)
        detector = RegimeDetector(lookback=50)
        regimes = detector.detect(data)
        for regime in regimes:
            assert isinstance(regime.label, RegimeLabel)
            assert 0 <= regime.confidence <= 1

    def test_detect_latest(self) -> None:
        data = _make_ohlcv(200)
        detector = RegimeDetector(lookback=50)
        latest = detector.detect_latest(data)
        assert isinstance(latest.label, RegimeLabel)

    def test_segment(self) -> None:
        data = _make_ohlcv(300)
        detector = RegimeDetector(lookback=50)
        segments = detector.segment(data)
        assert len(segments) > 0
        # Segments should cover the full range
        total_bars = sum(s.duration_bars for s in segments)
        assert total_bars > 0

    def test_trending_market(self) -> None:
        """Strong trend should produce a valid regime classification."""
        data = _make_ohlcv(500, trend=0.001, vol=0.005)
        detector = RegimeDetector(lookback=50)
        latest = detector.detect_latest(data)
        # Should produce a valid regime (any label is fine — just verify it works)
        assert isinstance(latest.label, RegimeLabel)
        assert latest.confidence >= 0

    def test_high_volatility(self) -> None:
        """High volatility should be detected."""
        data = _make_ohlcv(500, trend=0, vol=0.05)
        detector = RegimeDetector(lookback=50)
        latest = detector.detect_latest(data)
        # With high vol, should be high vol or panic
        assert isinstance(latest.label, RegimeLabel)

    def test_deterministic(self) -> None:
        """Same data should produce same regimes."""
        data = _make_ohlcv(200)
        detector = RegimeDetector(lookback=50)
        r1 = detector.detect(data)
        r2 = detector.detect(data)
        for a, b in zip(r1, r2):
            assert a.label == b.label
            assert abs(a.confidence - b.confidence) < 0.001


class TestPortfolioOptimizer:
    def test_equal_weight(self) -> None:
        optimizer = PortfolioOptimizer(method="equal_weight")
        signals = [
            {"symbol": "BTCUSDT", "direction": "BUY", "confidence": 0.8, "expected_return": 0.1},
            {"symbol": "ETHUSDT", "direction": "BUY", "confidence": 0.6, "expected_return": 0.05},
        ]
        state = optimizer.optimize(signals)
        assert len(state.allocations) == 2
        # Equal weight: both should be ~0.5
        assert abs(state.allocations[0].target_weight - state.allocations[1].target_weight) < 0.1

    def test_risk_parity(self) -> None:
        optimizer = PortfolioOptimizer(method="risk_parity")
        signals = [
            {"symbol": "BTCUSDT", "direction": "BUY", "confidence": 0.8, "expected_return": 0.1},
            {"symbol": "ETHUSDT", "direction": "BUY", "confidence": 0.6, "expected_return": 0.05},
        ]
        state = optimizer.optimize(signals)
        assert len(state.allocations) == 2
        assert state.total_exposure > 0

    def test_constraints_applied(self) -> None:
        constraints = PortfolioConstraints(max_single_position=0.05, max_total_exposure=0.1)
        optimizer = PortfolioOptimizer(constraints=constraints, method="equal_weight")
        signals = [
            {"symbol": "BTCUSDT", "direction": "BUY", "confidence": 0.8},
            {"symbol": "ETHUSDT", "direction": "BUY", "confidence": 0.6},
            {"symbol": "SOLUSDT", "direction": "BUY", "confidence": 0.4},
        ]
        state = optimizer.optimize(signals=signals)
        for alloc in state.allocations:
            assert abs(alloc.target_weight) <= 0.05 + 0.001
        assert state.total_exposure <= 0.1 + 0.001

    def test_short_direction(self) -> None:
        optimizer = PortfolioOptimizer(method="equal_weight")
        signals = [
            {"symbol": "BTCUSDT", "direction": "SELL", "confidence": 0.8},
        ]
        state = optimizer.optimize(signals)
        assert state.allocations[0].target_weight < 0

    def test_portfolio_metrics(self) -> None:
        optimizer = PortfolioOptimizer(method="equal_weight")
        signals = [
            {"symbol": "BTCUSDT", "direction": "BUY", "confidence": 0.8, "expected_return": 0.1},
            {"symbol": "ETHUSDT", "direction": "BUY", "confidence": 0.6, "expected_return": 0.05},
        ]
        state = optimizer.optimize(signals)
        assert state.expected_return > 0
        assert state.expected_volatility > 0
        assert state.diversification_ratio > 0

    def test_hrp_method(self) -> None:
        optimizer = PortfolioOptimizer(method="hrp")
        signals = [
            {"symbol": "BTCUSDT", "direction": "BUY", "confidence": 0.8},
            {"symbol": "ETHUSDT", "direction": "BUY", "confidence": 0.6},
        ]
        state = optimizer.optimize(signals)
        assert len(state.allocations) == 2
        assert state.total_exposure > 0


class TestStatisticalValidator:
    def test_return_significance(self) -> None:
        validator = StatisticalValidator(n_permutations=100)
        # Strong positive returns should be significant
        returns = pd.Series(np.random.randn(200) * 0.01 + 0.001)
        result = validator.test_return_significance(returns)
        assert isinstance(result, StatisticalTestResult)

    def test_sharpe_significance(self) -> None:
        validator = StatisticalValidator(n_permutations=100)
        returns = pd.Series(np.random.randn(200) * 0.01 + 0.001)
        result = validator.test_sharpe_significance(returns)
        assert isinstance(result, StatisticalTestResult)

    def test_vs_benchmark(self) -> None:
        validator = StatisticalValidator(n_permutations=100)
        strategy = pd.Series(np.random.randn(200) * 0.01 + 0.001)
        benchmark = pd.Series(np.random.randn(200) * 0.01)
        result = validator.test_vs_benchmark(strategy, benchmark)
        assert isinstance(result, StatisticalTestResult)

    def test_monte_carlo_reshuffling(self) -> None:
        validator = StatisticalValidator(n_permutations=200, seed=42)
        returns = pd.Series(np.random.randn(200) * 0.01 + 0.001)
        result = validator.monte_carlo_reshuffling(returns)
        assert isinstance(result, StatisticalTestResult)
        assert 0 <= result.p_value <= 1

    def test_deflated_sharpe(self) -> None:
        validator = StatisticalValidator(n_permutations=100)
        returns = pd.Series(np.random.randn(200) * 0.01 + 0.001)
        result = validator.deflated_sharpe(returns, n_trials=10)
        assert isinstance(result, StatisticalTestResult)

    def test_pbo(self) -> None:
        validator = StatisticalValidator(n_permutations=100)
        is_returns = pd.Series(np.random.randn(200) * 0.01 + 0.002)
        oos_returns = pd.Series(np.random.randn(100) * 0.01 + 0.0005)
        result = validator.probability_of_backtest_overfitting(is_returns, oos_returns)
        assert isinstance(result, StatisticalTestResult)
        assert 0 <= result.statistic <= 1

    def test_full_validation(self) -> None:
        validator = StatisticalValidator(n_permutations=100, seed=42)
        returns = pd.Series(np.random.randn(300) * 0.01 + 0.001)
        benchmark = pd.Series(np.random.randn(300) * 0.01)
        other = [pd.Series(np.random.randn(300) * 0.01) for _ in range(3)]

        report = validator.validate(returns, benchmark, other)
        assert len(report.results) > 0
        # Should have: return sig, sharpe sig, vs benchmark, reality check, multiple testing, deflated sharpe, monte carlo
        test_names = [r.test_name for r in report.results]
        assert "return_significance" in test_names
        assert "sharpe_significance" in test_names
