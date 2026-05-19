"""Tests for health monitoring system."""

from __future__ import annotations

from baet.core.health import (
    HealthCheck,
    HealthMonitor,
    HealthStatus,
    MetricsCollector,
    SystemHealth,
)


class TestMetricsCollector:
    def test_increment(self) -> None:
        m = MetricsCollector()
        m.increment("trades")
        m.increment("trades")
        assert m.get_counter("trades") == 2

    def test_gauge(self) -> None:
        m = MetricsCollector()
        m.gauge("equity", 10500.0)
        assert m.get_gauge("equity") == 10500.0

    def test_latency_stats(self) -> None:
        m = MetricsCollector()
        for i in range(100):
            m.record_latency("api_call", float(i))
        stats = m.get_latency_stats("api_call")
        assert stats["count"] == 100
        assert stats["min"] == 0.0
        assert stats["max"] == 99.0

    def test_snapshot(self) -> None:
        m = MetricsCollector()
        m.increment("trades", 5)
        m.gauge("equity", 10000.0)
        snap = m.snapshot()
        assert snap["counters"]["trades"] == 5
        assert snap["gauges"]["equity"] == 10000.0


class TestHealthMonitor:
    def test_healthy_system(self) -> None:
        monitor = HealthMonitor()
        monitor.register_check("test", lambda: HealthCheck(
            name="test", status=HealthStatus.HEALTHY, message="OK"
        ))
        health = monitor.check_health()
        assert health.status == HealthStatus.HEALTHY

    def test_degraded_system(self) -> None:
        monitor = HealthMonitor()
        monitor.register_check("test", lambda: HealthCheck(
            name="test", status=HealthStatus.DEGRADED, message="Slow"
        ))
        health = monitor.check_health()
        assert health.status == HealthStatus.DEGRADED

    def test_unhealthy_system(self) -> None:
        monitor = HealthMonitor()
        monitor.register_check("test", lambda: HealthCheck(
            name="test", status=HealthStatus.UNHEALTHY, message="Down"
        ))
        health = monitor.check_health()
        assert health.status == HealthStatus.UNHEALTHY

    def test_check_exception_handling(self) -> None:
        monitor = HealthMonitor()
        monitor.register_check("failing", lambda: 1 / 0)  # type: ignore[operator]
        health = monitor.check_health()
        assert health.status == HealthStatus.UNHEALTHY

    def test_to_dict(self) -> None:
        monitor = HealthMonitor()
        monitor.register_check("test", lambda: HealthCheck(
            name="test", status=HealthStatus.HEALTHY, message="OK"
        ))
        health = monitor.check_health()
        d = health.to_dict()
        assert d["status"] == "healthy"
        assert len(d["checks"]) == 1
