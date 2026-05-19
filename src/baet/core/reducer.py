"""Pure state reducer for BAET.

The single law of state:
    new_state = reduce(state, event)

No hidden mutations. No side effects. No timestamps from the system clock.
Every state change comes from an event, and every event is the product of
a prior state + input.

This module is the backbone. Everything else — execution, replay,
recovery, reconciliation — is built on top of this function.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from baet.core.events import Event, EventType
from baet.core.state import PortfolioState, TradeRecord


def reduce_state(state: PortfolioState, event: Event) -> PortfolioState:
    """Pure reducer: given a state and event, return a NEW state.

    The input state is never mutated. All fields are copied.
    This is the only function allowed to produce a new PortfolioState.

    Args:
        state: The current portfolio state (immutable in practice).
        event: The event to apply.

    Returns:
        A new PortfolioState reflecting the event.
    """
    # Deep copy so the caller's state is never mutated
    new_state = _copy_state(state)

    handler = _REDUCERS.get(event.event_type)
    if handler is not None:
        handler(new_state, event.payload)

    return new_state


def reduce_many(initial: PortfolioState, events: list[Event]) -> PortfolioState:
    """Fold a list of events over an initial state.

    This is the canonical replay function:
        state = reduce_many(PortfolioState(), event_stream)

    Deterministic: same events in same order → same final state.
    """
    state = initial
    for event in events:
        state = reduce_state(state, event)
    return state


def _copy_state(state: PortfolioState) -> PortfolioState:
    """Deep-copy a PortfolioState."""
    return PortfolioState(
        cash=state.cash,
        positions=deepcopy(state.positions),
        trades=list(state.trades),  # TradeRecord is frozen → shallow copy is fine
        equity_curve=deepcopy(state.equity_curve),
    )


def _on_fill(state: PortfolioState, payload: dict[str, Any]) -> None:
    """Apply a fill event to portfolio state (mutates the copy)."""
    symbol = payload["symbol"]
    side = payload["side"]
    price = Decimal(str(payload["price"]))
    units = Decimal(str(payload["units"]))
    fee = Decimal(str(payload.get("fee", 0)))

    if side == "BUY":
        cost = units * price + fee
        state.cash -= cost
        if symbol not in state.positions:
            state.positions[symbol] = {"units": Decimal("0"), "avg_price": Decimal("0")}
        pos = state.positions[symbol]
        old_units = pos["units"]
        new_units = old_units + units
        if new_units > 0:
            pos["avg_price"] = (
                (pos["avg_price"] * old_units) + (price * units)
            ) / new_units
        pos["units"] = new_units

    elif side == "SELL":
        proceeds = units * price - fee
        state.cash += proceeds
        if symbol in state.positions:
            state.positions[symbol]["units"] -= units
            if state.positions[symbol]["units"] <= 0:
                del state.positions[symbol]

    # Record the trade
    ts_str = payload.get("timestamp")
    if ts_str:
        ts = datetime.fromisoformat(ts_str)
    else:
        ts = datetime.now(timezone.utc)

    state.trades.append(TradeRecord(
        event_id=payload.get("event_id", ""),
        timestamp=ts,
        symbol=symbol,
        side=side,
        price=price,
        units=units,
        fee=fee,
    ))


def _on_portfolio_update(state: PortfolioState, payload: dict[str, Any]) -> None:
    """Apply a portfolio update event (e.g., deposit, withdrawal, correction)."""
    if "cash" in payload:
        state.cash = Decimal(str(payload["cash"]))
    if "positions" in payload:
        state.positions = {
            sym: {k: Decimal(str(v)) for k, v in pos.items()}
            for sym, pos in payload["positions"].items()
        }


def _on_equity_snapshot(state: PortfolioState, payload: dict[str, Any]) -> None:
    """Record an equity snapshot."""
    state.equity_curve.append(deepcopy(payload))


# Dispatch table: event_type → handler(state_copy, payload)
# Each handler mutates the copy in place (never the original).
_REDUCERS: dict[EventType, Any] = {
    EventType.ORDER_FILLED: _on_fill,
    EventType.PORTFOLIO_UPDATED: _on_portfolio_update,
    EventType.EQUITY_SNAPSHOT: _on_equity_snapshot,
}
