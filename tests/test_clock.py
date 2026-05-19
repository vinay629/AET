"""Tests for the deterministic clock."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from baet.core.clock import Clock, get_clock, reset_clock, set_clock


class TestRealClock:
    def test_now_returns_utc(self) -> None:
        clock = Clock.real()
        t = clock.now()
        assert t.tzinfo is not None

    def test_monotonic_increases(self) -> None:
        clock = Clock.real()
        t1 = clock.monotonic()
        t2 = clock.monotonic()
        assert t2 >= t1


class TestFixedClock:
    def test_now_returns_fixed_time(self) -> None:
        fixed = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
        clock = Clock.fixed(fixed)
        assert clock.now() == fixed
        # Call again — should be identical
        assert clock.now() == fixed

    def test_monotonic_returns_zero(self) -> None:
        clock = Clock.fixed(datetime(2026, 5, 18, tzinfo=timezone.utc))
        assert clock.monotonic() == 0.0


class TestOffsetClock:
    def test_now_starts_at_base(self) -> None:
        base = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
        clock = Clock.offset(base, speed=10.0)
        # Should be very close to base at start
        delta = abs((clock.now() - base).total_seconds())
        assert delta < 1.0


class TestGlobalClock:
    def test_get_clock_returns_real_by_default(self) -> None:
        reset_clock()
        clock = get_clock()
        assert isinstance(clock, Clock)

    def test_set_clock_replaces_global(self) -> None:
        fixed = datetime(2026, 3, 1, tzinfo=timezone.utc)
        set_clock(Clock.fixed(fixed))
        assert get_clock().now() == fixed
        reset_clock()

    def test_reset_clock_restores_real(self) -> None:
        fixed = datetime(2026, 3, 1, tzinfo=timezone.utc)
        set_clock(Clock.fixed(fixed))
        reset_clock()
        # Should be real clock now — just verify it doesn't return our fixed time
        assert get_clock().now() != fixed
