"""Order lifecycle tracking for BAET.

Orders are NOT instant fills. They have a lifecycle:
NEW → PARTIAL_FILL → FILLED
                   → CANCELLED
                   → REJECTED
                   → EXPIRED

Every state transition is an event.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any


class OrderStatus(StrEnum):
    NEW = "new"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


# Valid state transitions
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {
        OrderStatus.PARTIAL_FILL, OrderStatus.FILLED,
        OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED,
    },
    OrderStatus.PARTIAL_FILL: {
        OrderStatus.PARTIAL_FILL, OrderStatus.FILLED,
        OrderStatus.CANCELLED, OrderStatus.EXPIRED,
    },
    OrderStatus.FILLED: set(),  # Terminal
    OrderStatus.CANCELLED: set(),  # Terminal
    OrderStatus.REJECTED: set(),  # Terminal
    OrderStatus.EXPIRED: set(),  # Terminal
}


@dataclass
class Order:
    """Represents an order through its lifecycle."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None  # None for market orders
    stop_price: Decimal | None = None
    status: OrderStatus = OrderStatus.NEW
    client_order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    exchange_order_id: str | None = None
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal = Decimal("0")
    total_fee: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fills: list[FillEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            OrderStatus.FILLED, OrderStatus.CANCELLED,
            OrderStatus.REJECTED, OrderStatus.EXPIRED,
        }

    @property
    def is_active(self) -> bool:
        return self.status in {OrderStatus.NEW, OrderStatus.PARTIAL_FILL}

    def can_transition_to(self, new_status: OrderStatus) -> bool:
        """Check if a state transition is valid."""
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status: OrderStatus, reason: str = "") -> None:
        """Transition to a new status. Raises on invalid transition."""
        if not self.can_transition_to(new_status):
            raise OrderLifecycleError(
                f"Invalid transition: {self.status.value} → {new_status.value} "
                f"for order {self.client_order_id}"
            )
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

    def apply_fill(self, fill: FillEvent) -> None:
        """Apply a fill event to this order."""
        if self.is_terminal:
            raise OrderLifecycleError(
                f"Cannot fill terminal order {self.client_order_id} (status={self.status.value})"
            )

        self.fills.append(fill)
        old_filled = self.filled_quantity
        self.filled_quantity += fill.quantity

        # Update average fill price
        total_cost = self.average_fill_price * old_filled + fill.price * fill.quantity
        if self.filled_quantity > 0:
            self.average_fill_price = total_cost / self.filled_quantity

        self.total_fee += fill.fee
        self.updated_at = datetime.now(timezone.utc)

        # Auto-transition based on fill
        if self.filled_quantity >= self.quantity:
            self.transition_to(OrderStatus.FILLED)
        else:
            self.transition_to(OrderStatus.PARTIAL_FILL)

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price else None,
            "stop_price": str(self.stop_price) if self.stop_price else None,
            "filled_quantity": str(self.filled_quantity),
            "remaining_quantity": str(self.remaining_quantity),
            "average_fill_price": str(self.average_fill_price),
            "total_fee": str(self.total_fee),
            "fill_count": len(self.fills),
            "is_terminal": self.is_terminal,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class FillEvent:
    """Represents a single fill (partial or complete)."""
    fill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    fee: Decimal = Decimal("0")
    fee_asset: str = "USDT"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_maker: bool = False


class OrderLifecycleError(Exception):
    """Raised for invalid order lifecycle operations."""
    pass


class OrderTracker:
    """Tracks all orders and their lifecycle state."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}  # client_order_id → Order
        self._exchange_index: dict[str, str] = {}  # exchange_order_id → client_order_id

    def register(self, order: Order) -> None:
        """Register a new order."""
        self._orders[order.client_order_id] = order
        if order.exchange_order_id:
            self._exchange_index[order.exchange_order_id] = order.client_order_id

    def get(self, client_order_id: str) -> Order | None:
        return self._orders.get(client_order_id)

    def get_by_exchange_id(self, exchange_order_id: str) -> Order | None:
        client_id = self._exchange_index.get(exchange_order_id)
        if client_id:
            return self._orders.get(client_id)
        return None

    def get_active_orders(self, symbol: str | None = None) -> list[Order]:
        """Get all active (non-terminal) orders, optionally filtered by symbol."""
        orders = [o for o in self._orders.values() if o.is_active]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_all_orders(self) -> list[Order]:
        return list(self._orders.values())

    def get_open_order_count(self) -> int:
        return sum(1 for o in self._orders.values() if o.is_active)

    def summary(self) -> dict[str, Any]:
        """Return a summary of all tracked orders."""
        status_counts: dict[str, int] = {}
        for order in self._orders.values():
            status_counts[order.status.value] = status_counts.get(order.status.value, 0) + 1

        return {
            "total_orders": len(self._orders),
            "active_orders": self.get_open_order_count(),
            "terminal_orders": len(self._orders) - self.get_open_order_count(),
            "status_breakdown": status_counts,
        }
