"""Tests for backtest realism engine."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from baet.core.backtest_realism import (
    BacktestRealism,
    CandleContext,
    FeeSchedule,
)
from baet.core.events import Event, EventType


def _make_fill_event(
    side: str,
    price: str,
    units: str,
    fee: str = "0",
    sequence: int = 1,
) -> Event:
    ts = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
    return Event(
        event_type=EventType.ORDER_FILLED,
        timestamp_exchange=ts,
        timestamp_local=ts,
        sequence=sequence,
        source="test",
        payload={
            "symbol": "BTCUSDT",
            "side": side,
            "price": price,
            "units": units,
            "fee": fee,
            "timestamp": ts.isoformat(),
        },
    )


def _make_candle(
    open_price: float = 50000.0,
    high: float = 50200.0,
    low: float = 49800.0,
    close: float = 50100.0,
    volume: float = 100.0,
) -> CandleContext:
    return CandleContext(
        symbol="BTCUSDT",
        timeframe="1h",
        open_time=datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc),
        open=Decimal(str(open_price)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)),
        quote_volume=Decimal(str(volume * close)),
    )


class TestBacktestRealism:
    def test_buy_fill_adjusted_up(self) -> None:
        realism = BacktestRealism(spread_bps=5.0, slippage_bps=2.0)
        event = _make_fill_event("BUY", "50000", "0.01", "0")
        candle = _make_candle()

        adjusted, info = realism.adjust_fill(event, candle)

        # Buy price should be higher than open (spread + slippage)
        adjusted_price = Decimal(adjusted.payload["price"])
        assert adjusted_price > candle.open

    def test_sell_fill_adjusted_down(self) -> None:
        realism = BacktestRealism(spread_bps=5.0, slippage_bps=2.0)
        event = _make_fill_event("SELL", "50000", "0.01", "0")
        candle = _make_candle()

        adjusted, info = realism.adjust_fill(event, candle)

        # Sell price should be lower than open (spread + slippage)
        adjusted_price = Decimal(adjusted.payload["price"])
        assert adjusted_price < candle.open

    def test_fee_calculated(self) -> None:
        realism = BacktestRealism(fee_schedule=FeeSchedule(taker_fee=Decimal("0.001")))
        event = _make_fill_event("BUY", "50000", "1.0", "0")
        candle = _make_candle()

        adjusted, info = realism.adjust_fill(event, candle)

        # Fee should be: fill_price * units * fee_rate
        fee = Decimal(adjusted.payload["fee"])
        assert fee > 0

    def test_buy_capped_at_high(self) -> None:
        """Even with spread + slippage, buy fill shouldn't exceed candle high."""
        realism = BacktestRealism(spread_bps=500.0, slippage_bps=200.0)  # Extreme
        event = _make_fill_event("BUY", "50000", "0.01", "0")
        candle = _make_candle(high=50200.0)

        adjusted, info = realism.adjust_fill(event, candle)
        adjusted_price = Decimal(adjusted.payload["price"])
        assert adjusted_price <= candle.high

    def test_sell_floored_at_low(self) -> None:
        """Even with spread + slippage, sell fill shouldn't go below candle low."""
        realism = BacktestRealism(spread_bps=500.0, slippage_bps=200.0)  # Extreme
        event = _make_fill_event("SELL", "50000", "0.01", "0")
        candle = _make_candle(low=49800.0)

        adjusted, info = realism.adjust_fill(event, candle)
        adjusted_price = Decimal(adjusted.payload["price"])
        assert adjusted_price >= candle.low

    def test_larger_order_more_slippage(self) -> None:
        realism = BacktestRealism(slippage_bps=2.0)
        small_event = _make_fill_event("BUY", "50000", "0.01", "0")
        large_event = _make_fill_event("BUY", "50000", "10.0", "0")
        candle = _make_candle(volume=100.0)

        _, small_info = realism.adjust_fill(small_event, candle)
        _, large_info = realism.adjust_fill(large_event, candle)

        assert large_info.slippage_cost > small_info.slippage_cost

    def test_non_fill_event_unchanged(self) -> None:
        realism = BacktestRealism()
        ts = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.SIGNAL_GENERATED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="test",
            payload={"score": "0.5"},
        )
        candle = _make_candle()

        adjusted, info = realism.adjust_fill(event, candle)
        assert adjusted.event_type == EventType.SIGNAL_GENERATED

    def test_adjustment_metadata(self) -> None:
        realism = BacktestRealism(
            spread_bps=5.0, slippage_bps=2.0, latency_ms=100.0, execution_delay=1
        )
        event = _make_fill_event("BUY", "50000", "0.01", "0")
        candle = _make_candle()

        adjusted, info = realism.adjust_fill(event, candle)

        assert adjusted.payload["latency_ms"] == 100.0
        assert adjusted.payload["execution_delay_bars"] == 1
        assert "original_price" in adjusted.payload
        assert "fill_price" in adjusted.payload


class TestFeeSchedule:
    def test_maker_fee(self) -> None:
        schedule = FeeSchedule(maker_fee=Decimal("0.0005"), taker_fee=Decimal("0.001"))
        assert schedule.get_fee_rate(is_maker=True) == Decimal("0.0005")

    def test_taker_fee(self) -> None:
        schedule = FeeSchedule(maker_fee=Decimal("0.0005"), taker_fee=Decimal("0.001"))
        assert schedule.get_fee_rate(is_maker=False) == Decimal("0.001")


class TestTimeframeDelta:
    def test_1m(self) -> None:
        delta = BacktestRealism._timeframe_to_delta("1m")
        assert delta.total_seconds() == 60

    def test_5m(self) -> None:
        delta = BacktestRealism._timeframe_to_delta("5m")
        assert delta.total_seconds() == 300

    def test_1h(self) -> None:
        delta = BacktestRealism._timeframe_to_delta("1h")
        assert delta.total_seconds() == 3600

    def test_1d(self) -> None:
        delta = BacktestRealism._timeframe_to_delta("1d")
        assert delta.total_seconds() == 86400
