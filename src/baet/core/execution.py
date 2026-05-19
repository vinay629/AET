"""Execution engine for BAET.

The execution engine is an event producer. It:
1. Receives intent (submit/cancel/query)
2. Communicates with the exchange (or simulator)
3. Produces events that go through the reducer

It NEVER mutates PortfolioState directly. All state changes
flow through the event journal → reducer → new state.

Order lifecycle:
    SUBMITTED → ACKNOWLEDGED → PARTIALLY_FILLED → FILLED
                                          → CANCELLED
                                          → REJECTED
                                          → EXPIRED

Client order IDs are deterministic: they are derived from
(symbol, side, price, timestamp, nonce) so that retries
produce the same ID — making submission idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from baet.core.clock import Clock, get_clock
from baet.core.events import Event, EventStore, EventType
from baet.core.invariants import InvariantError, check_invariants
from baet.core.orders import Order, OrderSide, OrderStatus, OrderType, FillEvent
from baet.core.reducer import reduce_state
from baet.core.state import PortfolioState

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Raised when order execution fails."""
    pass


class OrderTimeoutError(ExecutionError):
    """Raised when an order exceeds its timeout."""
    pass


# ---------------------------------------------------------------------------
# Exchange protocol — what the execution engine needs from an exchange
# ---------------------------------------------------------------------------

class ExchangeGateway(Protocol):
    """Minimal interface the execution engine needs.

    Implement this for live Binance, testnet, or paper simulation.
    """

    def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> dict[str, Any]: ...

    def cancel_order(
        self, client_order_id: str, symbol: str
    ) -> dict[str, Any]: ...

    def query_order(
        self, client_order_id: str, symbol: str
    ) -> dict[str, Any]: ...

    def get_fills(
        self, client_order_id: str, symbol: str
    ) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

class RetryPolicy:
    """Configurable retry policy for exchange operations."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_ms: float = 500,
        max_delay_ms: float = 5000,
        backoff_factor: float = 2.0,
        retryable_status_codes: set[int] | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_factor = backoff_factor
        self.retryable_status_codes = retryable_status_codes or {-1021, -2010, -2011, -2013, -2015}

    def get_delay_ms(self, attempt: int) -> float:
        """Calculate delay before retry attempt (exponential backoff)."""
        delay = self.base_delay_ms * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay_ms)

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if the operation should be retried."""
        if attempt >= self.max_retries:
            return False
        # Retry on timeout, connection errors, and specific API codes
        if isinstance(error, (TimeoutError, ConnectionError)):
            return True
        # Check for Binance API error codes
        if hasattr(error, "code") and error.code in self.retryable_status_codes:
            return True
        return False


# ---------------------------------------------------------------------------
# Client order ID generation — deterministic and idempotent
# ---------------------------------------------------------------------------

def make_client_order_id(
    symbol: str,
    side: str,
    price: Decimal | None,
    timestamp: datetime,
    nonce: int = 0,
) -> str:
    """Generate a deterministic, idempotent client order ID.

    Same inputs → same ID. This means retrying a submission
    with the same parameters produces the same client_order_id,
    which the exchange will recognize as a duplicate.

    Format: baet-<hash[:16]>

    Args:
        symbol: Trading pair (e.g., "BTCUSDT").
        side: "BUY" or "SELL".
        price: Limit price, or None for market orders.
        timestamp: Exchange timestamp of the signal.
        nonce: Incremental counter for multiple orders at same ts.
    """
    parts = f"{symbol}:{side}:{price}:{timestamp.isoformat()}:{nonce}"
    digest = hashlib.sha256(parts.encode()).hexdigest()[:16]
    return f"baet-{digest}"


# ---------------------------------------------------------------------------
# Execution Engine
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """Result of an execution operation."""
    success: bool
    events: list[Event]
    error: str = ""
    order_id: str | None = None


class ExecutionEngine:
    """
    Produces events from exchange operations.

    This is the ONLY component that communicates with the exchange.
    It translates exchange responses into events that flow through
    the reducer. It never touches PortfolioState directly.

    All public methods return ExecutionResult with events that
    should be appended to the event store and reduced into state.
    """

    def __init__(
        self,
        event_store: EventStore,
        gateway: ExchangeGateway,
        retry_policy: RetryPolicy | None = None,
        clock: Clock | None = None,
        order_timeout_seconds: float = 30.0,
    ) -> None:
        self.event_store = event_store
        self.gateway = gateway
        self.retry_policy = retry_policy or RetryPolicy()
        self.clock = clock or get_clock()
        self.order_timeout_seconds = order_timeout_seconds
        self._pending_cancels: dict[str, datetime] = {}  # client_order_id → cancel_ts
        self._submitted_ids: set[str] = set()  # client_order_ids already submitted

    # ------------------------------------------------------------------
    # Submit order
    # ------------------------------------------------------------------

    def submit_order(
        self,
        state: PortfolioState,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
        nonce: int = 0,
    ) -> ExecutionResult:
        """
        Submit an order to the exchange.

        Flow:
            1. Generate deterministic client_order_id
            2. Submit to exchange (with retries)
            3. Produce ORDER_SUBMITTED event
            4. Query acknowledgment → ORDER_ACKNOWLEDGED event
            5. Reduce events into state + check invariants

        Args:
            state: Current portfolio state (for invariant checks).
            symbol: Trading pair.
            side: "BUY" or "SELL".
            order_type: "MARKET", "LIMIT", etc.
            quantity: Order quantity.
            price: Limit price (None for market orders).
            nonce: Unique counter for this signal timestamp.

        Returns:
            ExecutionResult with events to append to the journal.
        """
        events: list[Event] = []
        ts = self.clock.now()

        # Generate deterministic client order ID
        client_order_id = make_client_order_id(symbol, side, price, ts, nonce)

        # Check if this order was already submitted (idempotency)
        if client_order_id in self._submitted_ids:
            logger.info(f"Order {client_order_id} already submitted — skipping")
            return ExecutionResult(success=True, events=[], order_id=client_order_id)

        # Submit to exchange with retries
        exchange_response = self._retry_operation(
            lambda: self.gateway.submit_order(
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
            ),
            operation_name=f"submit_order({symbol}, {side})",
        )

        if exchange_response is None:
            error_msg = f"Failed to submit order after {self.retry_policy.max_retries} retries"
            logger.error(error_msg)
            return ExecutionResult(success=False, events=[], error=error_msg)

        exchange_order_id = exchange_response.get("orderId", "")

        # Produce ORDER_SUBMITTED event
        submitted_event = self.event_store.append(
            event_type=EventType.ORDER_SUBMITTED,
            timestamp_exchange=ts,
            source="execution_engine",
            payload={
                "client_order_id": client_order_id,
                "exchange_order_id": str(exchange_order_id),
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "quantity": str(quantity),
                "price": str(price) if price else None,
            },
            clock=self.clock,
        )
        events.append(submitted_event)

        # Produce ORDER_ACKNOWLEDGED event (if exchange confirmed)
        status = exchange_response.get("status", "")
        if status in ("NEW", "PARTIALLY_FILLED", "FILLED"):
            ack_event = self.event_store.append(
                event_type=EventType.ORDER_SUBMITTED,  # Reuse — acknowledged = submitted confirmed
                timestamp_exchange=ts,
                source="execution_engine",
                payload={
                    "client_order_id": client_order_id,
                    "exchange_order_id": str(exchange_order_id),
                    "status": status,
                    "acknowledged": True,
                },
                clock=self.clock,
            )
            events.append(ack_event)

        # If immediately filled (market orders), produce fill events
        if status == "FILLED" or exchange_response.get("executedQty", 0):
            fills = self._poll_fills(client_order_id, symbol, ts)
            events.extend(fills)

        # Track this order as submitted (idempotency)
        self._submitted_ids.add(client_order_id)

        # Reduce events into new state + check invariants
        new_state = state
        for event in events:
            new_state = reduce_state(new_state, event)

        try:
            for event in events:
                check_invariants(state, new_state, event, clock=self.clock)
        except InvariantError as e:
            logger.error(f"Invariant violation after submit: {e}")
            return ExecutionResult(
                success=False,
                events=events,
                error=f"Invariant violation: {e}",
                order_id=client_order_id,
            )

        return ExecutionResult(
            success=True,
            events=events,
            order_id=client_order_id,
        )

    # ------------------------------------------------------------------
    # Cancel order
    # ------------------------------------------------------------------

    def cancel_order(
        self,
        state: PortfolioState,
        client_order_id: str,
        symbol: str,
    ) -> ExecutionResult:
        """
        Cancel an open order.

        Flow:
            1. Send cancel to exchange (with retries)
            2. Produce ORDER_CANCELLED event
            3. Reduce + check invariants
        """
        events: list[Event] = []
        ts = self.clock.now()

        response = self._retry_operation(
            lambda: self.gateway.cancel_order(client_order_id, symbol),
            operation_name=f"cancel_order({client_order_id})",
        )

        if response is None:
            return ExecutionResult(
                success=False,
                events=[],
                error=f"Failed to cancel order {client_order_id}",
            )

        cancelled_event = self.event_store.append(
            event_type=EventType.ORDER_CANCELLED,
            timestamp_exchange=ts,
            source="execution_engine",
            payload={
                "client_order_id": client_order_id,
                "symbol": symbol,
                "exchange_response": str(response),
            },
            clock=self.clock,
        )
        events.append(cancelled_event)

        # Reduce + check invariants
        new_state = state
        for event in events:
            new_state = reduce_state(new_state, event)

        try:
            for event in events:
                check_invariants(state, new_state, event, clock=self.clock)
        except InvariantError as e:
            logger.error(f"Invariant violation after cancel: {e}")
            return ExecutionResult(
                success=False, events=events, error=str(e),
            )

        return ExecutionResult(success=True, events=events, order_id=client_order_id)

    # ------------------------------------------------------------------
    # Poll fills (for checking partial/complete fills)
    # ------------------------------------------------------------------

    def poll_fills(
        self,
        state: PortfolioState,
        client_order_id: str,
        symbol: str,
    ) -> ExecutionResult:
        """
        Poll the exchange for fills on an open order.

        Produces ORDER_PARTIAL_FILL and/or ORDER_FILLED events.
        """
        events: list[Event] = []
        ts = self.clock.now()

        fills = self._poll_fills(client_order_id, symbol, ts)
        events.extend(fills)

        # Reduce + check invariants
        new_state = state
        for event in events:
            new_state = reduce_state(new_state, event)

        try:
            for event in events:
                check_invariants(state, new_state, event, clock=self.clock)
        except InvariantError as e:
            logger.error(f"Invariant violation after poll: {e}")
            return ExecutionResult(
                success=False, events=events, error=str(e),
            )

        return ExecutionResult(success=True, events=events, order_id=client_order_id)

    # ------------------------------------------------------------------
    # Timeout check — call periodically for open orders
    # ------------------------------------------------------------------

    def check_timeouts(
        self,
        state: PortfolioState,
        open_orders: list[Order],
    ) -> ExecutionResult:
        """
        Check for orders that have exceeded the timeout.

        For each timed-out order:
            1. Attempt to cancel on exchange
            2. Produce ORDER_EXPIRED event
        """
        events: list[Event] = []
        ts = self.clock.now()

        for order in open_orders:
            if order.is_terminal:
                continue
            age_seconds = (ts - order.created_at).total_seconds()
            if age_seconds > self.order_timeout_seconds:
                logger.warning(
                    f"Order {order.client_order_id} timed out "
                    f"({age_seconds:.0f}s > {self.order_timeout_seconds}s)"
                )
                # Try to cancel
                try:
                    self.gateway.cancel_order(order.client_order_id, order.symbol)
                except Exception:
                    pass  # Best effort

                expired_event = self.event_store.append(
                    event_type=EventType.ORDER_EXPIRED,
                    timestamp_exchange=ts,
                    source="execution_engine",
                    payload={
                        "client_order_id": order.client_order_id,
                        "symbol": order.symbol,
                        "age_seconds": age_seconds,
                    },
                    clock=self.clock,
                )
                events.append(expired_event)

        # Reduce + check invariants
        new_state = state
        for event in events:
            new_state = reduce_state(new_state, event)

        try:
            for event in events:
                check_invariants(state, new_state, event, clock=self.clock)
        except InvariantError as e:
            return ExecutionResult(success=False, events=events, error=str(e))

        return ExecutionResult(success=True, events=events)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _retry_operation(
        self,
        operation: callable,
        operation_name: str = "operation",
    ) -> Any | None:
        """Execute an operation with retries."""
        last_error: Exception | None = None

        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                return operation()
            except Exception as e:
                last_error = e
                if not self.retry_policy.should_retry(e, attempt):
                    logger.error(
                        f"{operation_name} failed (attempt {attempt + 1}): {e}"
                    )
                    break
                delay_ms = self.retry_policy.get_delay_ms(attempt)
                logger.warning(
                    f"{operation_name} retry {attempt + 1}/{self.retry_policy.max_retries} "
                    f"after {delay_ms:.0f}ms: {e}"
                )
                time.sleep(delay_ms / 1000.0)

        logger.error(f"{operation_name} exhausted retries: {last_error}")
        return None

    def _poll_fills(
        self,
        client_order_id: str,
        symbol: str,
        ts: datetime,
    ) -> list[Event]:
        """Poll exchange for fills and produce events."""
        events: list[Event] = []

        try:
            fills = self.gateway.get_fills(client_order_id, symbol)
        except Exception as e:
            logger.warning(f"Failed to poll fills for {client_order_id}: {e}")
            return events

        for fill_data in fills:
            fill_qty = Decimal(str(fill_data.get("qty", 0)))
            fill_price = Decimal(str(fill_data.get("price", 0)))
            fill_fee = Decimal(str(fill_data.get("commission", 0)))
            fee_asset = fill_data.get("commissionAsset", "USDT")
            is_maker = fill_data.get("isMaker", False)

            # Determine if this is a partial or complete fill
            # (we'd need to track cumulative fills — simplified here)
            event_type = EventType.ORDER_PARTIAL_FILL

            fill_event = self.event_store.append(
                event_type=event_type,
                timestamp_exchange=ts,
                source="execution_engine",
                payload={
                    "client_order_id": client_order_id,
                    "symbol": symbol,
                    "fill_qty": str(fill_qty),
                    "fill_price": str(fill_price),
                    "fee": str(fill_fee),
                    "fee_asset": fee_asset,
                    "is_maker": is_maker,
                },
                clock=self.clock,
            )
            events.append(fill_event)

            # Also produce ORDER_FILLED for the reducer to process
            # (the reducer only handles ORDER_FILLED events)
            side = fill_data.get("side", "BUY")
            filled_event = self.event_store.append(
                event_type=EventType.ORDER_FILLED,
                timestamp_exchange=ts,
                source="execution_engine",
                payload={
                    "symbol": symbol,
                    "side": side,
                    "price": str(fill_price),
                    "units": str(fill_qty),
                    "fee": str(fill_fee),
                    "timestamp": ts.isoformat(),
                    "client_order_id": client_order_id,
                },
                clock=self.clock,
            )
            events.append(filled_event)

        return events
