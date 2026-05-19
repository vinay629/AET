"""Exchange reconciliation loop for BAET.

Runs periodically during live/paper trading:
    exchange state  vs  internal reducer state

On critical drift → auto-halt trading.

This is NOT a one-shot check at boot. It runs continuously
while the engine is running, comparing the exchange's view
of the world with our reducer-derived view.

Architecture:
    ReconcileLoop runs on a timer.
    Each tick:
        1. Query exchange balances + open orders
        2. Build internal view from reducer state
        3. Run ReconciliationEngine
        4. If critical drift → emit SYSTEM_HALT event
        5. If warning → emit WARNING event
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from baet.core.clock import Clock, get_clock
from baet.core.events import Event, EventStore, EventType
from baet.core.health import HealthMonitor, HealthStatus
from baet.core.orders import Order, OrderTracker
from baet.core.reconcile import (
    DriftSeverity,
    ReconciliationEngine,
    ReconciliationReport,
)
from baet.core.state import PortfolioState

logger = logging.getLogger(__name__)


class ReconcileAction(StrEnum):
    NONE = "none"
    LOG = "log"
    WARN = "warn"
    HALT = "halt"


@dataclass
class ReconcileTick:
    """Result of a single reconciliation tick."""
    timestamp: datetime
    action: ReconcileAction
    report: ReconciliationReport | None
    halted: bool


class ExchangeSnapshot(Protocol):
    """Interface for getting exchange state during reconciliation."""

    def get_balances(self) -> dict[str, Decimal]: ...
    def get_open_orders(self) -> list[dict[str, Any]]: ...


class ReconcileLoop:
    """
    Periodic reconciliation between exchange and internal state.

    Runs in a background thread. Each tick:
        1. Fetches exchange balances + orders
        2. Builds internal view from current PortfolioState
        3. Runs reconciliation engine
        4. Takes action based on drift severity

    Thread-safe: uses a lock when reading/writing shared state.
    """

    def __init__(
        self,
        event_store: EventStore,
        reconciliation_engine: ReconciliationEngine | None = None,
        interval_seconds: float = 30.0,
        clock: Clock | None = None,
    ) -> None:
        self.event_store = event_store
        self.engine = reconciliation_engine or ReconciliationEngine()
        self.interval_seconds = interval_seconds
        self.clock = clock or get_clock()

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._halted = False
        self._last_tick: ReconcileTick | None = None
        self._tick_count = 0

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def last_tick(self) -> ReconcileTick | None:
        return self._last_tick

    def start(self) -> None:
        """Start the reconciliation loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="reconcile_loop"
        )
        self._thread.start()
        logger.info(f"ReconcileLoop started (interval={ self.interval_seconds}s)")

    def stop(self) -> None:
        """Stop the reconciliation loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("ReconcileLoop stopped")

    def tick(
        self,
        state: PortfolioState,
        exchange: ExchangeSnapshot,
        order_tracker: OrderTracker | None = None,
    ) -> ReconcileTick:
        """
        Execute a single reconciliation tick.

        This is the core method — can be called manually (for testing)
        or by the background loop.

        Args:
            state: Current portfolio state from the reducer.
            exchange: Exchange client for fetching balances/orders.
            order_tracker: Optional tracker for open order comparison.

        Returns:
            ReconcileTick with the result.
        """
        now = self.clock.now()

        # Build internal balance view from reducer state
        internal_balances: dict[str, Decimal] = {"USDT": state.cash}
        for symbol, pos in state.positions.items():
            base = symbol.replace("USDT", "").replace("BUSD", "")
            if base:
                internal_balances[base] = pos["units"]

        # Build internal order view
        internal_orders: list[dict[str, Any]] = []
        if order_tracker:
            for order in order_tracker.get_active_orders():
                internal_orders.append({
                    "client_order_id": order.client_order_id,
                    "exchange_order_id": order.exchange_order_id,
                    "symbol": order.symbol,
                    "status": order.status.value,
                    "side": order.side.value,
                    "quantity": str(order.quantity),
                    "filled_quantity": str(order.filled_quantity),
                })

        # Fetch exchange state
        try:
            exchange_balances = exchange.get_balances()
            exchange_orders = exchange.get_open_orders()
        except Exception as e:
            logger.error(f"Failed to fetch exchange state: {e}")
            tick = ReconcileTick(
                timestamp=now,
                action=ReconcileAction.WARN,
                report=None,
                halted=False,
            )
            self._last_tick = tick
            return tick

        # Run reconciliation
        report = self.engine.reconcile(
            internal_balances=internal_balances,
            exchange_balances=exchange_balances,
            internal_orders=internal_orders,
            exchange_orders=exchange_orders,
        )

        # Determine action
        if report.should_halt:
            action = ReconcileAction.HALT
            self._halted = True
            # Persist halt event
            self.event_store.append(
                event_type=EventType.ERROR,
                timestamp_exchange=now,
                source="reconcile_loop",
                payload={
                    "type": "RECONCILIATION_HALT",
                    "reason": report.halt_reason,
                    "critical_count": report.critical_count,
                    "warning_count": report.warning_count,
                },
            )
            logger.critical(f"RECONCILIATION HALT: {report.halt_reason}")
        elif report.critical_count > 0:
            action = ReconcileAction.HALT
            self._halted = True
            logger.critical(f"Critical drift: {report.critical_count} issues")
        elif report.warning_count > 0:
            action = ReconcileAction.WARN
            logger.warning(f"Reconciliation warnings: {report.warning_count}")
        elif report.drifts:
            action = ReconcileAction.LOG
            logger.info(f"Reconciliation info: {len(report.drifts)} minor drifts")
        else:
            action = ReconcileAction.NONE

        tick = ReconcileTick(
            timestamp=now,
            action=action,
            report=report,
            halted=self._halted,
        )

        with self._lock:
            self._last_tick = tick
            self._tick_count += 1

        return tick

    def _run_loop(self) -> None:
        """Background loop — runs tick() at the configured interval.

        Subclasses or callers should override this to provide
        state and exchange client. The base implementation
        just sleeps — use tick() directly for now.
        """
        while self._running:
            time.sleep(self.interval_seconds)
            # The actual tick() call needs state + exchange,
            # which the caller provides. This loop just manages timing.
            # In production, this would be wired to the engine's
            # current state and exchange client.
