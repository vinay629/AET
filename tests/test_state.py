"""Tests for durable portfolio state."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from baet.core.events import Event, EventStore, EventType
from baet.core.state import PortfolioState, TradeRecord


class TestPortfolioState:
    def test_default_state(self) -> None:
        state = PortfolioState()
        assert state.cash == Decimal("10000.0")
        assert state.positions == {}
        assert state.trades == []

    def test_apply_buy_fill(self) -> None:
        state = PortfolioState()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.ORDER_FILLED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="test",
            payload={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "price": 68000.0,
                "units": 0.01,
                "fee": 0.68,
                "timestamp": ts.isoformat(),
            },
        )
        state.apply(event)
        assert "BTCUSDT" in state.positions
        assert state.positions["BTCUSDT"]["units"] == Decimal("0.01")
        assert state.cash < Decimal("10000.0")
        assert len(state.trades) == 1

    def test_apply_sell_fill(self) -> None:
        state = PortfolioState()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)

        # Buy first
        buy_event = Event(
            event_type=EventType.ORDER_FILLED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="test",
            payload={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "price": 68000.0,
                "units": 0.01,
                "fee": 0.68,
                "timestamp": ts.isoformat(),
            },
        )
        state.apply(buy_event)

        # Then sell
        sell_event = Event(
            event_type=EventType.ORDER_FILLED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=2,
            source="test",
            payload={
                "symbol": "BTCUSDT",
                "side": "SELL",
                "price": 69000.0,
                "units": 0.01,
                "fee": 0.69,
                "timestamp": ts.isoformat(),
            },
        )
        state.apply(sell_event)
        assert "BTCUSDT" not in state.positions  # Position closed
        assert len(state.trades) == 2

    def test_from_events_reconstructs_state(self) -> None:
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        events = [
            Event(
                event_type=EventType.ORDER_FILLED,
                timestamp_exchange=ts,
                timestamp_local=ts,
                sequence=1,
                source="test",
                payload={
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "price": 68000.0,
                    "units": 0.01,
                    "fee": 0.68,
                    "timestamp": ts.isoformat(),
                },
            ),
        ]
        state = PortfolioState.from_events(events)
        assert "BTCUSDT" in state.positions
        assert state.positions["BTCUSDT"]["units"] == Decimal("0.01")

    def test_from_journal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = EventStore(base_dir=Path(tmp))
            ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
            store.append(
                EventType.ORDER_FILLED,
                ts,
                "test",
                {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "price": 68000.0,
                    "units": 0.01,
                    "fee": 0.68,
                    "timestamp": ts.isoformat(),
                },
            )
            store.close()

            state = PortfolioState.from_journal(store, "2026-05-17")
            assert "BTCUSDT" in state.positions

    def test_verify_invariants_ok(self) -> None:
        state = PortfolioState()
        violations = state.verify_invariants()
        assert violations == []

    def test_verify_invariants_negative_cash(self) -> None:
        state = PortfolioState()
        state.cash = Decimal("-100")
        violations = state.verify_invariants()
        assert len(violations) == 1
        assert "negative" in violations[0].lower()

    def test_snapshot(self) -> None:
        state = PortfolioState()
        snapshot = state.snapshot()
        assert "cash" in snapshot
        assert "positions" in snapshot
        assert "timestamp" in snapshot

    def test_total_equity_no_positions(self) -> None:
        state = PortfolioState(cash=Decimal("5000"))
        assert state.total_equity() == Decimal("5000")

    def test_total_equity_with_prices(self) -> None:
        state = PortfolioState(cash=Decimal("3200"))
        state.positions["BTCUSDT"] = {
            "units": Decimal("0.01"),
            "avg_price": Decimal("68000"),
        }
        equity = state.total_equity({"BTCUSDT": Decimal("69000")})
        assert equity == Decimal("3200") + Decimal("0.01") * Decimal("69000")


class TestStatePersistence:
    def test_save_and_load_snapshot(self) -> None:
        state = PortfolioState(cash=Decimal("9320.32"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            from baet.core.state import save_snapshot, load_snapshot
            save_snapshot(state, path)
            loaded = load_snapshot(path)
            assert loaded["cash"] == "9320.32"
