"""Risk policy models for BAET trading platform."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PositionSizingPolicy(BaseModel):
    """Position sizing rules and limits."""

    max_risk_per_trade: float = 0.01  # 1% max risk per trade
    max_position_size: float = 0.10  # 10% max in any single position
    min_position_size: float = 0.001  # 0.1% min to avoid dust
    sizing_method: Literal["fixed", "kelly", "percent_risk"] = "percent_risk"

    class Config:
        frozen = True


class DrawdownProtectionPolicy(BaseModel):
    """Drawdown protection and stop-loss rules."""

    max_portfolio_drawdown: float = 0.15  # 15% max portfolio drawdown
    max_daily_loss: float = 0.05  # 5% max daily loss
    trailing_stop_enabled: bool = True
    trailing_stop_distance: float = 0.03  # 3% trailing stop
    kill_switch_drawdown: float = 0.20  # 20% triggers kill-switch

    class Config:
        frozen = True


class RegimeRiskPolicy(BaseModel):
    """Risk adjustments based on market regime."""

    trending_max_exposure: float = 0.20
    ranging_max_exposure: float = 0.15
    high_volatility_max_exposure: float = 0.10
    low_volatility_max_exposure: float = 0.25
    regime_confidence_threshold: float = 0.60

    class Config:
        frozen = True


class StrategyRiskPolicy(BaseModel):
    """Per-strategy risk limits and controls."""

    enabled_strategies: list[str] = Field(default_factory=list)  # Empty = all enabled
    blacklisted_strategies: list[str] = Field(default_factory=list)
    max_strategy_allocation: dict[str, float] = Field(default_factory=dict)
    strategy_min_sharpe: float = 0.5  # Min Sharpe to allow strategy
    strategy_max_drawdown: float = 0.15  # Max drawdown per strategy

    class Config:
        frozen = True


class PortfolioRiskPolicy(BaseModel):
    """Portfolio-level risk limits."""

    max_total_exposure: float = 0.50  # 50% max total exposure
    max_correlation: float = 0.70  # Max correlation between positions
    max_concentration: float = 0.30  # Max 30% in any one symbol
    max_active_positions: int = 10
    max_leverage: float = 1.0  # No leverage for initial release

    class Config:
        frozen = True


class EmergencyPolicy(BaseModel):
    """Emergency controls and kill-switch conditions."""

    kill_switch_enabled: bool = True
    kill_switch_conditions: list[str] = Field(
        default_factory=lambda: [
            "portfolio_drawdown_exceeded",
            "daily_loss_exceeded",
            "consecutive_losses_10",
            "manual_trigger",
        ]
    )
    cooldown_period_hours: int = 24
    require_manual_reset: bool = True
    notify_on_trigger: bool = True

    class Config:
        frozen = True


class RiskPolicy(BaseModel):
    """
    Master risk policy container.

    This is the single source of truth for all risk rules in BAET.
    All trade signals must pass through checks defined by these policies.
    """

    position_sizing: PositionSizingPolicy = Field(default_factory=PositionSizingPolicy)
    drawdown: DrawdownProtectionPolicy = Field(default_factory=DrawdownProtectionPolicy)
    regime: RegimeRiskPolicy = Field(default_factory=RegimeRiskPolicy)
    strategy: StrategyRiskPolicy = Field(default_factory=StrategyRiskPolicy)
    portfolio: PortfolioRiskPolicy = Field(default_factory=PortfolioRiskPolicy)
    emergency: EmergencyPolicy = Field(default_factory=EmergencyPolicy)

    class Config:
        frozen = True

    @classmethod
    def create_default(cls) -> RiskPolicy:
        """Create default risk policy."""
        return cls()

    def get_max_exposure_for_regime(self, regime: str) -> float:
        """Get max exposure limit based on market regime."""
        regime_map = {
            "TRENDING": self.regime.trending_max_exposure,
            "RANGING": self.regime.ranging_max_exposure,
            "HIGH_VOLATILITY": self.regime.high_volatility_max_exposure,
            "LOW_VOLATILITY": self.regime.low_volatility_max_exposure,
        }
        return regime_map.get(regime.upper(), self.portfolio.max_total_exposure)

    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """Check if a strategy is enabled (not blacklisted, in enabled list if set)."""
        if strategy_name in self.strategy.blacklisted_strategies:
            return False
        if (
            self.strategy.enabled_strategies
            and strategy_name not in self.strategy.enabled_strategies
        ):
            return False
        return True
