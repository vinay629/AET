"""Risk controls and policy hooks."""

from baet.risk.checks import RiskCheckResult, RiskViolation
from baet.risk.engine import RiskEngine
from baet.risk.integration import (
    create_risk_engine_from_config,
    evaluate_combined_signals,
    evaluate_strategy_signal,
    extract_risk_metadata,
    should_execute_trade,
    update_risk_engine_state,
)
from baet.risk.policy import (
    DrawdownProtectionPolicy,
    EmergencyPolicy,
    PortfolioRiskPolicy,
    PositionSizingPolicy,
    RegimeRiskPolicy,
    RiskPolicy,
    StrategyRiskPolicy,
)

__all__ = [
    "RiskCheckResult",
    "RiskViolation",
    "RiskEngine",
    "RiskPolicy",
    "PositionSizingPolicy",
    "DrawdownProtectionPolicy",
    "RegimeRiskPolicy",
    "StrategyRiskPolicy",
    "PortfolioRiskPolicy",
    "EmergencyPolicy",
    "create_risk_engine_from_config",
    "evaluate_strategy_signal",
    "evaluate_combined_signals",
    "update_risk_engine_state",
    "should_execute_trade",
    "extract_risk_metadata",
]
