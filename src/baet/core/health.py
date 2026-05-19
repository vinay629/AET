"""Health monitoring system for BAET.

Provides structured health checks, metrics, and observability.
Endpoints: /health, /reconciliation, /state_hash, /event_lag
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    message: str
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SystemHealth:
    """Overall system health report."""
    status: HealthStatus = HealthStatus.HEALTHY
    checks: list[HealthCheck] = field(default_factory=list)
    uptime_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": c.latency_ms,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class MetricsCollector:
    """Collects and tracks system metrics over time."""

    def __init__(self, window_size: int = 1000) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._window_size = window_size
        self._start_time = time.monotonic()

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def record_latency(self, name: str, latency_ms: float) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(latency_ms)
        # Keep only recent values
        if len(self._histograms[name]) > self._window_size:
            self._histograms[name] = self._histograms[name][-self._window_size:]

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def get_latency_stats(self, name: str) -> dict[str, float]:
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "p95": 0, "p99": 0}
        sorted_values = sorted(values)
        return {
            "count": len(sorted_values),
            "avg": sum(sorted_values) / len(sorted_values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p95": sorted_values[int(len(sorted_values) * 0.95)],
            "p99": sorted_values[int(len(sorted_values) * 0.99)],
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "uptime_seconds": time.monotonic() - self._start_time,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "latencies": {
                name: self.get_latency_stats(name)
                for name in self._histograms
            },
        }


class HealthMonitor:
    """System health monitor with pluggable checks."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._checks: dict[str, callable] = {}
        self._metrics = MetricsCollector()
        self._start_time = time.monotonic()
        self._state_dir = state_dir
        self._last_event_count = 0
        self._last_event_check_time = time.monotonic()

    def register_check(self, name: str, check_fn: callable) -> None:
        """Register a health check function that returns HealthCheck."""
        self._checks[name] = check_fn

    def check_health(self) -> SystemHealth:
        """Run all registered health checks and return overall health."""
        health = SystemHealth(
            uptime_seconds=time.monotonic() - self._start_time,
        )

        for name, check_fn in self._checks.items():
            start = time.monotonic()
            try:
                check = check_fn()
                check.latency_ms = (time.monotonic() - start) * 1000
            except Exception as e:
                check = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {e}",
                    latency_ms=(time.monotonic() - start) * 1000,
                )
            health.checks.append(check)

        # Determine overall status
        statuses = [c.status for c in health.checks]
        if HealthStatus.UNHEALTHY in statuses:
            health.status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            health.status = HealthStatus.DEGRADED
        else:
            health.status = HealthStatus.HEALTHY

        return health

    def check_event_lag(self, event_store: Any) -> HealthCheck:
        """Check if event processing is keeping up."""
        try:
            latest_seq = event_store.get_latest_sequence()
            now = time.monotonic()
            elapsed = now - self._last_event_check_time

            if elapsed > 0:
                event_rate = (latest_seq - self._last_event_count) / elapsed
            else:
                event_rate = 0

            self._last_event_count = latest_seq
            self._last_event_check_time = now

            self._metrics.gauge("event_lag.latest_sequence", latest_seq)
            self._metrics.gauge("event_lag.event_rate", event_rate)

            return HealthCheck(
                name="event_lag",
                status=HealthStatus.HEALTHY,
                message=f"Sequence {latest_seq}, rate {event_rate:.1f} events/sec",
                details={"latest_sequence": latest_seq, "event_rate": event_rate},
            )
        except Exception as e:
            return HealthCheck(
                name="event_lag",
                status=HealthStatus.UNHEALTHY,
                message=f"Cannot check event lag: {e}",
            )

    def check_state_integrity(self, state: Any) -> HealthCheck:
        """Verify portfolio state invariants."""
        try:
            violations = state.verify_invariants()
            if violations:
                return HealthCheck(
                    name="state_integrity",
                    status=HealthStatus.UNHEALTHY,
                    message=f"{len(violations)} invariant violations",
                    details={"violations": violations},
                )
            return HealthCheck(
                name="state_integrity",
                status=HealthStatus.HEALTHY,
                message="All invariants hold",
            )
        except Exception as e:
            return HealthCheck(
                name="state_integrity",
                status=HealthStatus.UNHEALTHY,
                message=f"Integrity check failed: {e}",
            )

    def get_metrics(self) -> dict[str, Any]:
        """Return current metrics snapshot."""
        return self._metrics.snapshot()

    @property
    def metrics(self) -> MetricsCollector:
        return self._metrics
