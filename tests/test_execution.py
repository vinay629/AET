"""Tests for the execution engine."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from baet.core.clock import Clock, set_clock, reset_clock
from baet.core.events import EventStore, EventType
from baet.core.execution import (
    ExecutionEngine,
    ExecutionResult,
    RetryPolicy,
    make_client_order_id,
)
from baet.core.invariants import InvariantError
from baet.core.orders import Order, OrderSide, OrderStatus, OrderType
from baet.core.state import PortfolioState


class FakeGateway:
    """Fake exchange gateway for testing."""

    def __init__(
        self,
        fill_immediately: bool = True,
        reject: bool = False,
        fail_count: int = 0,
    ) -> None:
        self.fill_immediately = fill_immediately
        self.reject = reject
        self.fail_count = fail_count
        self._call_count = 0
        self.submitted_orders: list[dict] = []

    def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> dict[str, Any]:
        self._call_count += 1
        if self._call_count <= self.fail_count:
            raise ConnectionError("Simulated connection failure")

        self.submitted_orders.append({
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
        })

        if self.reject:
            return {"status": "REJECTED", "orderId": ""}

        status = "FILLED" if self.fill_immediately else "NEW"
        return {
            "orderId": f"ex-{client_order_id[:8]}",
            "status": status,
            "executedQty": str(quantity) if self.fill_immediately else "0",
        }

    def cancel_order(self, client_order_id: str, symbol: str) -> dict[str, Any]:
        return {"status": "CANCELLED", "orderId": f"ex-{client_order_id[:8]}"}

    def query_order(self, client_order_id: str, symbol: str) -> dict[str, Any]:
        return {"status": "NEW", "orderId": f"ex-{client_order_id[:8]}"}

    def get_fills(self, client_order_id: str, symbol: str) -> list[dict[str, Any]]:
        return []


TEST_TS = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def env(tmp_path):
    event_dir = tmp_path / "events"
    event_dir.mkdir()
    set_clock(Clock.fixed(TEST_TS))
    store = EventStore(event_dir)
    gateway = FakeGateway(fill_immediately=False)
    engine = ExecutionEngine(
        event_store=store,
        gateway=gateway,
        retry_policy=RetryPolicy(max_retries=2, base_delay_ms=10),
        clock=Clock.fixed(TEST_TS),
    )
    state = PortfolioState()
    yield {
        "store": store,
        "gateway": gateway,
        "engine": engine,
        "state": state,
    }
    store.close()
    reset_clock()


class TestClientOrderId:
    def test_deterministic(self) -> None:
        id1 = make_client_order_id("BTCUSDT", "BUY", Decimal("50000"), TEST_TS, 0)
        id2 = make_client_order_id("BTCUSDT", "BUY", Decimal("50000"), TEST_TS, 0)
        assert id1 == id2

    def test_different_inputs_different_ids(self) -> None:
        id1 = make_client_order_id("BTCUSDT", "BUY", Decimal("50000"), TEST_TS, 0)
        id2 = make_client_order_id("BTCUSDT", "BUY", Decimal("51000"), TEST_TS, 0)
        assert id1 != id2

    def test_different_nonce_different_ids(self) -> None:
        id1 = make_client_order_id("BTCUSDT", "BUY", Decimal("50000"), TEST_TS, 0)
        id2 = make_client_order_id("BTCUSDT", "BUY", Decimal("50000"), TEST_TS, 1)
        assert id1 != id2

    def test_starts_with_baet(self) -> None:
        cid = make_client_order_id("BTCUSDT", "BUY", None, TEST_TS)
        assert cid.startswith("baet-")


class TestSubmitOrder:
    def test_submit_produces_events(self, env) -> None:
        result = env["engine"].submit_order(
            state=env["state"],
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )
        assert result.success is True
        assert len(result.events) > 0
        assert result.order_id is not None

    def test_submit_records_on_exchange(self, env) -> None:
        env["engine"].submit_order(
            state=env["state"],
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
        )
        assert len(env["gateway"].submitted_orders) == 1
        assert env["gateway"].submitted_orders[0]["symbol"] == "BTCUSDT"

    def test_idempotent_retry(self, env) -> None:
        """Same parameters → same client_order_id → second call is no-op."""
        state = env["state"]
        result1 = env["engine"].submit_order(
            state=state, symbol="BTCUSDT", side="BUY",
            order_type="LIMIT", quantity=Decimal("0.01"), price=Decimal("50000"),
        )
        assert result1.success is True

        # Second call with same params should be idempotent
        result2 = env["engine"].submit_order(
            state=state, symbol="BTCUSDT", side="BUY",
            order_type="LIMIT", quantity=Decimal("0.01"), price=Decimal("50000"),
        )
        assert result2.success is True
        # Only one order on exchange
        assert len(env["gateway"].submitted_orders) == 1

    def test_retry_on_failure(self, env) -> None:
        """Gateway fails twice then succeeds."""
        gateway = FakeGateway(fail_count=0)
        gateway._call_count = 0
        # Make it fail on first call
        original_submit = gateway.submit_order
        call_count = 0

        def flaky_submit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Temporary failure")
            return original_submit(*args, **kwargs)

        gateway.submit_order = flaky_submit

        engine = ExecutionEngine(
            event_store=env["store"],
            gateway=gateway,
            retry_policy=RetryPolicy(max_retries=2, base_delay_ms=10),
            clock=Clock.fixed(TEST_TS),
        )

        result = engine.submit_order(
            state=env["state"], symbol="BTCUSDT", side="BUY",
            order_type="LIMIT", quantity=Decimal("0.01"), price=Decimal("50000"),
        )
        assert result.success is True
        assert call_count == 2  # Failed once, succeeded on retry


class TestCancelOrder:
    def test_cancel_produces_event(self, env) -> None:
        # First submit
        submit_result = env["engine"].submit_order(
            state=env["state"], symbol="BTCUSDT", side="BUY",
            order_type="LIMIT", quantity=Decimal("0.01"), price=Decimal("50000"),
        )
        assert submit_result.success is True

        # Then cancel
        result = env["engine"].cancel_order(
            state=env["state"],
            client_order_id=submit_result.order_id,
            symbol="BTCUSDT",
        )
        assert result.success is True
        assert len(result.events) > 0


class TestRetryPolicy:
    def test_exponential_backoff(self) -> None:
        policy = RetryPolicy(base_delay_ms=100, backoff_factor=2.0, max_delay_ms=1000)
        assert policy.get_delay_ms(0) == 100
        assert policy.get_delay_ms(1) == 200
        assert policy.get_delay_ms(2) == 400

    def test_max_delay_cap(self) -> None:
        policy = RetryPolicy(base_delay_ms=100, backoff_factor=10.0, max_delay_ms=500)
        assert policy.get_delay_ms(0) == 100
        assert policy.get_delay_ms(1) == 500  # Capped

    def test_should_retry_connection_error(self) -> None:
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(ConnectionError("timeout"), 0) is True
        assert policy.should_retry(ConnectionError("timeout"), 3) is False

    def test_should_retry_non_retryable(self) -> None:
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(ValueError("bad input"), 0) is False
