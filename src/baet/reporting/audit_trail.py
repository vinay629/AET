"""
Audit Trail System for M5.2 Live Pilot Compliance

Provides comprehensive audit logging for compliance, debugging, and post-trade analysis.
Tracks all trading decisions, risk checks, executions, and position changes.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    """Types of events that get logged in audit trail."""

    TRADE_SIGNAL = "trade_signal"  # Strategy signal generated
    RISK_EVALUATION = "risk_evaluation"  # Risk engine evaluated signal
    TRADE_EXECUTED = "trade_executed"  # Trade executed in paper/live
    TRADE_REJECTED = "trade_rejected"  # Trade rejected (by risk, market, etc)
    POSITION_OPENED = "position_opened"  # Position entry executed
    POSITION_CLOSED = "position_closed"  # Position exit executed
    POSITION_MODIFIED = "position_modified"  # Position size/stop-loss modified
    PORTFOLIO_UPDATED = "portfolio_updated"  # Portfolio state updated
    REGIME_DETECTED = "regime_detected"  # Market regime changed
    RISK_LIMIT_BREACH = "risk_limit_breach"  # Risk limit breached (recovery logged too)
    EMERGENCY_STOP = "emergency_stop"  # Emergency stop triggered
    SYSTEM_ERROR = "system_error"  # System error occurred
    MARKET_DATA_UPDATE = "market_data_update"  # Market data snapshot
    DAILY_SUMMARY = "daily_summary"  # Daily P&L and statistics
    NOTIFICATION_SENT = "notification_sent"  # Alert/notification sent


class RiskEvaluation(BaseModel):
    """Result of risk engine evaluation."""

    approved: bool
    violations: list[str] = Field(default_factory=list)
    original_size: float | None = None
    modified_size: float | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradeSignal(BaseModel):
    """Trading signal from strategy."""

    symbol: str
    action: str  # BUY, SELL, HOLD
    strategy: str
    confidence: float
    price: float | None = None
    size: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEntry(BaseModel):
    """Single audit trail entry."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: AuditEventType
    symbol: str | None = None
    action: str | None = None  # BUY, SELL, HOLD, etc
    quantity: float | None = None
    price: float | None = None
    signal: TradeSignal | None = None
    risk_evaluation: RiskEvaluation | None = None
    position_id: str | None = None
    market_condition: str | None = None  # regime (TRENDING, RANGING, etc)
    volatility: float | None = None
    p_l: float | None = None
    portfolio_value: float | None = None
    cash_balance: float | None = None
    error_message: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditTrail:
    """Audit trail logger for M5.2 live pilot compliance."""

    def __init__(self, log_dir: Path = Path("logs/audit")):
        """Initialize audit trail.

        Args:
            log_dir: Directory for audit logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.entries: list[AuditEntry] = []
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup JSON logger for audit trail."""
        logger = logging.getLogger("audit_trail")
        logger.setLevel(logging.INFO)

        # Remove existing handlers
        logger.handlers = []

        # Create rotating file handler with date
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{today}.jsonl"

        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.INFO)

        # Use simple format - each line is a JSON entry
        formatter = logging.Formatter("%(message)s")  # Message will be JSON
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        return logger

    def log_trade_signal(
        self,
        symbol: str,
        action: str,
        strategy: str,
        confidence: float,
        price: float | None = None,
        size: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Log a trade signal from strategy.

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            action: BUY, SELL, or HOLD
            strategy: Strategy name
            confidence: Confidence score [0-1]
            price: Current price
            size: Suggested position size
            metadata: Additional metadata
        """
        signal = TradeSignal(
            symbol=symbol,
            action=action,
            strategy=strategy,
            confidence=confidence,
            price=price,
            size=size,
            metadata=metadata or {},
        )

        entry = AuditEntry(
            event_type=AuditEventType.TRADE_SIGNAL,
            symbol=symbol,
            action=action,
            signal=signal,
            price=price,
            quantity=size,
            metadata={"strategy": strategy, "confidence": confidence},
        )

        self._log_entry(entry)

    def log_risk_evaluation(
        self,
        symbol: str,
        action: str,
        approved: bool,
        violations: list[str] | None = None,
        original_size: float | None = None,
        modified_size: float | None = None,
        reason: str | None = None,
    ) -> None:
        """Log risk engine evaluation result.

        Args:
            symbol: Trading pair
            action: BUY, SELL, HOLD
            approved: Whether trade was approved
            violations: List of violated risk rules
            original_size: Size before risk adjustment
            modified_size: Size after risk adjustment
            reason: Explanation if rejected
        """
        risk_eval = RiskEvaluation(
            approved=approved,
            violations=violations or [],
            original_size=original_size,
            modified_size=modified_size,
            reason=reason,
        )

        entry = AuditEntry(
            event_type=AuditEventType.RISK_EVALUATION,
            symbol=symbol,
            action=action,
            risk_evaluation=risk_eval,
            quantity=modified_size,
            metadata={
                "approved": approved,
                "violation_count": len(violations or []),
            },
        )

        self._log_entry(entry)

    def log_trade_executed(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        position_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Log executed trade.

        Args:
            symbol: Trading pair
            action: BUY or SELL
            quantity: Amount executed
            price: Execution price
            position_id: Position identifier
            metadata: Additional metadata
        """
        entry = AuditEntry(
            event_type=AuditEventType.TRADE_EXECUTED,
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            position_id=position_id,
            metadata=metadata or {},
        )

        self._log_entry(entry)

    def log_trade_rejected(
        self,
        symbol: str,
        action: str,
        reason: str,
        quantity: float | None = None,
        price: float | None = None,
    ) -> None:
        """Log rejected trade.

        Args:
            symbol: Trading pair
            action: BUY, SELL, HOLD
            reason: Why trade was rejected
            quantity: Intended quantity
            price: Intended price
        """
        entry = AuditEntry(
            event_type=AuditEventType.TRADE_REJECTED,
            symbol=symbol,
            action=action,
            reason=reason,
            quantity=quantity,
            price=price,
        )

        self._log_entry(entry)

    def log_position_opened(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        position_id: str,
        metadata: dict | None = None,
    ) -> None:
        """Log position opened.

        Args:
            symbol: Trading pair
            quantity: Position size
            entry_price: Entry price
            position_id: Position identifier
            metadata: Additional metadata (stop-loss, take-profit, etc)
        """
        entry = AuditEntry(
            event_type=AuditEventType.POSITION_OPENED,
            symbol=symbol,
            action="BUY",
            quantity=quantity,
            price=entry_price,
            position_id=position_id,
            metadata=metadata or {},
        )

        self._log_entry(entry)

    def log_position_closed(
        self,
        symbol: str,
        quantity: float,
        exit_price: float,
        position_id: str,
        entry_price: float,
        p_l: float | None = None,
        reason: str | None = None,
    ) -> None:
        """Log position closed.

        Args:
            symbol: Trading pair
            quantity: Position size
            exit_price: Exit price
            position_id: Position identifier
            entry_price: Original entry price
            p_l: Realized P&L
            reason: Why position was closed (stop-loss, take-profit, manual, etc)
        """
        entry = AuditEntry(
            event_type=AuditEventType.POSITION_CLOSED,
            symbol=symbol,
            action="SELL",
            quantity=quantity,
            price=exit_price,
            position_id=position_id,
            p_l=p_l,
            reason=reason,
            metadata={
                "entry_price": entry_price,
                "pnl_percent": (p_l / (entry_price * quantity * 100))
                if entry_price and quantity
                else None,
            },
        )

        self._log_entry(entry)

    def log_portfolio_updated(
        self,
        total_value: float,
        cash_balance: float,
        positions_count: int,
        daily_p_l: float | None = None,
    ) -> None:
        """Log portfolio state update.

        Args:
            total_value: Total portfolio value
            cash_balance: Available cash
            positions_count: Number of open positions
            daily_p_l: Daily profit/loss
        """
        entry = AuditEntry(
            event_type=AuditEventType.PORTFOLIO_UPDATED,
            portfolio_value=total_value,
            cash_balance=cash_balance,
            p_l=daily_p_l,
            metadata={"positions_count": positions_count},
        )

        self._log_entry(entry)

    def log_regime_detected(
        self,
        regime: str,
        volatility: float,
        trend: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Log detected market regime.

        Args:
            regime: Regime label (TRENDING, RANGING, etc)
            volatility: Current volatility
            trend: Trend direction (UP, DOWN, SIDEWAYS)
            metadata: Additional metadata
        """
        entry = AuditEntry(
            event_type=AuditEventType.REGIME_DETECTED,
            market_condition=regime,
            volatility=volatility,
            metadata={"trend": trend, **(metadata or {})},
        )

        self._log_entry(entry)

    def log_risk_limit_breach(
        self,
        limit_type: str,
        current_value: float,
        limit_value: float,
        action_taken: str | None = None,
    ) -> None:
        """Log risk limit breach.

        Args:
            limit_type: Type of limit (daily_loss, position_loss, consecutive_losses, etc)
            current_value: Current value
            limit_value: Limit threshold
            action_taken: Action taken (e.g., emergency_stop, trade_rejected)
        """
        entry = AuditEntry(
            event_type=AuditEventType.RISK_LIMIT_BREACH,
            reason=f"{limit_type} breached: {current_value:.2f} vs limit {limit_value:.2f}",
            metadata={
                "limit_type": limit_type,
                "current_value": current_value,
                "limit_value": limit_value,
                "action_taken": action_taken,
            },
        )

        self._log_entry(entry)

    def log_emergency_stop(self, reason: str, metadata: dict | None = None) -> None:
        """Log emergency stop event.

        Args:
            reason: Reason for emergency stop
            metadata: Additional metadata
        """
        entry = AuditEntry(
            event_type=AuditEventType.EMERGENCY_STOP,
            reason=reason,
            metadata=metadata or {},
        )

        self._log_entry(entry)

    def log_system_error(
        self,
        error_message: str,
        error_type: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Log system error.

        Args:
            error_message: Error message
            error_type: Exception type
            metadata: Additional metadata
        """
        entry = AuditEntry(
            event_type=AuditEventType.SYSTEM_ERROR,
            error_message=error_message,
            metadata={"error_type": error_type, **(metadata or {})},
        )

        self._log_entry(entry)

    def log_daily_summary(
        self,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        daily_p_l: float,
        daily_return: float,
        highest_price: float | None = None,
        lowest_price: float | None = None,
    ) -> None:
        """Log daily summary statistics.

        Args:
            total_trades: Number of trades in the day
            winning_trades: Number of winning trades
            losing_trades: Number of losing trades
            daily_p_l: Daily P&L
            daily_return: Daily return percentage
            highest_price: Highest price in day
            lowest_price: Lowest price in day
        """
        entry = AuditEntry(
            event_type=AuditEventType.DAILY_SUMMARY,
            p_l=daily_p_l,
            metadata={
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "daily_return_pct": daily_return,
                "win_rate": ((winning_trades / total_trades * 100) if total_trades > 0 else 0),
                "highest_price": highest_price,
                "lowest_price": lowest_price,
            },
        )

        self._log_entry(entry)

    def _log_entry(self, entry: AuditEntry) -> None:
        """Log entry to audit trail.

        Args:
            entry: Audit entry to log
        """
        self.entries.append(entry)

        # Log to file as JSON
        json_str = entry.model_dump_json()
        self.logger.info(json_str)

    def get_entries(
        self,
        event_type: AuditEventType | None = None,
        symbol: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[AuditEntry]:
        """Get filtered audit entries.

        Args:
            event_type: Filter by event type
            symbol: Filter by symbol
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of matching entries
        """
        results = self.entries

        if event_type:
            results = [e for e in results if e.event_type == event_type]

        if symbol:
            results = [e for e in results if e.symbol == symbol]

        if start_time:
            results = [e for e in results if e.timestamp >= start_time]

        if end_time:
            results = [e for e in results if e.timestamp <= end_time]

        return results

    def export_to_json(self, filepath: Path) -> None:
        """Export audit trail to JSON file.

        Args:
            filepath: Output file path
        """
        data = [e.model_dump() for e in self.entries]
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def export_to_jsonl(self, filepath: Path) -> None:
        """Export audit trail to JSONL file (one entry per line).

        Args:
            filepath: Output file path
        """
        with open(filepath, "w") as f:
            for entry in self.entries:
                f.write(entry.model_dump_json() + "\n")

    def get_daily_report(self) -> dict[str, Any]:
        """Get daily audit report summary.

        Returns:
            Dictionary with daily statistics
        """
        today_entries = [e for e in self.entries if e.timestamp.date() == datetime.utcnow().date()]

        trade_signals = [e for e in today_entries if e.event_type == AuditEventType.TRADE_SIGNAL]
        risk_breaches = [
            e for e in today_entries if e.event_type == AuditEventType.RISK_LIMIT_BREACH
        ]
        trades_executed = [
            e for e in today_entries if e.event_type == AuditEventType.TRADE_EXECUTED
        ]
        trades_rejected = [
            e for e in today_entries if e.event_type == AuditEventType.TRADE_REJECTED
        ]

        return {
            "date": datetime.utcnow().date().isoformat(),
            "total_signals": len(trade_signals),
            "total_executed": len(trades_executed),
            "total_rejected": len(trades_rejected),
            "risk_breaches": len(risk_breaches),
            "total_entries": len(today_entries),
            "symbols_traded": list(set(e.symbol for e in trades_executed if e.symbol)),
        }
