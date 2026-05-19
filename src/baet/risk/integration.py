"""Integration helpers to gate every trade path with centralized risk checks."""

from __future__ import annotations

import pandas as pd

from baet.config.models import RiskConfig
from baet.core.enums import RegimeLabel
from baet.risk.engine import RiskEngine


def create_risk_engine_from_config(config: RiskConfig) -> RiskEngine:
    """
    Create a RiskEngine instance from application config.

    Args:
        config: RiskConfig from application settings

    Returns:
        Configured RiskEngine instance
    """
    return RiskEngine(config.policy)


def evaluate_strategy_signal(
    engine: RiskEngine,
    signal: dict[str, object],
    regime: RegimeLabel | None = None,
) -> dict[str, object] | None:
    """
    Evaluate a single strategy signal through risk checks.

    Args:
        engine: RiskEngine instance
        signal: Signal dictionary with keys like action, target_position, etc.
        regime: Optional market regime for regime-based risk adjustments

    Returns:
        Modified signal dictionary if approved, None if rejected
    """
    result = engine.evaluate_signal(signal, regime)

    if not result.approved:
        # Signal rejected - return None
        return None

    # Return modified signal
    modified_signal = signal.copy()
    modified_signal["action"] = result.adjusted_action
    if result.adjusted_size is not None:
        modified_signal["size_hint"] = result.adjusted_size
    modified_signal["risk_reasons"] = result.reasons
    modified_signal["risk_score"] = result.risk_score
    modified_signal["risk_approved"] = True

    return modified_signal


def evaluate_combined_signals(
    engine: RiskEngine,
    combined_signals: pd.DataFrame,
    regime: RegimeLabel | None = None,
) -> pd.DataFrame:
    """
    Evaluate a DataFrame of combined signals through risk checks.

    Args:
        engine: RiskEngine instance
        combined_signals: DataFrame with signal columns
        regime: Optional market regime

    Returns:
        DataFrame with only approved/modified signals
    """
    approved_signals = []

    for _, signal_row in combined_signals.iterrows():
        signal_dict = signal_row.to_dict()
        result = evaluate_strategy_signal(engine, signal_dict, regime)
        if result is not None:
            approved_signals.append(result)

    if not approved_signals:
        return pd.DataFrame(columns=combined_signals.columns)

    return pd.DataFrame(approved_signals)


def update_risk_engine_state(
    engine: RiskEngine,
    equity: float,
    positions: dict,
    daily_pnl: float,
) -> None:
    """
    Update RiskEngine portfolio state for accurate risk calculations.

    Args:
        engine: RiskEngine instance
        equity: Current total equity
        positions: Dictionary of current positions
        daily_pnl: Daily P&L
    """
    engine.update_portfolio_state(equity=equity, positions=positions, daily_pnl=daily_pnl)


def should_execute_trade(risk_result: dict[str, object] | None) -> bool:
    """
    Determine if a trade should be executed based on risk check result.

    Args:
        risk_result: Result from evaluate_strategy_signal(), or None if rejected

    Returns:
        True if trade should execute, False otherwise
    """
    if risk_result is None:
        return False
    return risk_result.get("risk_approved", False) and risk_result.get("action") != "HOLD"


def extract_risk_metadata(risk_result: dict[str, object] | None) -> dict[str, object]:
    """
    Extract risk metadata from a checked signal for logging/debugging.

    Args:
        risk_result: Result from evaluate_strategy_signal(), or None

    Returns:
        Dictionary with risk metadata (reasons, score, etc.)
    """
    if risk_result is None:
        return {
            "risk_approved": False,
            "risk_reasons": ["Signal rejected or not checked"],
            "risk_score": 1.0,
        }

    return {
        "risk_approved": risk_result.get("risk_approved", False),
        "risk_reasons": risk_result.get("risk_reasons", []),
        "risk_score": risk_result.get("risk_score", 0.0),
        "action_original": risk_result.get("action", "UNKNOWN"),
        "action_adjusted": risk_result.get("action", "UNKNOWN"),
        "size_original": risk_result.get("size_hint", 0.0),
        "size_adjusted": risk_result.get("size_hint", 0.0),
    }
