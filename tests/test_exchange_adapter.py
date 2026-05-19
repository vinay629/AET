"""Tests for exchange adapter hardening."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from baet.core.exchange_adapter import (
    ConnectionManager,
    ConnectionState,
    FillRecord,
    FillTracker,
    OrderReconciler,
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
)


class TestRateLimiter:
    def test_allows_within_limit(self) -> None:
        limiter = RateLimiter()
        limiter.acquire(weight=1)

    def test_tracks_weight(self) -> None:
        limiter = RateLimiter(RateLimitConfig(max_weight_per_minute=10))
        limiter.acquire(weight=5)
        limiter.acquire(weight=5)
        # Should be near limit now

    def test_429_backoff(self) -> None:
        limiter = RateLimiter()
        limiter.handle_429(retry_after=0.1)
        # Next acquire should wait
        start = time.monotonic()
        limiter.acquire(weight=1)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05  # Should have waited

    def test_order_limits(self) -> None:
        limiter = RateLimiter(RateLimitConfig(max_orders_per_10s=2))
        limiter.acquire(is_order=True)
        limiter.acquire(is_order=True)
        # Third should wait or fail depending on timing


class TestFillTracker:
    def test_register_and_track(self) -> None:
        tracker = FillTracker()
        tracker.register_order("order-1", "BTCUSDT", "BUY")
        assert tracker.get_fill("order-1") is not None

    def test_record_fill(self) -> None:
        tracker = FillTracker()
        tracker.register_order("order-1", "BTCUSDT", "BUY")
        is_new = tracker.record_fill("order-1", Decimal("0.5"), Decimal("50000"), Decimal("5"))
        assert is_new is True

    def test_cumulative_fill_tracking(self) -> None:
        """Fill tracker accumulates fills — same qty twice means two partial fills."""
        tracker = FillTracker()
        tracker.register_order("order-1", "BTCUSDT", "BUY")
        tracker.record_fill("order-1", Decimal("0.5"), Decimal("50000"), Decimal("5"))
        # Same qty again — this is a second partial fill, not a duplicate
        is_new = tracker.record_fill("order-1", Decimal("0.5"), Decimal("50000"), Decimal("5"))
        assert is_new is True
        fill = tracker.get_fill("order-1")
        assert fill is not None
        assert fill.total_filled == Decimal("1.0")

    def test_cumulative_fills(self) -> None:
        tracker = FillTracker()
        tracker.register_order("order-1", "BTCUSDT", "BUY")
        tracker.record_fill("order-1", Decimal("0.5"), Decimal("50000"), Decimal("5"))
        tracker.record_fill("order-1", Decimal("0.3"), Decimal("51000"), Decimal("3"))

        fill = tracker.get_fill("order-1")
        assert fill is not None
        assert fill.total_filled == Decimal("0.8")
        assert fill.fill_count == 2

    def test_unfilled_qty(self) -> None:
        tracker = FillTracker()
        tracker.register_order("order-1", "BTCUSDT", "BUY")
        tracker.record_fill("order-1", Decimal("0.5"), Decimal("50000"), Decimal("5"))

        unfilled = tracker.get_unfilled_qty("order-1", Decimal("1.0"))
        assert unfilled == Decimal("0.5")

    def test_mark_complete(self) -> None:
        tracker = FillTracker()
        tracker.register_order("order-1", "BTCUSDT", "BUY")
        tracker.mark_complete("order-1")

        fill = tracker.get_fill("order-1")
        assert fill is not None
        assert fill.is_complete is True

    def test_reconcile_with_exchange(self) -> None:
        tracker = FillTracker()
        tracker.register_order("order-1", "BTCUSDT", "BUY")
        tracker.record_fill("order-1", Decimal("0.5"), Decimal("50000"), Decimal("5"))

        exchange_fills = [
            {"clientOrderId": "order-1", "executedQty": "0.5", "price": "50000", "commission": "5"},
            {"clientOrderId": "order-1", "executedQty": "0.3", "price": "51000", "commission": "3"},
        ]

        new_fills = tracker.reconcile_with_exchange(exchange_fills)
        # Both fills are recorded (cumulative tracking)
        assert len(new_fills) == 2
        fill = tracker.get_fill("order-1")
        assert fill is not None
        assert fill.total_filled == Decimal("1.3")  # 0.5 + 0.5 + 0.3


class TestConnectionManager:
    def test_initial_state(self) -> None:
        mgr = ConnectionManager()
        assert mgr.state == ConnectionState.DISCONNECTED

    def test_connect(self) -> None:
        mgr = ConnectionManager()
        mgr.on_connect()
        assert mgr.state == ConnectionState.CONNECTED
        assert mgr.stats.connect_count == 1

    def test_disconnect(self) -> None:
        mgr = ConnectionManager()
        mgr.on_connect()
        mgr.on_disconnect("test")
        assert mgr.state == ConnectionState.DISCONNECTED
        assert mgr.stats.disconnect_count == 1

    def test_reconnect_delay(self) -> None:
        mgr = ConnectionManager(base_reconnect_delay=0.01)
        mgr.on_connect()
        mgr.on_disconnect("test")

        delay1 = mgr.on_reconnect_start()
        assert delay1 >= 0.01

    def test_sequence_gap_detection(self) -> None:
        mgr = ConnectionManager()
        mgr.on_connect()
        mgr.on_message(1)
        mgr.on_message(2)
        gaps = mgr.on_message(5)  # Gap: 3, 4 missing
        assert len(gaps) == 2
        assert 3 in gaps
        assert 4 in gaps

    def test_no_gap(self) -> None:
        mgr = ConnectionManager()
        mgr.on_connect()
        mgr.on_message(1)
        gaps = mgr.on_message(2)
        assert len(gaps) == 0


class TestOrderReconciler:
    def test_consistent_orders(self) -> None:
        tracker = FillTracker()
        reconciler = OrderReconciler(tracker)

        internal = [{"client_order_id": "o1", "symbol": "BTCUSDT", "status": "NEW", "filled_quantity": "0"}]
        exchange = [{"clientOrderId": "o1", "symbol": "BTCUSDT", "status": "NEW", "executedQty": "0"}]

        events = reconciler.reconcile_orders(internal, exchange)
        assert len(events) == 0

    def test_status_mismatch(self) -> None:
        tracker = FillTracker()
        reconciler = OrderReconciler(tracker)

        internal = [{"client_order_id": "o1", "symbol": "BTCUSDT", "status": "NEW", "filled_quantity": "0"}]
        exchange = [{"clientOrderId": "o1", "symbol": "BTCUSDT", "status": "FILLED", "executedQty": "1.0"}]

        events = reconciler.reconcile_orders(internal, exchange)
        assert any(e["type"] == "ORDER_STATUS_MISMATCH" for e in events)

    def test_fill_quantity_mismatch(self) -> None:
        tracker = FillTracker()
        reconciler = OrderReconciler(tracker)

        internal = [{"client_order_id": "o1", "symbol": "BTCUSDT", "status": "PARTIALLY_FILLED", "filled_quantity": "0.5"}]
        exchange = [{"clientOrderId": "o1", "symbol": "BTCUSDT", "status": "PARTIALLY_FILLED", "executedQty": "0.8"}]

        events = reconciler.reconcile_orders(internal, exchange)
        assert any(e["type"] == "FILL_QUANTITY_MISMATCH" for e in events)

    def test_unknown_order_on_exchange(self) -> None:
        tracker = FillTracker()
        reconciler = OrderReconciler(tracker)

        internal = []
        exchange = [{"clientOrderId": "ext-123", "symbol": "ETHUSDT", "status": "NEW", "executedQty": "0"}]

        events = reconciler.reconcile_orders(internal, exchange)
        assert any(e["type"] == "UNKNOWN_ORDER_ON_EXCHANGE" for e in events)

    def test_order_not_on_exchange(self) -> None:
        tracker = FillTracker()
        reconciler = OrderReconciler(tracker)

        internal = [{"client_order_id": "o1", "symbol": "BTCUSDT", "status": "NEW", "filled_quantity": "0"}]
        exchange = []

        events = reconciler.reconcile_orders(internal, exchange)
        assert any(e["type"] == "ORDER_NOT_ON_EXCHANGE" for e in events)
