"""Tests for M4.1b Risk Integration - Centralized Risk Checks Gate Every Trade Path."""

from datetime import datetime

import pandas as pd
import pytest
from baet.config.models import RiskConfig
from baet.risk.engine import RiskEngine
from baet.risk.integration import (
    create_risk_engine_from_config,
    evaluate_combined_signals,
    evaluate_strategy_signal,
    extract_risk_metadata,
    should_execute_trade,
    update_risk_engine_state,
)
from baet.risk.policy import RiskPolicy, StrategyRiskPolicy

# ========== Helper Functions ==========


def create_test_signal(action="BUY", size=0.1, strategy="test_strategy", symbol="BTCUSDT"):
    """Create a test signal dictionary."""
    return {
        "action": action,
        "target_position": 1.0 if action == "BUY" else (-1.0 if action == "SELL" else 0.0),
        "confidence": 0.8,
        "size_hint": size,
        "strategy_name": strategy,
        "symbol": symbol,
        "timestamp": datetime.now(),
    }


def create_risk_engine():
    """Create a RiskEngine with default policy."""
    policy = RiskPolicy()
    return RiskEngine(policy)


# ========== Test create_risk_engine_from_config ==========


def test_create_risk_engine_from_config():
    """Test creating RiskEngine from config."""
    config = RiskConfig()
    engine = create_risk_engine_from_config(config)

    assert engine is not None
    assert engine.policy is not None


# ========== Test evaluate_strategy_signal ==========


def test_evaluate_strategy_signal_approves_valid():
    """Test that valid signals are approved."""
    engine = create_risk_engine()
    signal = create_test_signal(action="BUY", size=0.05)  # Small size, should pass

    result = evaluate_strategy_signal(engine, signal)

    assert result is not None
    assert result["risk_approved"]
    assert result["action"] == "BUY"


def test_evaluate_strategy_signal_rejects_blacklisted():
    """Test that blacklisted strategies are rejected."""
    policy = RiskPolicy(strategy=StrategyRiskPolicy(blacklisted_strategies=["bad_strategy"]))
    engine = RiskEngine(policy)
    signal = create_test_signal(strategy="bad_strategy")

    result = evaluate_strategy_signal(engine, signal)

    assert result is None  # Rejected


def test_evaluate_strategy_signal_modifies_size():
    """Test that signal size can be modified."""
    engine = create_risk_engine()
    signal = create_test_signal(size=0.15)  # Exceeds default 0.10 max

    result = evaluate_strategy_signal(engine, signal)

    # Should be modified (reduced) not rejected
    assert result is not None
    assert result["size_hint"] <= 0.10


def test_evaluate_strategy_signal_with_regime():
    """Test signal evaluation with regime."""
    engine = create_risk_engine()
    signal = create_test_signal()

    from baet.core.models import RegimeLabel

    result = evaluate_strategy_signal(engine, signal, regime=RegimeLabel.TRENDING)

    assert result is not None
    assert result["risk_approved"]


# ========== Test evaluate_combined_signals ==========


def test_evaluate_combined_signals_filters_rejected():
    """Test that rejected signals are filtered out."""
    policy = RiskPolicy(strategy=StrategyRiskPolicy(blacklisted_strategies=["bad"]))
    engine = RiskEngine(policy)

    # Create DataFrame with one good and one bad signal
    good_signal = create_test_signal(strategy="good", size=0.05)
    bad_signal = create_test_signal(strategy="bad", size=0.05)

    df = pd.DataFrame([good_signal, bad_signal])

    result = evaluate_combined_signals(engine, df)

    # Only good signal should remain
    assert len(result) == 1
    assert result.iloc[0]["strategy_name"] == "good"


def test_evaluate_combined_signals_empty():
    """Test with empty DataFrame."""
    engine = create_risk_engine()

    empty_df = pd.DataFrame(
        columns=[
            "action",
            "target_position",
            "confidence",
            "size_hint",
            "strategy_name",
            "symbol",
            "timestamp",
        ]
    )

    result = evaluate_combined_signals(engine, empty_df)

    assert len(result) == 0


def test_evaluate_combined_signals_all_rejected():
    """Test when all signals are rejected."""
    policy = RiskPolicy(strategy=StrategyRiskPolicy(blacklisted_strategies=["all"]))
    engine = RiskEngine(policy)

    signals = [
        create_test_signal(strategy="all", size=0.05),
        create_test_signal(strategy="all", size=0.03),
    ]

    df = pd.DataFrame(signals)
    result = evaluate_combined_signals(engine, df)

    assert len(result) == 0


# ========== Test update_risk_engine_state ==========


def test_update_risk_engine_state():
    """Test updating portfolio state."""
    engine = create_risk_engine()

    positions = {"BTCUSDT": {"exposure": 1000.0}}

    update_risk_engine_state(engine=engine, equity=9500.0, positions=positions, daily_pnl=-100.0)

    assert engine.portfolio_state["total_equity"] == 9500.0
    assert engine.portfolio_state["total_exposure"] == 1000.0
    assert engine.portfolio_state["daily_pnl"] == -100.0


# ========== Test should_execute_trade ==========


def test_should_execute_trade_approved():
    """Test that approved trades should execute."""
    signal = create_test_signal()
    signal["risk_approved"] = True
    signal["action"] = "BUY"

    assert should_execute_trade(signal)


def test_should_execute_trade_rejected():
    """Test that rejected trades should not execute."""
    assert not should_execute_trade(None)  # None = rejected


def test_should_execute_trade_hold():
    """Test that HOLD action should not execute."""
    signal = create_test_signal()
    signal["risk_approved"] = True
    signal["action"] = "HOLD"

    assert not should_execute_trade(signal)


# ========== Test extract_risk_metadata ==========


def test_extract_risk_metadata_approved():
    """Test extracting metadata from approved signal."""
    signal = create_test_signal()
    signal["risk_approved"] = True
    signal["risk_reasons"] = ["All checks passed"]
    signal["risk_score"] = 0.0

    metadata = extract_risk_metadata(signal)

    assert metadata["risk_approved"]
    assert "All checks passed" in metadata["risk_reasons"]


def test_extract_risk_metadata_rejected():
    """Test extracting metadata from rejected signal."""
    metadata = extract_risk_metadata(None)  # None = rejected

    assert not metadata["risk_approved"]
    assert "rejected" in metadata["risk_reasons"][0].lower()


def test_extract_risk_metadata_with_adjustments():
    """Test metadata includes adjustments."""
    signal = create_test_signal()
    signal["risk_approved"] = True
    signal["action"] = "BUY"
    signal["risk_reasons"] = ["Size adjusted"]
    signal["risk_score"] = 0.3

    metadata = extract_risk_metadata(signal)

    assert metadata["action_original"] == "BUY"
    assert metadata["risk_score"] == 0.3


# ========== Test Ensemble Integration ==========


def test_ensemble_with_risk_engine():
    """Test that ensemble works with risk engine."""
    from baet.strategies.ensemble import EnsembleConfig, StaticEnsemble

    engine = create_risk_engine()
    config = EnsembleConfig(name="test_ensemble")
    ensemble = StaticEnsemble(config, risk_engine=engine)

    # Ensemble should have risk_engine
    assert ensemble.risk_engine is engine


def test_ensemble_without_risk_engine():
    """Test that ensemble works without risk engine (backward compatible)."""
    from baet.strategies.ensemble import EnsembleConfig, StaticEnsemble

    config = EnsembleConfig(name="test_ensemble")
    ensemble = StaticEnsemble(config)  # No risk engine

    # Should work without risk engine
    assert ensemble.risk_engine is None


# ========== Test Backtest Integration ==========


def test_backtest_with_risk_engine():
    """Test that backtest engine accepts risk engine."""
    from baet.execution.backtest import PortfolioBacktestEngine

    engine = create_risk_engine()
    config = RiskConfig()
    backtest = PortfolioBacktestEngine(config, risk_engine=engine)

    assert backtest.risk_engine is engine


def test_backtest_without_risk_engine():
    """Test that backtest works without risk engine (backward compatible)."""
    from baet.execution.backtest import PortfolioBacktestEngine

    config = RiskConfig()
    backtest = PortfolioBacktestEngine(config)  # No risk engine

    # Should work without risk engine
    assert backtest.risk_engine is None


# ========== Test Integration Without Risk Engine (Graceful Degradation) ==========


def test_integration_functions_handle_none_engine():
    """Test that integration functions handle None engine gracefully."""
    # These functions should not be called with None engine in practice,
    # but let's ensure they don't crash
    pass  # Placeholder - functions check for engine before calling


def test_signal_evaluation_requires_engine():
    """Test that signal evaluation requires engine."""
    # evaluate_strategy_signal requires engine as first param
    signal = create_test_signal()

    # Would need engine to actually evaluate
    # This test just documents the interface
    assert signal is not None


# ========== End-to-End Integration Test ==========


def test_full_integration_flow():
    """Test full integration flow: signal -> risk check -> decision."""
    engine = create_risk_engine()

    # Create multiple signals
    signals = [
        create_test_signal(action="BUY", size=0.05, strategy="strat_a"),
        create_test_signal(action="BUY", size=0.03, strategy="strat_b"),
        create_test_signal(action="SELL", size=0.02, strategy="strat_a"),
    ]

    # Evaluate each signal
    approved = []
    for signal in signals:
        result = evaluate_strategy_signal(engine, signal)
        if result is not None:
            approved.append(result)

    # All should be approved (small sizes, no drawdown)
    assert len(approved) == 3

    # Now simulate drawdown
    engine.portfolio_state["total_equity"] = 8000.0  # 20% drawdown
    engine.portfolio_state["peak_equity"] = 10000.0

    # Re-evaluate
    approved_after_dd = []
    for signal in signals:
        result = evaluate_strategy_signal(engine, signal)
        if result is not None:
            approved_after_dd.append(result)

    # All should be rejected now (drawdown exceeded)
    assert len(approved_after_dd) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
