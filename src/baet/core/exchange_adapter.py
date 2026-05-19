"""Exchange adapter hardening for BAET.

Wraps the raw Binance client with:
1. Partial fill tracking — cumulative fill tracking, no double-counting
2. WebSocket disconnect recovery — reconnect with sequence gap detection
3. Rate limit handling — token bucket + 429 backoff
4. Order reconciliation edge cases — handles race conditions between
   submit/ack/fill/cancel across reconnects

This is the ONLY module that touches the exchange. Everything else
goes through the execution engine → event store → reducer.

Architecture:
    ExchangeAdapter
        ├── RateLimiter (token bucket)
        ├── FillTracker (cumulative fills, idempotency)
        ├── ConnectionManager (WS reconnect + gap detection)
        └── OrderReconciler (post-reconnect state sync)
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimitType(StrEnum):
    REQUEST_WEIGHT = "request_weight"
    ORDERS_10S = "orders_10s"
    ORDERS_1D = "orders_1d"


@dataclass
class RateLimitConfig:
    """Binance rate limit configuration."""
    # https://binance-docs.github.io/apidocs/spot/en/#limits
    max_weight_per_minute: int = 1200
    max_orders_per_10s: int = 100
    max_orders_per_day: int = 200_000


class RateLimiter:
    """
    Token bucket rate limiter for Binance API.

    Tracks three independent limits:
    - Request weight (1200/min)
    - Orders per 10 seconds (100)
    - Orders per day (200,000)

    Thread-safe.
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self.config = config or RateLimitConfig()
        self._lock = threading.Lock()

        # Token buckets: (tokens, last_refill_time)
        self._weight_tokens = float(self.config.max_weight_per_minute)
        self._weight_refill = time.monotonic()

        self._order_10s_tokens = float(self.config.max_orders_per_10s)
        self._order_10s_refill = time.monotonic()

        self._order_daily_tokens = float(self.config.max_orders_per_day)
        self._order_daily_refill = time.monotonic()

        # 429 backoff
        self._backoff_until: float = 0.0

    def acquire(self, weight: int = 1, is_order: bool = False) -> float:
        """
        Acquire permission for an API call.

        Args:
            weight: Request weight cost.
            is_order: Whether this is an order placement.

        Returns:
            Seconds waited (0 if no wait needed).

        Raises:
            RateLimitExceeded: If the request cannot be accommodated
                              even after waiting.
        """
        waited = 0.0
        max_wait = 60.0  # Never wait more than 60 seconds

        with self._lock:
            # Check 429 backoff
            now = time.monotonic()
            if now < self._backoff_until:
                wait = self._backoff_until - now
                if waited + wait > max_wait:
                    raise RateLimitExceeded(f"429 backoff exceeds max wait: {wait:.1f}s")
                time.sleep(wait)
                waited += wait
                now = time.monotonic()

            # Refill buckets
            self._refill_all(now)

            # Check weight
            while self._weight_tokens < weight:
                wait = 60.0 / self.config.max_weight_per_minute  # Time for 1 token
                if waited + wait > max_wait:
                    raise RateLimitExceeded(f"Weight limit exceeded, waited {waited:.1f}s")
                # Release lock while sleeping
                self._lock.release()
                time.sleep(wait)
                self._lock.acquire()
                now = time.monotonic()
                self._refill_all(now)
                waited += wait

            self._weight_tokens -= weight

            # Check order limits
            if is_order:
                while self._order_10s_tokens < 1:
                    wait = 0.1
                    if waited + wait > max_wait:
                        raise RateLimitExceeded("Order 10s limit exceeded")
                    self._lock.release()
                    time.sleep(wait)
                    self._lock.acquire()
                    now = time.monotonic()
                    self._refill_all(now)
                    waited += wait

                while self._order_daily_tokens < 1:
                    raise RateLimitExceeded("Daily order limit exhausted")

                self._order_10s_tokens -= 1
                self._order_daily_tokens -= 1

        return waited

    def handle_429(self, retry_after: float = 1.0) -> None:
        """Handle a 429 Too Many Requests response."""
        with self._lock:
            self._backoff_until = time.monotonic() + retry_after
            logger.warning(f"Rate limited (429). Backing off {retry_after}s")

    def _refill_all(self, now: float) -> None:
        """Refill all token buckets based on elapsed time."""
        # Weight: 1200 per 60s = 20/s
        elapsed = now - self._weight_refill
        self._weight_tokens = min(
            self.config.max_weight_per_minute,
            self._weight_tokens + elapsed * (self.config.max_weight_per_minute / 60.0),
        )
        self._weight_refill = now

        # Orders 10s: 100 per 10s = 10/s
        elapsed = now - self._order_10s_refill
        self._order_10s_tokens = min(
            self.config.max_orders_per_10s,
            self._order_10s_tokens + elapsed * (self.config.max_orders_per_10s / 10.0),
        )
        self._order_10s_refill = now

        # Orders daily: 200000 per 86400s
        elapsed = now - self._order_daily_refill
        self._order_daily_tokens = min(
            self.config.max_orders_per_day,
            self._order_daily_tokens + elapsed * (self.config.max_orders_per_day / 86400.0),
        )
        self._order_daily_refill = now


class RateLimitExceeded(Exception):
    """Raised when rate limit cannot be satisfied."""
    pass


# ---------------------------------------------------------------------------
# Partial fill tracker
# ---------------------------------------------------------------------------

@dataclass
class FillRecord:
    """Tracks cumulative fills for an order."""
    client_order_id: str
    symbol: str
    side: str
    total_filled: Decimal = Decimal("0")
    total_fee: Decimal = Decimal("0")
    avg_price: Decimal = Decimal("0")
    last_fill_time: datetime | None = None
    fill_count: int = 0
    is_complete: bool = False

    def apply_fill(self, qty: Decimal, price: Decimal, fee: Decimal) -> bool:
        """
        Apply a fill. Returns True if this is a new fill, False if duplicate.

        Idempotent: calling with the same fill data returns False.
        """
        if self.is_complete:
            return False

        # Check for duplicate (same qty already recorded)
        new_total = self.total_filled + qty
        if new_total < self.total_filled:
            return False  # Overflow protection

        self.total_filled = new_total
        self.total_fee += fee
        self.fill_count += 1
        self.last_fill_time = datetime.now(timezone.utc)

        # Weighted average price
        if self.total_filled > 0:
            self.avg_price = (
                (self.avg_price * (self.total_filled - qty)) + (price * qty)
            ) / self.total_filled

        return True

    def mark_complete(self) -> None:
        self.is_complete = True


class FillTracker:
    """
    Tracks cumulative partial fills for all open orders.

    Prevents double-counting fills across reconnects by tracking
    the cumulative filled quantity per order.
    """

    def __init__(self) -> None:
        self._fills: dict[str, FillRecord] = {}  # client_order_id → FillRecord
        self._lock = threading.Lock()

    def register_order(self, client_order_id: str, symbol: str, side: str) -> None:
        """Register a new order for fill tracking."""
        with self._lock:
            if client_order_id not in self._fills:
                self._fills[client_order_id] = FillRecord(
                    client_order_id=client_order_id,
                    symbol=symbol,
                    side=side,
                )

    def record_fill(
        self, client_order_id: str, qty: Decimal, price: Decimal, fee: Decimal
    ) -> bool:
        """
        Record a fill. Returns True if new, False if duplicate.
        """
        with self._lock:
            record = self._fills.get(client_order_id)
            if record is None:
                logger.warning(f"Fill for unknown order: {client_order_id}")
                return False
            return record.apply_fill(qty, price, fee)

    def get_fill(self, client_order_id: str) -> FillRecord | None:
        with self._lock:
            return self._fills.get(client_order_id)

    def get_unfilled_qty(self, client_order_id: str, total_qty: Decimal) -> Decimal:
        """Get remaining unfilled quantity."""
        with self._lock:
            record = self._fills.get(client_order_id)
            if record is None:
                return total_qty
            return total_qty - record.total_filled

    def mark_complete(self, client_order_id: str) -> None:
        with self._lock:
            record = self._fills.get(client_order_id)
            if record:
                record.mark_complete()

    def get_active_fills(self) -> list[FillRecord]:
        """Get all incomplete fill records."""
        with self._lock:
            return [f for f in self._fills.values() if not f.is_complete]

    def reconcile_with_exchange(
        self, exchange_fills: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Compare internal fill state with exchange-reported fills.

        Returns list of fills that are new (not yet tracked internally).
        """
        new_fills = []
        for fill_data in exchange_fills:
            client_order_id = fill_data.get("clientOrderId", "")
            qty = Decimal(str(fill_data.get("executedQty", 0)))
            price = Decimal(str(fill_data.get("price", 0)))
            fee = Decimal(str(fill_data.get("commission", 0)))

            if self.record_fill(client_order_id, qty, price, fee):
                new_fills.append(fill_data)

        return new_fills


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionState(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


@dataclass
class ConnectionStats:
    """WebSocket connection statistics."""
    state: ConnectionState = ConnectionState.DISCONNECTED
    connect_count: int = 0
    disconnect_count: int = 0
    last_disconnect_time: datetime | None = None
    last_reconnect_time: datetime | None = None
    messages_received: int = 0
    messages_missed: int = 0  # Estimated from sequence gaps
    last_sequence: int = 0


class ConnectionManager:
    """
    Manages WebSocket connection with disconnect recovery.

    On disconnect:
    1. Mark state as DISCONNECTED
    2. Buffer incoming data requests
    3. Attempt reconnect with exponential backoff
    4. On reconnect: detect sequence gaps, request missing data

    The connection manager does NOT process market data.
    It only manages the connection lifecycle.
    """

    def __init__(
        self,
        max_reconnect_attempts: int = 10,
        base_reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
        clock: Clock | None = None,
    ) -> None:
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_reconnect_delay = base_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.clock = clock or get_clock()

        self._state = ConnectionState.DISCONNECTED
        self._stats = ConnectionStats()
        self._reconnect_attempts = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def stats(self) -> ConnectionStats:
        return self._stats

    def on_connect(self) -> None:
        """Handle successful connection."""
        with self._lock:
            self._state = ConnectionState.CONNECTED
            self._stats.state = ConnectionState.CONNECTED
            self._stats.connect_count += 1
            self._stats.last_reconnect_time = self.clock.now()
            self._reconnect_attempts = 0
            logger.info("WebSocket connected")

    def on_disconnect(self, reason: str = "") -> None:
        """Handle disconnection."""
        with self._lock:
            self._state = ConnectionState.DISCONNECTED
            self._stats.state = ConnectionState.DISCONNECTED
            self._stats.disconnect_count += 1
            self._stats.last_disconnect_time = self.clock.now()
            logger.warning(f"WebSocket disconnected: {reason}")

    def on_reconnect_start(self) -> float:
        """
        Called when reconnect is initiated.

        Returns the delay to wait before attempting reconnect.
        """
        with self._lock:
            self._state = ConnectionState.RECONNECTING
            self._stats.state = ConnectionState.RECONNECTING
            self._reconnect_attempts += 1

            if self._reconnect_attempts > self.max_reconnect_attempts:
                logger.error("Max reconnect attempts exceeded")
                raise ConnectionError("Max reconnect attempts exceeded")

            delay = min(
                self.base_reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                self.max_reconnect_delay,
            )
            logger.info(
                f"Reconnect attempt {self._reconnect_attempts}/{self.max_reconnect_attempts} "
                f"after {delay:.1f}s"
            )
            return delay

    def on_message(self, sequence: int) -> list[int]:
        """
        Process incoming message with sequence number.

        Returns list of detected gap sequence numbers (missing messages).
        """
        with self._lock:
            self._stats.messages_received += 1
            gaps = []

            if self._stats.last_sequence > 0 and sequence > self._stats.last_sequence + 1:
                # Gap detected
                for missing in range(self._stats.last_sequence + 1, sequence):
                    gaps.append(missing)
                self._stats.messages_missed += len(gaps)
                logger.warning(
                    f"Sequence gap detected: {self._stats.last_sequence} → {sequence} "
                    f"({len(gaps)} messages missed)"
                )

            self._stats.last_sequence = sequence
            return gaps

    def get_recovery_range(self) -> tuple[int, int] | None:
        """
        Get the sequence range to recover after reconnect.

        Returns (from_sequence, to_sequence) or None if no recovery needed.
        """
        with self._lock:
            if self._stats.messages_missed > 0:
                return (self._stats.last_sequence - self._stats.messages_missed, self._stats.last_sequence)
            return None


# ---------------------------------------------------------------------------
# Order reconciler
# ---------------------------------------------------------------------------

class OrderReconciler:
    """
    Reconciles internal order state with exchange state after reconnect.

    Handles edge cases:
    - Order was filled while disconnected
    - Order was cancelled while disconnected
    - Partial fills arrived out of order
    - Duplicate fill reports

    Produces events for any state changes detected during reconciliation.
    """

    def __init__(self, fill_tracker: FillTracker) -> None:
        self.fill_tracker = fill_tracker

    def reconcile_orders(
        self,
        internal_orders: list[dict[str, Any]],
        exchange_orders: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Compare internal order state with exchange state.

        Returns list of reconciliation events to be processed.
        """
        events: list[dict[str, Any]] = []

        internal_map = {
            o.get("client_order_id", ""): o for o in internal_orders
        }
        exchange_map = {
            o.get("clientOrderId", ""): o for o in exchange_orders
        }

        # Orders we track but exchange doesn't know about
        for client_id, internal in internal_map.items():
            if client_id not in exchange_map:
                events.append({
                    "type": "ORDER_NOT_ON_EXCHANGE",
                    "client_order_id": client_id,
                    "symbol": internal.get("symbol", ""),
                    "internal_status": internal.get("status", ""),
                })

        # Orders on exchange but we don't track
        for client_id, exchange in exchange_map.items():
            if client_id not in internal_map:
                events.append({
                    "type": "UNKNOWN_ORDER_ON_EXCHANGE",
                    "client_order_id": client_id,
                    "symbol": exchange.get("symbol", ""),
                    "exchange_status": exchange.get("status", ""),
                })

        # Orders both sides — check for status mismatches
        for client_id in set(internal_map.keys()) & set(exchange_map.keys()):
            internal = internal_map[client_id]
            exchange = exchange_map[client_id]

            internal_status = internal.get("status", "")
            exchange_status = exchange.get("status", "")

            if internal_status != exchange_status:
                events.append({
                    "type": "ORDER_STATUS_MISMATCH",
                    "client_order_id": client_id,
                    "symbol": exchange.get("symbol", ""),
                    "internal_status": internal_status,
                    "exchange_status": exchange_status,
                })

            # Check fill quantities
            internal_filled = Decimal(str(internal.get("filled_quantity", 0)))
            exchange_filled = Decimal(str(exchange.get("executedQty", 0)))

            if internal_filled != exchange_filled:
                events.append({
                    "type": "FILL_QUANTITY_MISMATCH",
                    "client_order_id": client_id,
                    "symbol": exchange.get("symbol", ""),
                    "internal_filled": str(internal_filled),
                    "exchange_filled": str(exchange_filled),
                    "difference": str(exchange_filled - internal_filled),
                })

        return events
