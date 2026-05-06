"""Risk check result models for BAET trading platform."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class RiskViolation(BaseModel):
    """
    Represents a single risk rule violation.
    
    Used to provide detailed information about why a trade was rejected
    or modified by the risk engine.
    """
    
    rule: str  # Which rule was violated (e.g., "max_position_size", "drawdown_limit")
    severity: Literal["warning", "critical", "kill_switch"] = "warning"
    message: str  # Human-readable description
    current_value: float | None = None  # Current metric value
    threshold_value: float | None = None  # Threshold that was exceeded
    strategy_name: str | None = None  # Which strategy triggered this
    symbol: str | None = None  # Which symbol triggered this
    
    class Config:
        frozen = True


class RiskCheckResult(BaseModel):
    """
    Result of running risk checks on a trade signal.
    
    This is the output of the risk engine. It indicates whether the trade
    was approved, rejected, or modified, along with detailed reasons.
    """
    
    approved: bool  # Whether the trade is approved (may be modified)
    action: str  # Original action (BUY, SELL, HOLD)
    adjusted_action: str  # May be modified to HOLD or reduced
    adjusted_size: float | None = None  # May be reduced from original
    confidence: float = 1.0  # Confidence in the risk decision (0.0 to 1.0)
    reasons: list[str] = Field(default_factory=list)  # Why approved/rejected
    risk_score: float = 0.0  # 0.0 (safe) to 1.0 (high risk)
    violations: list[RiskViolation] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    
    class Config:
        frozen = True
    
    @classmethod
    def approve(cls, action: str, size: float | None = None, 
                reasons: list[str] | None = None) -> RiskCheckResult:
        """Create an approved result."""
        return cls(
            approved=True,
            action=action,
            adjusted_action=action,
            adjusted_size=size,
            confidence=1.0,
            reasons=reasons or ["Risk check passed"],
            risk_score=0.0
        )
    
    @classmethod
    def reject(cls, action: str, reasons: list[str], 
               violations: list[RiskViolation] | None = None) -> RiskCheckResult:
        """Create a rejected result."""
        return cls(
            approved=False,
            action=action,
            adjusted_action="HOLD",  # Force HOLD on rejection
            adjusted_size=0.0,
            confidence=1.0,
            reasons=reasons,
            risk_score=1.0,
            violations=violations or []
        )
    
    @classmethod
    def modify(cls, action: str, original_size: float, 
                 modified_size: float, reasons: list[str]) -> RiskCheckResult:
        """Create a modified result (approved with changes)."""
        return cls(
            approved=True,
            action=action,
            adjusted_action=action,
            adjusted_size=modified_size,
            confidence=0.8,
            reasons=reasons,
            risk_score=0.3,
        )
    
    def add_violation(self, violation: RiskViolation) -> None:
        """Add a violation to the result (mutable for building results)."""
        self.violations.append(violation)
        if violation.severity == "kill_switch":
            self.approved = False
            self.adjusted_action = "HOLD"
            self.adjusted_size = 0.0
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the risk check."""
        status = "APPROVED" if self.approved else "REJECTED"
        if self.adjusted_action != self.action:
            status += f" (modified to {self.adjusted_action})"
        reasons_text = "; ".join(self.reasons[:3])  # First 3 reasons
        return f"{status}: {reasons_text}"
