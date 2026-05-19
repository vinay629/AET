"""Deterministic clock for BAET.

All timestamps flow through Clock so that tests and replay
can inject a fixed time source instead of calling datetime.now().

Usage:
    # Production:
    clock = Clock.real()

    # Tests / replay:
    clock = Clock.fixed(datetime(2026, 5, 18, tzinfo=timezone.utc))
    clock = Clock.offset(base_time, speed=10.0)  # 10x speed for simulation
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional


class Clock(ABC):
    """Abstract clock — all timestamps in BAET flow through this."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current time as a timezone-aware datetime (UTC)."""
        ...

    @abstractmethod
    def monotonic(self) -> float:
        """Return a monotonic counter for latency measurements (seconds)."""
        ...

    @classmethod
    def real(cls) -> Clock:
        """Wall-clock time — for production."""
        return _RealClock()

    @classmethod
    def fixed(cls, timestamp: datetime) -> Clock:
        """Fixed time — for deterministic tests."""
        return _FixedClock(timestamp)

    @classmethod
    def offset(cls, base: datetime, speed: float = 1.0) -> Clock:
        """Offset clock starting from base, advancing at `speed` multiplier.
        Useful for simulation: speed=10.0 means 10 seconds pass per real second.
        """
        return _OffsetClock(base, speed)


class _RealClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic(self) -> float:
        return time.monotonic()


class _FixedClock(Clock):
    def __init__(self, timestamp: datetime) -> None:
        self._timestamp = timestamp

    def now(self) -> datetime:
        return self._timestamp

    def monotonic(self) -> float:
        return 0.0


class _OffsetClock(Clock):
    def __init__(self, base: datetime, speed: float = 1.0) -> None:
        self._base = base
        self._speed = speed
        self._start = time.monotonic()

    def now(self) -> datetime:
        elapsed = time.monotonic() - self._start
        from datetime import timedelta
        return self._base + timedelta(seconds=elapsed * self._speed)

    def monotonic(self) -> float:
        return (time.monotonic() - self._start) * self._speed


# Module-level default clock — replaced in tests.
_default_clock: Optional[Clock] = None


def get_clock() -> Clock:
    """Return the active clock. Creates a real clock if none set."""
    global _default_clock
    if _default_clock is None:
        _default_clock = Clock.real()
    return _default_clock


def set_clock(clock: Clock) -> None:
    """Set the global clock (for tests / simulation)."""
    global _default_clock
    _default_clock = clock


def reset_clock() -> None:
    """Reset to a fresh real clock."""
    global _default_clock
    _default_clock = Clock.real()
