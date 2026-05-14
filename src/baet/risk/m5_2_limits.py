"""M5.2 Risk limit validator and enforcement.

This module validates and enforces the M5.2 live pilot risk limits:
- Daily loss limit ($10)
- Single position loss limit ($5)
- Consecutive loss limit (3 trades)
- Max concurrent positions (2)
- Max daily trades (5)
"""

from dataclasses import dataclass, field

from baet.config.models import M5Point2RiskLimits


@dataclass
class M5Point2RiskTracker:
    """Tracks M5.2 risk metrics for compliance."""

    limits: M5Point2RiskLimits
    daily_realized_pl: float = 0.0
    daily_trades: int = 0
    consecutive_losses: int = 0
    concurrent_positions: int = 0
    position_pls: dict[str, float] = field(default_factory=dict)
    emergency_stop_triggered: bool = False
    last_breach_reason: str | None = None

    def reset_daily(self) -> None:
        """Reset daily metrics (call at start of each trading day)."""
        self.daily_realized_pl = 0.0
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.position_pls.clear()

    def check_can_trade(self) -> tuple[bool, str | None]:
        """Check if new trade can be made.

        Returns:
            (can_trade, reason_if_cannot)
        """
        # Check emergency stop
        if self.emergency_stop_triggered:
            return False, "EMERGENCY_STOP_ACTIVE"

        # Check daily loss limit
        if self.daily_realized_pl <= -self.limits.daily_loss_limit:
            reason = f"DAILY_LOSS_LIMIT ({self.daily_realized_pl:.2f} <= -{self.limits.daily_loss_limit})"
            if self.limits.emergency_stop_on_breach:
                self.emergency_stop_triggered = True
            return False, reason

        # Check consecutive losses
        if self.consecutive_losses >= self.limits.consecutive_loss_limit:
            reason = f"CONSECUTIVE_LOSSES ({self.consecutive_losses} >= {self.limits.consecutive_loss_limit})"
            if self.limits.emergency_stop_on_breach:
                self.emergency_stop_triggered = True
            return False, reason

        # Check max daily trades
        if self.daily_trades >= self.limits.max_daily_trades:
            reason = f"DAILY_TRADE_LIMIT ({self.daily_trades} >= {self.limits.max_daily_trades})"
            return False, reason

        # Check max concurrent positions
        if self.concurrent_positions >= self.limits.max_concurrent_positions:
            reason = f"CONCURRENT_POSITIONS ({self.concurrent_positions} >= {self.limits.max_concurrent_positions})"
            return False, reason

        return True, None

    def on_trade_executed(self, position_id: str, quantity: float, entry_price: float) -> None:
        """Record a trade execution.

        Args:
            position_id: Unique position identifier
            quantity: Trade quantity
            entry_price: Entry price
        """
        self.daily_trades += 1
        self.concurrent_positions += 1
        self.position_pls[position_id] = 0.0

    def on_position_closed(
        self, position_id: str, exit_price: float, entry_price: float, quantity: float
    ) -> None:
        """Record position closure and update P&L tracking.

        Args:
            position_id: Position identifier
            exit_price: Exit price
            entry_price: Entry price
            quantity: Position quantity
        """
        if position_id not in self.position_pls:
            return

        pl = (exit_price - entry_price) * quantity
        self.position_pls[position_id] = pl
        self.daily_realized_pl += pl
        self.concurrent_positions = max(0, self.concurrent_positions - 1)

        # Track consecutive losses
        if pl < -self.limits.single_position_loss_limit:
            self.consecutive_losses += 1
            if self.limits.emergency_stop_on_breach:
                self.emergency_stop_triggered = True
                self.last_breach_reason = (
                    f"POSITION_LOSS_LIMIT ({pl:.2f} <= -{self.limits.single_position_loss_limit})"
                )
        else:
            self.consecutive_losses = 0  # Reset on winning trade

        del self.position_pls[position_id]

    def on_position_updated(self, position_id: str, current_pl: float) -> tuple[bool, str | None]:
        """Check position for stop-loss (unrealized loss limit).

        Args:
            position_id: Position identifier
            current_pl: Current unrealized P&L

        Returns:
            (should_close, reason)
        """
        if current_pl <= -self.limits.single_position_loss_limit:
            if self.limits.emergency_stop_on_breach:
                self.emergency_stop_triggered = True
                reason = f"POSITION_LOSS_LIMIT ({current_pl:.2f} <= -{self.limits.single_position_loss_limit})"
                self.last_breach_reason = reason
                return True, reason
            return True, f"STOP_LOSS_HIT ({current_pl:.2f})"

        return False, None

    def trigger_emergency_stop(self, reason: str) -> None:
        """Trigger emergency stop (manual or automatic).

        Args:
            reason: Reason for emergency stop
        """
        self.emergency_stop_triggered = True
        self.last_breach_reason = f"EMERGENCY_STOP: {reason}"

    def reset_emergency_stop(self) -> None:
        """Reset emergency stop (requires manual intervention)."""
        self.emergency_stop_triggered = False
        self.last_breach_reason = None

    def get_status(self) -> dict:
        """Get current M5.2 risk status.

        Returns:
            Status dictionary
        """
        can_trade, reason = self.check_can_trade()

        return {
            "can_trade": can_trade,
            "blocked_reason": reason,
            "emergency_stop_active": self.emergency_stop_triggered,
            "daily_realized_pl": self.daily_realized_pl,
            "daily_trades": self.daily_trades,
            "consecutive_losses": self.consecutive_losses,
            "concurrent_positions": self.concurrent_positions,
            "daily_loss_limit": self.limits.daily_loss_limit,
            "daily_loss_remaining": (self.limits.daily_loss_limit - abs(self.daily_realized_pl)),
            "consecutive_loss_limit": self.limits.consecutive_loss_limit,
            "max_concurrent_positions": self.limits.max_concurrent_positions,
            "max_daily_trades": self.limits.max_daily_trades,
            "capital_at_risk": self.limits.capital_at_risk,
            "positions_open": len(self.position_pls),
        }

    def get_breaches(self) -> list[str]:
        """Get list of current breaches.

        Returns:
            List of breach reasons
        """
        breaches = []

        if self.daily_realized_pl <= -self.limits.daily_loss_limit:
            breaches.append(f"Daily loss limit: {self.daily_realized_pl:.2f}")

        if self.consecutive_losses >= self.limits.consecutive_loss_limit:
            breaches.append(f"Consecutive losses: {self.consecutive_losses}")

        if self.daily_trades >= self.limits.max_daily_trades:
            breaches.append(f"Daily trade limit: {self.daily_trades}")

        if self.concurrent_positions >= self.limits.max_concurrent_positions:
            breaches.append(f"Concurrent positions: {self.concurrent_positions}")

        if self.emergency_stop_triggered:
            breaches.append(f"Emergency stop active: {self.last_breach_reason}")

        return breaches
