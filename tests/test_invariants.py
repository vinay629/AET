"""Tests for invariant middleware."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from baet.core.clock import Clock, set_clock, reset_clock
from baet.core.events import Event, EventType
from baet.core.invariants import (
    InvariantError,
    InvariantSeverity,
    check_cash_delta_matches_fill,
    check_invariants,
    check_no_negative_cash,
    check_no_negative_positions,
    check_position_delta_matches_fill,
)
from baet.core.state import PortfolioState


def _make_event(
    event_type: EventType,
    payload: dict,
    sequence: int = 1,
    ts: datetime | None = None,
) -> Event:
    ts = ts or datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
    return Event(
        event_type=event_type,
        timestamp_exchange=ts,
        timestamp_local=ts,
        sequence=sequence,
        source="test",
        payload=payload,
    )


class TestNoNegativeCash:
    def test_positive_cash_passes(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(cash=Decimal("5000"))
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "1000", "units": "1", "fee": "1",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_no_negative_cash(prev, new, event)
        assert len(violations) == 0

    def test_negative_cash_fails(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(cash=Decimal("-100"))
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "999999", "units": "1", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_no_negative_cash(prev, new, event)
        assert len(violations) == 1
        assert violations[0].severity == InvariantSeverity.ERROR

    def test_zero_cash_passes(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(cash=Decimal("0"))
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "100000", "units": "1", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_no_negative_cash(prev, new, event)
        assert len(violations) == 0


class TestNoNegativePositions:
    def test_positive_position_passes(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(
            positions={"BTCUSDT": {"units": Decimal("1"), "avg_price": Decimal("50000")}}
        )
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "50000", "units": "1", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_no_negative_positions(prev, new, event)
        assert len(violations) == 0

    def test_negative_position_fails(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(
            positions={"BTCUSDT": {"units": Decimal("-1"), "avg_price": Decimal("50000")}}
        )
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "SELL",
            "price": "50000", "units": "1", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_no_negative_positions(prev, new, event)
        assert len(violations) == 1
        assert "BTCUSDT" in violations[0].message


class TestCashDeltaMatchesFill:
    def test_buy_cash_delta_correct(self) -> None:
        prev = PortfolioState(cash=Decimal("10000"))
        new = PortfolioState(cash=Decimal("8999"))
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "1000", "units": "1", "fee": "1",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_cash_delta_matches_fill(prev, new, event)
        assert len(violations) == 0

    def test_buy_cash_delta_wrong(self) -> None:
        prev = PortfolioState(cash=Decimal("10000"))
        new = PortfolioState(cash=Decimal("9500"))  # Wrong delta
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "1000", "units": "1", "fee": "1",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_cash_delta_matches_fill(prev, new, event)
        assert len(violations) == 1

    def test_sell_cash_delta_correct(self) -> None:
        prev = PortfolioState(
            cash=Decimal("10000"),
            positions={"BTCUSDT": {"units": Decimal("1"), "avg_price": Decimal("50000")}},
        )
        new = PortfolioState(
            cash=Decimal("11998"),
            positions={"BTCUSDT": {"units": Decimal("0.5"), "avg_price": Decimal("50000")}},
        )
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "SELL",
            "price": "4000", "units": "0.5", "fee": "2",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        # proceeds = 0.5 * 4000 - 2 = 1998
        # new cash = 10000 + 1998 = 11998
        violations = check_cash_delta_matches_fill(prev, new, event)
        assert len(violations) == 0

    def test_non_fill_event_skipped(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(cash=Decimal("5000"))
        event = _make_event(EventType.PORTFOLIO_UPDATED, {"cash": "5000"})
        violations = check_cash_delta_matches_fill(prev, new, event)
        assert len(violations) == 0


class TestPositionDeltaMatchesFill:
    def test_buy_position_delta_correct(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(
            positions={"BTCUSDT": {"units": Decimal("1"), "avg_price": Decimal("50000")}}
        )
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "50000", "units": "1", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_position_delta_matches_fill(prev, new, event)
        assert len(violations) == 0

    def test_sell_position_delta_correct(self) -> None:
        prev = PortfolioState(
            positions={"BTCUSDT": {"units": Decimal("1"), "avg_price": Decimal("50000")}},
        )
        new = PortfolioState(
            positions={"BTCUSDT": {"units": Decimal("0.5"), "avg_price": Decimal("50000")}},
        )
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "SELL",
            "price": "60000", "units": "0.5", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_position_delta_matches_fill(prev, new, event)
        assert len(violations) == 0

    def test_position_delta_wrong(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(
            positions={"BTCUSDT": {"units": Decimal("2"), "avg_price": Decimal("50000")}}
        )
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "50000", "units": "1", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_position_delta_matches_fill(prev, new, event)
        assert len(violations) == 1


class TestCheckInvariants:
    def test_all_clear(self) -> None:
        ts = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
        set_clock(Clock.fixed(ts))
        try:
            prev = PortfolioState()
            new = PortfolioState(
                cash=Decimal("8999"),
                positions={"BTCUSDT": {"units": Decimal("1"), "avg_price": Decimal("1000")}},
            )
            event = Event(
                event_type=EventType.ORDER_FILLED,
                timestamp_exchange=ts,
                timestamp_local=ts,
                sequence=1,
                source="test",
                payload={
                    "symbol": "BTCUSDT", "side": "BUY",
                    "price": "1000", "units": "1", "fee": "1",
                    "timestamp": ts.isoformat(),
                },
            )
            violations = check_invariants(prev, new, event, halt_on_error=False)
            critical = [v for v in violations if v.severity in (InvariantSeverity.ERROR, InvariantSeverity.HALT)]
            assert len(critical) == 0
        finally:
            reset_clock()

    def test_halt_on_error_raises(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(cash=Decimal("-100"))
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "999999", "units": "1", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        with pytest.raises(InvariantError):
            check_invariants(prev, new, event, halt_on_error=True)

    def test_no_halt_returns_violations(self) -> None:
        prev = PortfolioState()
        new = PortfolioState(cash=Decimal("-100"))
        event = _make_event(EventType.ORDER_FILLED, {
            "symbol": "BTCUSDT", "side": "BUY",
            "price": "999999", "units": "1", "fee": "0",
            "timestamp": "2026-05-18T12:00:00+00:00",
        })
        violations = check_invariants(prev, new, event, halt_on_error=False)
        assert len(violations) > 0
