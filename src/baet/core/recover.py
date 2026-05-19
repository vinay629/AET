"""Boot recovery for BAET.

Startup flow:
    1. Load latest snapshot
    2. Replay remaining events from journal
    3. Verify state invariants
    4. Reconcile with exchange (if live/paper mode)

This is the ONLY path from "process started" to "ready to trade".
No component may skip this sequence.

Usage:
    recovery = RecoveryManager(snapshot_dir, event_store)
    result = recovery.boot(exchange_client)
    if result.ready:
        state = result.state
    else:
        halt_trading(result.reason)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from baet.core.clock import Clock, get_clock
from baet.core.events import Event, EventStore, EventType
from baet.core.health import HealthMonitor, HealthStatus
from baet.core.reconcile import DriftSeverity, ReconciliationEngine, ReconciliationReport
from baet.core.snapshot import SnapshotManager
from baet.core.state import PortfolioState

logger = logging.getLogger(__name__)


class ExchangeClient(Protocol):
    """Minimal interface needed for reconciliation during boot."""

    def get_balances(self) -> dict[str, Decimal]: ...
    def get_open_orders(self) -> list[dict[str, Any]]: ...


@dataclass
class BootResult:
    """Result of the boot recovery process."""
    ready: bool
    state: PortfolioState | None
    last_sequence: int
    snapshot_sequence: int
    events_replayed: int
    invariants_ok: bool
    reconciliation: ReconciliationReport | None
    reason: str = ""  # Only set when ready=False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RecoveryManager:
    """
    Orchestrates the boot recovery sequence.

    The sequence is:
        1. Load latest snapshot (or start from zero)
        2. Replay all events after the snapshot
        3. Verify invariants on the reconstructed state
        4. If exchange_client provided, reconcile
    """

    def __init__(
        self,
        snapshot_dir: Path,
        event_store: EventStore,
        snapshot_manager: SnapshotManager | None = None,
        reconciliation_engine: ReconciliationEngine | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.snapshot_dir = snapshot_dir
        self.event_store = event_store
        self.snapshot_manager = snapshot_manager or SnapshotManager(snapshot_dir)
        self.reconciliation_engine = reconciliation_engine or ReconciliationEngine()
        self.clock = clock or get_clock()

    def boot(
        self,
        exchange_client: ExchangeClient | None = None,
        date: str | None = None,
    ) -> BootResult:
        """
        Execute the full boot recovery sequence.

        Args:
            exchange_client: If provided, reconcile with exchange after replay.
            date: Optional date string (YYYY-MM-DD). Defaults to today.

        Returns:
            BootResult with state and readiness status.
        """
        logger.info("=== BOOT RECOVERY START ===")

        # Step 1: Load snapshot
        state, snapshot_sequence, events_replayed = self._restore_state(date)

        # Step 2: Verify invariants
        violations = state.verify_invariants()
        invariants_ok = len(violations) == 0

        if not invariants_ok:
            logger.error(f"INVARIANT VIOLATIONS after replay: {violations}")
            return BootResult(
                ready=False,
                state=state,
                last_sequence=snapshot_sequence + events_replayed,
                snapshot_sequence=snapshot_sequence,
                events_replayed=events_replayed,
                invariants_ok=False,
                reconciliation=None,
                reason=f"Invariant violations: {violations}",
            )

        logger.info(
            f"State reconstructed: cash={state.cash}, "
            f"positions={list(state.positions.keys())}, "
            f"trades={len(state.trades)}, "
            f"invariants_ok=True"
        )

        # Step 3: Reconcile with exchange (if client provided)
        reconciliation_report = None
        if exchange_client is not None:
            reconciliation_report = self._reconcile(state, exchange_client)

            if reconciliation_report.should_halt:
                logger.error(
                    f"RECONCILIATION HALT: {reconciliation_report.halt_reason}"
                )
                return BootResult(
                    ready=False,
                    state=state,
                    last_sequence=snapshot_sequence + events_replayed,
                    snapshot_sequence=snapshot_sequence,
                    events_replayed=events_replayed,
                    invariants_ok=True,
                    reconciliation=reconciliation_report,
                    reason=f"Reconciliation halt: {reconciliation_report.halt_reason}",
                )

            if not reconciliation_report.is_consistent:
                logger.warning(
                    f"Reconciliation warnings: {reconciliation_report.warning_count} warnings, "
                    f"{reconciliation_report.critical_count} critical"
                )
            else:
                logger.info("Reconciliation: consistent")

        last_seq = snapshot_sequence + events_replayed
        logger.info(f"=== BOOT RECOVERY COMPLETE — ready=True, sequence={last_seq} ===")

        return BootResult(
            ready=True,
            state=state,
            last_sequence=last_seq,
            snapshot_sequence=snapshot_sequence,
            events_replayed=events_replayed,
            invariants_ok=True,
            reconciliation=reconciliation_report,
        )

    def _restore_state(self, date: str | None) -> tuple[PortfolioState, int, int]:
        """
        Restore state from snapshot + replay.

        Returns (state, snapshot_sequence, events_replayed).
        """
        result_state, last_sequence = self.snapshot_manager.restore_state(
            self.event_store, date
        )

        # Determine snapshot sequence from the snapshot metadata
        meta_path = self.snapshot_dir / "latest.json"
        snapshot_sequence = 0
        if meta_path.exists():
            import json
            with meta_path.open("r") as f:
                meta = json.load(f)
            snapshot_sequence = meta.get("latest_sequence", 0)

        events_replayed = max(0, last_sequence - snapshot_sequence)

        logger.info(
            f"Restored: snapshot_seq={snapshot_sequence}, "
            f"last_seq={last_sequence}, replayed={events_replayed}"
        )

        return result_state, snapshot_sequence, events_replayed

    def _reconcile(
        self, state: PortfolioState, client: ExchangeClient
    ) -> ReconciliationReport:
        """Run reconciliation between internal state and exchange."""
        # Build internal balance view
        internal_balances: dict[str, Decimal] = {"USDT": state.cash}
        for symbol, pos in state.positions.items():
            # Extract base asset from symbol (e.g., BTCUSDT → BTC)
            base = symbol.replace("USDT", "").replace("BUSD", "")
            if base:
                internal_balances[base] = pos["units"]

        # Build internal order view from recent events
        internal_orders: list[dict[str, Any]] = []
        # In a full implementation, we'd track open orders from the event journal.
        # For now, we pass an empty list — the reconciliation engine will flag
        # any exchange orders not tracked internally.

        exchange_balances = client.get_balances()
        exchange_orders = client.get_open_orders()

        report = self.reconciliation_engine.reconcile(
            internal_balances=internal_balances,
            exchange_balances=exchange_balances,
            internal_orders=internal_orders,
            exchange_orders=exchange_orders,
        )

        return report
