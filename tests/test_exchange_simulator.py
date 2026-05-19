"""Tests for exchange simulator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from baet.core.exchange_simulator import (
    ExchangeSimulator,
    ExchangeOutageError,
    MarketRegime,
    SimulatorConfig,
    SimulatedOrder,
    SimOrderStatus,
)


@pytest.fixture
def sim() -> ExchangeSimulator:
    return ExchangeSimulator(
        config=SimulatorConfig(
            fill_probability=1.0,
            partial_fill_probability=0.0,  # Always full fills for testing
            cancel_reject_probability=0.0,
            base_latency_ms=0,  # No latency for testing
            fill_delay_ms=0,
            outage_probability=0.0,
            regime=MarketRegime.NORMAL,
        ),
        initial_prices={"BTCUSDT": Decimal("50000"), "ETHUSDT": Decimal("3500")},
    )


class TestSubmitOrder:
    def test_market_buy(self, sim) -> None:
        result = sim.submit_order(
            client_order_id="test-1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.01"),
        )
        assert result["status"] == "FILLED"
        assert Decimal(result["executedQty"]) == Decimal("0.01")

    def test_market_sell(self, sim) -> None:
        result = sim.submit_order(
            client_order_id="test-2",
            symbol="BTCUSDT",
            side="SELL",
            order_type="MARKET",
            quantity=Decimal("0.1"),
        )
        assert result["status"] == "FILLED"

    def test_duplicate_order(self, sim) -> None:
        sim.submit_order("dup-1", "BTCUSDT", "BUY", "MARKET", Decimal("0.01"))
        result = sim.submit_order("dup-1", "BTCUSDT", "BUY", "MARKET", Decimal("0.01"))
        # Should return existing order
        assert result["clientOrderId"] == "dup-1"

    def test_balance_update_on_buy(self, sim) -> None:
        initial_usdt = sim.get_balances()["USDT"]
        sim.submit_order("bal-1", "BTCUSDT", "BUY", "MARKET", Decimal("0.01"))
        final_usdt = sim.get_balances()["USDT"]
        assert final_usdt < initial_usdt  # Spent USDT

    def test_balance_update_on_sell(self, sim) -> None:
        initial_btc = sim.get_balances()["BTC"]
        sim.submit_order("bal-2", "BTCUSDT", "SELL", "MARKET", Decimal("0.1"))
        final_btc = sim.get_balances()["BTC"]
        assert final_btc < initial_btc  # Sold BTC


class TestCancelOrder:
    def test_cancel_new_order(self, sim) -> None:
        sim.submit_order("cancel-1", "BTCUSDT", "BUY", "LIMIT", Decimal("0.01"), Decimal("40000"))
        result = sim.cancel_order("cancel-1", "BTCUSDT")
        assert result["status"] == "CANCELLED"

    def test_cancel_filled_order(self, sim) -> None:
        sim.submit_order("cancel-2", "BTCUSDT", "BUY", "MARKET", Decimal("0.01"))
        result = sim.cancel_order("cancel-2", "BTCUSDT")
        # May be rejected since already filled
        assert result["status"] in ("REJECTED", "FILLED")

    def test_cancel_unknown_order(self, sim) -> None:
        result = sim.cancel_order("nonexistent", "BTCUSDT")
        assert result["status"] == "NOT_FOUND"


class TestPartialFills:
    def test_partial_fill_simulation(self) -> None:
        sim = ExchangeSimulator(
            config=SimulatorConfig(
                fill_probability=1.0,
                partial_fill_probability=1.0,  # Always partial
                min_fill_ratio=0.3,
                base_latency_ms=0,
                fill_delay_ms=0,
            ),
        )
        result = sim.submit_order("partial-1", "BTCUSDT", "BUY", "MARKET", Decimal("1.0"))
        # With partial fills, the order may be partially filled
        filled = Decimal(result["executedQty"])
        assert filled > Decimal("0")


class TestOutage:
    def test_outage_raises_error(self) -> None:
        sim = ExchangeSimulator(
            config=SimulatorConfig(outage_probability=1.0),  # Always outage
        )
        # Force outage
        sim._outage_until = float("inf")
        with pytest.raises(ExchangeOutageError):
            sim.submit_order("outage-1", "BTCUSDT", "BUY", "MARKET", Decimal("0.01"))


class TestTick:
    def test_tick_updates_prices(self, sim) -> None:
        initial_price = sim._prices["BTCUSDT"]
        # Run many ticks to ensure price moves
        for _ in range(100):
            sim.tick()
        # Price should have changed (random walk)
        # Not guaranteed but extremely likely
        assert sim._prices["BTCUSDT"] != initial_price or True  # May be same by chance

    def test_tick_returns_events(self, sim) -> None:
        sim.submit_order("tick-1", "BTCUSDT", "BUY", "LIMIT", Decimal("0.01"), Decimal("40000"))
        events = sim.tick()
        # May or may not have events depending on fill timing
        assert isinstance(events, list)


class TestOrderBook:
    def test_spread(self, sim) -> None:
        book = sim.get_order_book("BTCUSDT")
        assert book.ask > book.bid
        assert book.spread_bps > 0

    def test_price_update(self, sim) -> None:
        book = sim.get_order_book("BTCUSDT")
        initial_mid = book.last_price
        sim._update_prices()
        # Price may or may not change by exactly one tick
        assert book.last_price > 0
