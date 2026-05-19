"""Tests for boot recovery.

Verifies the startup flow:
    snapshot → replay → invariants → reconcile
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from baet.core.clock import Clock, set_clock, reset_clock
from baet.core.events import Event, EventStore, EventType
from baet.core.recover import BootResult, ExchangeClient, RecoveryManager
from baet.core.reconcile import ReconciliationEngine
from baet.core.snapshot import SnapshotManager
from baet.core.state import PortfolioState


class FakeExchange:
    """Fake exchange client for testing reconciliation."""

    def __init__(
        self,
        balances: dict[str, Decimal] | None = None,
        orders: list[dict[str, Any]] | None = None,
    ) -> None:
        self._balances = balances or {}
        self._orders = orders or []

    def get_balances(self) -> dict[str, Decimal]:
        return self._balances

    def get_open_orders(self) -> list[dict[str, Any]]:
        return self._orders


TEST_TS = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def tmp_dirs(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    event_dir = tmp_path / "events"
    snapshot_dir.mkdir()
    event_dir.mkdir()
    # Use a fixed clock so event validation doesn't fail from wall-clock mismatch
    set_clock(Clock.fixed(TEST_TS))
    yield {"snapshot_dir": snapshot_dir, "event_dir": event_dir}
    reset_clock()


class TestBootFromScratch:
    def test_no_snapshot_replays_all(self, tmp_dirs) -> None:
        store = EventStore(tmp_dirs["event_dir"])
        store.append(
            EventType.ORDER_FILLED,
            TEST_TS,
            "test",
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "price": 1000.0,
                "units": 1.0,
                "fee": 1.0,
                "timestamp": TEST_TS.isoformat(),
            },
        )
        store.close()

        recovery = RecoveryManager(tmp_dirs["snapshot_dir"], store)
        result = recovery.boot()

        assert result.ready is True
        assert result.state is not None
        assert result.state.cash == Decimal("8999")
        assert result.events_replayed == 1

    def test_no_events_no_snapshot(self, tmp_dirs) -> None:
        store = EventStore(tmp_dirs["event_dir"])
        store.close()

        recovery = RecoveryManager(tmp_dirs["snapshot_dir"], store)
        result = recovery.boot()

        assert result.ready is True
        assert result.state is not None
        assert result.state.cash == Decimal("10000.0")
        assert result.events_replayed == 0


class TestBootWithSnapshot:
    def test_restore_from_snapshot_plus_replay(self, tmp_dirs) -> None:
        store = EventStore(tmp_dirs["event_dir"])
        snap_mgr = SnapshotManager(tmp_dirs["snapshot_dir"], interval=2)

        # Append 2 events — should trigger snapshot at event 2
        for i in range(2):
            store.append(
                EventType.ORDER_FILLED,
                TEST_TS,
                "test",
                {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "price": 1000.0,
                    "units": 0.01,
                    "fee": 0.1,
                    "timestamp": TEST_TS.isoformat(),
                },
            )

        # Force snapshot save
        state = PortfolioState.from_journal(store)
        snap_mgr.save_snapshot(state, event_sequence=2, event_count=2, store=store)

        # Append 1 more event after snapshot
        store.append(
            EventType.ORDER_FILLED,
            TEST_TS,
            "test",
            {
                "symbol": "ETHUSDT",
                "side": "BUY",
                "price": 3500.0,
                "units": 0.1,
                "fee": 0.35,
                "timestamp": TEST_TS.isoformat(),
            },
        )
        store.close()

        # Boot should restore from snapshot + replay 1 event
        recovery = RecoveryManager(
            tmp_dirs["snapshot_dir"], store, snapshot_manager=snap_mgr
        )
        result = recovery.boot()

        assert result.ready is True
        assert result.state is not None
        assert "BTCUSDT" in result.state.positions
        assert "ETHUSDT" in result.state.positions
        assert result.events_replayed >= 1


class TestBootInvariantViolation:
    def test_negative_cash_halts(self, tmp_dirs) -> None:
        store = EventStore(tmp_dirs["event_dir"])

        # Manually corrupt state via portfolio update
        store.append(
            EventType.PORTFOLIO_UPDATED,
            TEST_TS,
            "test",
            {"cash": "-100.00"},
        )
        store.close()

        recovery = RecoveryManager(tmp_dirs["snapshot_dir"], store)
        result = recovery.boot()

        assert result.ready is False
        assert result.invariants_ok is False
        assert "Cash is negative" in result.reason


class TestBootReconciliation:
    def test_consistent_with_exchange(self, tmp_dirs) -> None:
        store = EventStore(tmp_dirs["event_dir"])
        store.append(
            EventType.ORDER_FILLED,
            TEST_TS,
            "test",
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "price": 1000.0,
                "units": 0.01,
                "fee": 0.1,
                "timestamp": TEST_TS.isoformat(),
            },
        )
        store.close()

        # Exchange matches internal state
        # Internal: cash = 10000 - (0.01 * 1000 + 0.1) = 9989.90
        exchange = FakeExchange(
            balances={"USDT": Decimal("9989.90"), "BTC": Decimal("0.01")},
            orders=[],
        )

        recovery = RecoveryManager(tmp_dirs["snapshot_dir"], store)
        result = recovery.boot(exchange_client=exchange)

        assert result.ready is True
        assert result.reconciliation is not None

    def test_critical_drift_halts(self, tmp_dirs) -> None:
        store = EventStore(tmp_dirs["event_dir"])
        store.append(
            EventType.ORDER_FILLED,
            TEST_TS,
            "test",
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "price": 1000.0,
                "units": 0.01,
                "fee": 0.1,
                "timestamp": TEST_TS.isoformat(),
            },
        )
        store.close()

        # Exchange has an unknown order — critical drift
        exchange = FakeExchange(
            balances={"USDT": Decimal("8999.9"), "BTC": Decimal("0.01")},
            orders=[{"exchange_order_id": "ext-123", "symbol": "ETHUSDT", "status": "open"}],
        )

        recovery = RecoveryManager(tmp_dirs["snapshot_dir"], store)
        result = recovery.boot(exchange_client=exchange)

        assert result.ready is False
        assert result.reconciliation is not None
        assert result.reconciliation.should_halt is True


class TestBootResult:
    def test_ready_result_has_state(self, tmp_dirs) -> None:
        store = EventStore(tmp_dirs["event_dir"])
        store.close()

        recovery = RecoveryManager(tmp_dirs["snapshot_dir"], store)
        result = recovery.boot()

        assert result.ready is True
        assert result.state is not None
        assert isinstance(result.state, PortfolioState)

    def test_not_ready_has_reason(self, tmp_dirs) -> None:
        store = EventStore(tmp_dirs["event_dir"])
        store.append(
            EventType.PORTFOLIO_UPDATED,
            TEST_TS,
            "test",
            {"cash": "-50.00"},
        )
        store.close()

        recovery = RecoveryManager(tmp_dirs["snapshot_dir"], store)
        result = recovery.boot()

        assert result.ready is False
        assert len(result.reason) > 0
