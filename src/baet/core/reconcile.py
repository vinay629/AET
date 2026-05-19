"""Exchange reconciliation engine for BAET.

Periodically compares internal state with exchange reality.
Detects and classifies drift. Triggers safety halts on severe divergence.

This is the bridge between internal assumptions and exchange truth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# Default tolerance for balance comparisons
DEFAULT_BALANCE_TOLERANCE = Decimal("0.001")  # 0.1%
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("0.01")  # Minimum absolute difference to flag


class DriftType(StrEnum):
    MISSING_FILL = "missing_fill"
    DUPLICATE_FILL = "duplicate_fill"
    STALE_ORDER = "stale_order"
    UNKNOWN_ORDER = "unknown_order"
    BALANCE_DRIFT = "balance_drift"
    FEE_DRIFT = "fee_drift"
    ROUNDING_DRIFT = "rounding_drift"
    POSITION_DRIFT = "position_drift"


class DriftSeverity(StrEnum):
    INFO = "info"           # Within tolerance, informational
    WARNING = "warning"     # Outside tolerance, monitor closely
    CRITICAL = "critical"   # Significant divergence, halt trading


@dataclass
class DriftReport:
    """A single detected discrepancy."""
    drift_type: DriftType
    severity: DriftSeverity
    symbol: str
    internal_value: str
    exchange_value: str
    difference: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReconciliationReport:
    """Full reconciliation result."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    drifts: list[DriftReport] = field(default_factory=list)
    is_consistent: bool = True
    should_halt: bool = False
    halt_reason: str = ""

    @property
    def critical_count(self) -> int:
        return sum(1 for d in self.drifts if d.severity == DriftSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.drifts if d.severity == DriftSeverity.WARNING)

    def summary(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "is_consistent": self.is_consistent,
            "should_halt": self.should_halt,
            "halt_reason": self.halt_reason,
            "total_drifts": len(self.drifts),
            "critical": self.critical_count,
            "warnings": self.warning_count,
            "drift_types": list(set(d.drift_type.value for d in self.drifts)),
        }


class ReconciliationEngine:
    """
    Compares internal portfolio state with exchange reality.

    Run every 30-60 seconds during live trading.
    Classifies drift and triggers safety halts when needed.
    """

    def __init__(
        self,
        balance_tolerance: Decimal = DEFAULT_BALANCE_TOLERANCE,
        absolute_tolerance: Decimal = DEFAULT_ABSOLUTE_TOLERANCE,
    ) -> None:
        self.balance_tolerance = balance_tolerance
        self.absolute_tolerance = absolute_tolerance
        self._last_report: ReconciliationReport | None = None
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

    def reconcile(
        self,
        internal_balances: dict[str, Decimal],
        exchange_balances: dict[str, Decimal],
        internal_orders: list[dict[str, Any]],
        exchange_orders: list[dict[str, Any]],
    ) -> ReconciliationReport:
        """
        Full reconciliation between internal state and exchange state.

        Args:
            internal_balances: {symbol: quantity} from internal tracking
            exchange_balances: {symbol: quantity} from exchange API
            internal_orders: list of active internal order dicts
            exchange_orders: list of active exchange order dicts
        """
        report = ReconciliationReport()

        # Compare balances
        self._compare_balances(report, internal_balances, exchange_balances)

        # Compare orders
        self._compare_orders(report, internal_orders, exchange_orders)

        # Determine severity
        if report.critical_count > 0:
            report.is_consistent = False
            report.should_halt = True
            report.halt_reason = f"{report.critical_count} critical drift(s) detected"
            self._consecutive_failures += 1
        elif report.warning_count > 0:
            report.is_consistent = False
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

        # Halt if too many consecutive failures
        if self._consecutive_failures >= self._max_consecutive_failures:
            report.should_halt = True
            report.halt_reason = (
                f"{self._consecutive_failures} consecutive reconciliation failures"
            )

        self._last_report = report

        if report.drifts:
            logger.warning(
                f"Reconciliation: {len(report.drifts)} drifts, "
                f"{report.critical_count} critical, {report.warning_count} warnings"
            )
        else:
            logger.info("Reconciliation: all balances and orders consistent")

        return report

    def _compare_balances(
        self,
        report: ReconciliationReport,
        internal: dict[str, Decimal],
        exchange: dict[str, Decimal],
    ) -> None:
        """Compare internal balances with exchange balances."""
        all_symbols = set(internal.keys()) | set(exchange.keys())

        for symbol in all_symbols:
            internal_qty = internal.get(symbol, Decimal("0"))
            exchange_qty = exchange.get(symbol, Decimal("0"))
            diff = exchange_qty - internal_qty

            if diff == 0:
                continue

            abs_diff = abs(diff)
            tolerance = max(
                self.absolute_tolerance,
                abs(internal_qty) * self.balance_tolerance,
            )

            if abs_diff <= tolerance:
                severity = DriftSeverity.INFO
            elif abs_diff <= tolerance * 10:
                severity = DriftSeverity.WARNING
            else:
                severity = DriftSeverity.CRITICAL

            # Classify the drift
            drift_type = self._classify_balance_drift(diff, internal_qty, exchange_qty)

            report.drifts.append(DriftReport(
                drift_type=drift_type,
                severity=severity,
                symbol=symbol,
                internal_value=str(internal_qty),
                exchange_value=str(exchange_qty),
                difference=str(diff),
                message=(
                    f"{symbol}: internal={internal_qty}, exchange={exchange_qty}, "
                    f"diff={diff} ({severity.value})"
                ),
            ))

    def _classify_balance_drift(
        self, diff: Decimal, internal: Decimal, exchange: Decimal
    ) -> DriftType:
        """Classify the type of balance drift."""
        # Very small difference — likely rounding
        if abs(diff) < Decimal("0.0001"):
            return DriftType.ROUNDING_DRIFT

        # Exchange has more than internal — possible missing fill
        if exchange > internal:
            return DriftType.MISSING_FILL

        # Internal has more than exchange — possible fee drift or duplicate
        return DriftType.BALANCE_DRIFT

    def _compare_orders(
        self,
        report: ReconciliationReport,
        internal_orders: list[dict[str, Any]],
        exchange_orders: list[dict[str, Any]],
    ) -> None:
        """Compare internal open orders with exchange open orders."""
        internal_ids = {o.get("exchange_order_id") or o.get("client_order_id"): o for o in internal_orders}
        exchange_ids = {o.get("exchange_order_id"): o for o in exchange_orders if o.get("exchange_order_id")}

        # Orders we think are open but exchange doesn't know about
        for order_id, order in internal_ids.items():
            if order_id not in exchange_ids:
                report.drifts.append(DriftReport(
                    drift_type=DriftType.STALE_ORDER,
                    severity=DriftSeverity.WARNING,
                    symbol=order.get("symbol", "unknown"),
                    internal_value=order.get("status", "unknown"),
                    exchange_value="not_found",
                    difference="order_missing_on_exchange",
                    message=f"Order {order_id} tracked internally but not on exchange",
                ))

        # Orders on exchange but we don't know about
        for order_id, order in exchange_ids.items():
            if order_id not in internal_ids:
                report.drifts.append(DriftReport(
                    drift_type=DriftType.UNKNOWN_ORDER,
                    severity=DriftSeverity.CRITICAL,
                    symbol=order.get("symbol", "unknown"),
                    internal_value="not_tracked",
                    exchange_value=order.get("status", "unknown"),
                    difference="order_missing_internally",
                    message=f"Order {order_id} on exchange but not tracked internally",
                ))

    @property
    def last_report(self) -> ReconciliationReport | None:
        return self._last_report

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures
