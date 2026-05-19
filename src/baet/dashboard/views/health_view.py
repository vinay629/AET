"""Health view — read-only projection of system health.

Derived from event journal + health monitor.
"""

from __future__ import annotations

import time
from typing import Any

from baet.dashboard.views.base import MaterializedView
from baet.core.health import HealthStatus


class HealthView(MaterializedView):
    """Read-only system health projection."""

    def __init__(self, event_store, health_monitor=None, cache_ttl: float = 0.5) -> None:
        super().__init__(event_store, cache_ttl)
        self.health_monitor = health_monitor

    def _compute(self, **params: Any) -> dict[str, Any]:
        events = self.event_store.replay()
        latest_seq = events[-1].sequence if events else 0

        # Event pipeline metrics
        event_count = len(events)
        event_types = {}
        for e in events:
            t = e.event_type.value
            event_types[t] = event_types.get(t, 0) + 1

        # Error count
        error_count = sum(1 for e in events if e.event_type.value == "error")

        # Latency stats from health monitor
        latency_stats = {}
        if self.health_monitor:
            metrics = self.health_monitor.get_metrics()
            latency_stats = metrics.get("latencies", {})

        # Engine status (derived from recent events)
        engine_status = self._derive_engine_status(events)

        # Invariant status
        invariant_violations = sum(
            1 for e in events[-100:]
            if e.event_type.value == "error" and "invariant" in str(e.payload).lower()
        )

        return {
            "engine_status": engine_status,
            "event_pipeline": {
                "total_events": event_count,
                "latest_sequence": latest_seq,
                "event_types": event_types,
                "error_count": error_count,
                "events_per_type": event_types,
            },
            "latency": {
                "p50_ms": self._extract_latency_percentile(latency_stats, 50),
                "p95_ms": self._extract_latency_percentile(latency_stats, 95),
                "p99_ms": self._extract_latency_percentile(latency_stats, 99),
            },
            "invariants": {
                "violations_last_100": invariant_violations,
                "status": "healthy" if invariant_violations == 0 else "degraded",
            },
            "uptime_seconds": time.monotonic() - (
                self.health_monitor._start_time if self.health_monitor else time.monotonic()
            ),
        }

    def _derive_engine_status(self, events: list) -> str:
        """Derive engine status from recent events."""
        if not events:
            return "STOPPED"

        # Check last few events for system start/stop
        for event in reversed(events[-10:]):
            if event.event_type.value == "system_start":
                return "RUNNING"
            if event.event_type.value == "system_stop":
                return "STOPPED"
            if event.event_type.value == "error" and "halt" in str(event.payload).lower():
                return "HALTED"

        return "RUNNING" if events else "STOPPED"

    @staticmethod
    def _extract_latency_percentile(latency_stats: dict, percentile: int) -> float:
        """Extract a percentile from latency stats."""
        for name, stats in latency_stats.items():
            key = f"p{percentile}"
            if isinstance(stats, dict) and key in stats:
                return stats[key]
        return 0.0
