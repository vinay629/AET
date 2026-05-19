"""Tests for order lifecycle tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from baet.core.orders import (
    FillEvent,
    Order,
    OrderLifecycleError,
    OrderSide,
    OrderStatus,
    OrderTracker,
    OrderType,
)


class TestOrder:
    def test_create_order(self) -> None:
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            price=Decimal("68000"),
        )
        assert order.status == OrderStatus.NEW
        assert order.is_active
        assert not order.is_terminal
        assert order.remaining_quantity == Decimal("0.01")

    def test_fill_transitions_to_filled(self) -> None:
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
        )
        fill = FillEvent(
            order_id=order.client_order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price=Decimal("68000"),
            quantity=Decimal("0.01"),
            fee=Decimal("0.68"),
        )
        order.apply_fill(fill)
        assert order.status == OrderStatus.FILLED
        assert order.is_terminal
        assert not order.is_active
        assert order.filled_quantity == Decimal("0.01")

    def test_partial_fill(self) -> None:
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.02"),
            price=Decimal("68000"),
        )
        fill = FillEvent(
            order_id=order.client_order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price=Decimal("68000"),
            quantity=Decimal("0.01"),
            fee=Decimal("0.34"),
        )
        order.apply_fill(fill)
        assert order.status == OrderStatus.PARTIAL_FILL
        assert order.is_active
        assert order.remaining_quantity == Decimal("0.01")

    def test_invalid_transition_raises(self) -> None:
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
        )
        # Fill the order
        fill = FillEvent(
            order_id=order.client_order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            price=Decimal("68000"),
            quantity=Decimal("0.01"),
            fee=Decimal("0.68"),
        )
        order.apply_fill(fill)

        # Try to fill again — should raise
        with pytest.raises(OrderLifecycleError):
            order.apply_fill(fill)

    def test_to_dict(self) -> None:
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            price=Decimal("68000"),
        )
        d = order.to_dict()
        assert d["symbol"] == "BTCUSDT"
        assert d["status"] == "new"
        assert d["is_terminal"] is False
        assert d["fill_count"] == 0


class TestOrderTracker:
    def test_register_and_get(self) -> None:
        tracker = OrderTracker()
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
        )
        tracker.register(order)
        retrieved = tracker.get(order.client_order_id)
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"

    def test_get_active_orders(self) -> None:
        tracker = OrderTracker()
        order1 = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
        )
        order2 = Order(
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.1"),
        )
        tracker.register(order1)
        tracker.register(order2)

        active = tracker.get_active_orders()
        assert len(active) == 2

        btc_active = tracker.get_active_orders(symbol="BTCUSDT")
        assert len(btc_active) == 1

    def test_summary(self) -> None:
        tracker = OrderTracker()
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
        )
        tracker.register(order)
        summary = tracker.summary()
        assert summary["total_orders"] == 1
        assert summary["active_orders"] == 1
