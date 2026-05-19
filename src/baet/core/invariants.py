"""Invariant middleware for BAET.

After EVERY state transition, these invariants are checked.
If any invariant fails, the system halts — no exceptions.

This is the safety net that catches bugs in the reducer,
the execution engine, or any other state-mutating code.

Usage:
    state = reduce_state(prev_state, event)
    check_invariants(prev_state, state, event)

If check_invariants raises InvariantError, the event is rejected
and the previous state is preserved.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from baet.core.clock import Clock, get_clock
from baet.core.events import Event, EventType
from baet.core.state import PortfolioState

logger = logging.getLogger(__name__)


class InvariantSeverity(StrEnum):
    WARNING = "warning"    # Logged, state accepted
    ERROR = "error"        # Logged, state rejected, event discarded
    HALT = "halt"          # Logged, system halts trading


@dataclass
class InvariantViolation:
    """A single invariant violation."""
    name: str
    severity: InvariantSeverity
    message: str
    event_type: EventType
    event_sequence: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InvariantError(Exception):
    """Raised when a critical invariant is violated."""
    def __init__(self, violations: list[InvariantViolation]) -> None:
        self.violations = violations
        messages = "; ".join(v.message for v in violations)
        super().__init__(f"Invariant violation(s): {messages}")


# ---------------------------------------------------------------------------
# Individual invariant checks
# Each returns a list of violations (empty = OK).
# ---------------------------------------------------------------------------

def check_no_negative_cash(
    prev: PortfolioState, new: PortfolioState, event: Event
) -> list[InvariantViolation]:
    """Cash must never be negative."""
    violations = []
    if new.cash < 0:
        violations.append(InvariantViolation(
            name="no_negative_cash",
            severity=InvariantSeverity.ERROR,
            message=f"Cash went negative: {new.cash} (event seq={event.sequence})",
            event_type=event.event_type,
            event_sequence=event.sequence,
        ))
    return violations


def check_no_negative_positions(
    prev: PortfolioState, new: PortfolioState, event: Event
) -> list[InvariantViolation]:
    """Position units must never be negative."""
    violations = []
    for symbol, pos in new.positions.items():
        if pos["units"] < 0:
            violations.append(InvariantViolation(
                name="no_negative_positions",
                severity=InvariantSeverity.ERROR,
                message=(
                    f"Negative position in {symbol}: {pos['units']} "
                    f"(event seq={event.sequence})"
                ),
                event_type=event.event_type,
                event_sequence=event.sequence,
            ))
    return violations


def check_no_future_timestamps(
    prev: PortfolioState, new: PortfolioState, event: Event,
    clock: Clock | None = None,
) -> list[InvariantViolation]:
    """Exchange timestamps must not be in the future."""
    violations = []
    clk = clock or get_clock()
    now = clk.now()
    if event.timestamp_exchange > now:
        violations.append(InvariantViolation(
            name="no_future_timestamps",
            severity=InvariantSeverity.ERROR,
            message=(
                f"Exchange timestamp {event.timestamp_exchange} is in the future "
                f"(now={now}, event seq={event.sequence})"
            ),
            event_type=event.event_type,
            event_sequence=event.sequence,
        ))
    return violations


def check_cash_delta_matches_fill(
    prev: PortfolioState, new: PortfolioState, event: Event
) -> list[InvariantViolation]:
    """For fill events, verify cash delta matches the fill calculation."""
    violations = []
    if event.event_type != EventType.ORDER_FILLED:
        return violations

    payload = event.payload
    side = payload.get("side", "")
    price = Decimal(str(payload.get("price", 0)))
    units = Decimal(str(payload.get("units", 0)))
    fee = Decimal(str(payload.get("fee", 0)))

    if side == "BUY":
        expected_delta = -(units * price + fee)
    elif side == "SELL":
        expected_delta = units * price - fee
    else:
        return violations

    actual_delta = new.cash - prev.cash
    if actual_delta != expected_delta:
        violations.append(InvariantViolation(
            name="cash_delta_matches_fill",
            severity=InvariantSeverity.ERROR,
            message=(
                f"Cash delta mismatch for {side} fill: "
                f"expected={expected_delta}, actual={actual_delta}, "
                f"price={price}, units={units}, fee={fee} "
                f"(event seq={event.sequence})"
            ),
            event_type=event.event_type,
            event_sequence=event.sequence,
        ))
    return violations


def check_position_delta_matches_fill(
    prev: PortfolioState, new: PortfolioState, event: Event
) -> list[InvariantViolation]:
    """For fill events, verify position delta matches the fill."""
    violations = []
    if event.event_type != EventType.ORDER_FILLED:
        return violations

    payload = event.payload
    symbol = payload.get("symbol", "")
    side = payload.get("side", "")
    units = Decimal(str(payload.get("units", 0)))

    prev_units = prev.positions.get(symbol, {}).get("units", Decimal("0"))
    new_units = new.positions.get(symbol, {}).get("units", Decimal("0"))

    if side == "BUY":
        expected = prev_units + units
    elif side == "SELL":
        expected = prev_units - units
    else:
        return violations

    if new_units != expected:
        violations.append(InvariantViolation(
            name="position_delta_matches_fill",
            severity=InvariantSeverity.ERROR,
            message=(
                f"Position delta mismatch for {symbol} {side}: "
                f"expected={expected}, actual={new_units} "
                f"(event seq={event.sequence})"
            ),
            event_type=event.event_type,
            event_sequence=event.sequence,
        ))
    return violations


def check_no_duplicate_event(
    prev: PortfolioState, new: PortfolioState, event: Event
) -> list[InvariantViolation]:
    """Events with the same event_id should not change state twice."""
    # This is a structural check — the event store handles idempotency,
    # but we verify here that the reducer is pure.
    return []  # Placeholder — actual dedup is in EventStore


def check_replay_consistency(
    prev: PortfolioState, new: PortfolioState, event: Event
) -> list[InvariantViolation]:
    """Verify that replay(prev.events + [event]) == new state.

    This is expensive, so only run in debug/certification mode.
    Controlled by BAET_CERTIFY env var.
    """
    violations = []
    import os
    if os.environ.get("BAET_CERTIFY", "0") != "1":
        return violations

    from baet.core.reducer import reduce_many
    combined_events = []  # We don't store events in state, so we can't replay from scratch.
    # Instead, verify that applying the event to prev produces new.
    replayed = reduce_many(prev, [event])
    if replayed.state_hash() != new.state_hash():
        violations.append(InvariantViolation(
            name="replay_consistency",
            severity=InvariantSeverity.HALT,
            message=(
                f"Replay inconsistency at seq={event.sequence}: "
                f"reduce(state, event).hash={new.state_hash()[:12]} "
                f"!= reduce_many(state, [event]).hash={replayed.state_hash()[:12]}"
            ),
            event_type=event.event_type,
            event_sequence=event.sequence,
        ))
    return violations


# ---------------------------------------------------------------------------
# Registry of all invariant checks
# ---------------------------------------------------------------------------

ALL_CHECKS: list[callable] = [
    check_no_negative_cash,
    check_no_negative_positions,
    check_no_future_timestamps,
    check_cash_delta_matches_fill,
    check_position_delta_matches_fill,
    check_replay_consistency,
]


def _wrap_check(fn: callable, clock: Clock | None) -> callable:
    """Wrap a check function to inject the clock parameter if it accepts one."""
    import inspect
    sig = inspect.signature(fn)
    if "clock" in sig.parameters:
        def wrapped(prev: PortfolioState, new: PortfolioState, event: Event) -> list[InvariantViolation]:
            return fn(prev, new, event, clock=clock)
        return wrapped
    return fn


def check_invariants(
    prev_state: PortfolioState,
    new_state: PortfolioState,
    event: Event,
    *,
    halt_on_error: bool = True,
    clock: Clock | None = None,
) -> list[InvariantViolation]:
    """
    Run all invariant checks on a state transition.

    Args:
        prev_state: State before the event.
        new_state: State after the event.
        event: The event that caused the transition.
        halt_on_error: If True, raise InvariantError on ERROR/HALT violations.
        clock: Optional clock for time-based checks.

    Returns:
        List of all violations found (empty = all clear).

    Raises:
        InvariantError: If halt_on_error is True and any ERROR/HALT violations exist.
    """
    all_violations: list[InvariantViolation] = []

    for check_fn in ALL_CHECKS:
        wrapped = _wrap_check(check_fn, clock)
        try:
            violations = wrapped(prev_state, new_state, event)
            all_violations.extend(violations)
        except Exception as e:
            all_violations.append(InvariantViolation(
                name=check_fn.__name__,
                severity=InvariantSeverity.ERROR,
                message=f"Check crashed: {e}",
                event_type=event.event_type,
                event_sequence=event.sequence,
            ))

    # Log warnings
    for v in all_violations:
        if v.severity == InvariantSeverity.WARNING:
            logger.warning(f"Invariant warning: {v.name} — {v.message}")

    # Collect errors and halts
    critical = [v for v in all_violations if v.severity in (InvariantSeverity.ERROR, InvariantSeverity.HALT)]

    if critical:
        for v in critical:
            logger.error(f"Invariant {v.severity.value}: {v.name} — {v.message}")
        if halt_on_error:
            raise InvariantError(critical)

    return all_violations
