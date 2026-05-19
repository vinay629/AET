"""Tests for process supervisor and halt coordinator."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from baet.core.supervisor import (
    HaltCoordinator,
    HaltEvent,
    HaltReason,
    ServiceHealth,
    ServiceRecord,
    ServiceState,
    Supervisor,
    SystemHaltedError,
    RestartPolicy,
    RestartManager,
)


class MockService:
    """Mock service for testing."""

    def __init__(self, name: str, fail_start: bool = False, fail_health: bool = False) -> None:
        self._name = name
        self.fail_start = fail_start
        self.fail_health = fail_health
        self.started = False
        self.stopped = False
        self.health_calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        if self.fail_start:
            raise RuntimeError(f"{self._name} failed to start")
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def health_check(self) -> ServiceHealth:
        self.health_calls += 1
        if self.fail_health:
            return ServiceHealth(name=self._name, status="failed")
        return ServiceHealth(
            name=self._name,
            status="running",
            last_heartbeat=asyncio.get_event_loop().time(),
        )


class TestHaltCoordinator:
    def test_initial_state(self) -> None:
        hc = HaltCoordinator()
        assert hc.is_halted is False
        assert hc.halt_event is None

    def test_halt(self) -> None:
        hc = HaltCoordinator()
        asyncio.get_event_loop().run_until_complete(
            hc.halt(HaltReason.MANUAL, "Test halt", "test")
        )
        assert hc.is_halted is True
        assert hc.halt_event is not None
        assert hc.halt_event.reason == HaltReason.MANUAL

    def test_halt_idempotent(self) -> None:
        hc = HaltCoordinator()
        asyncio.get_event_loop().run_until_complete(
            hc.halt(HaltReason.MANUAL, "First halt")
        )
        # Second halt should not overwrite
        asyncio.get_event_loop().run_until_complete(
            hc.halt(HaltReason.INVARIANT_VIOLATION, "Second halt")
        )
        assert hc.halt_event.reason == HaltReason.MANUAL

    def test_resume(self) -> None:
        hc = HaltCoordinator()
        asyncio.get_event_loop().run_until_complete(
            hc.halt(HaltReason.MANUAL, "Test")
        )
        asyncio.get_event_loop().run_until_complete(hc.resume())
        assert hc.is_halted is False
        assert hc.halt_event is None

    def test_check_raises_when_halted(self) -> None:
        hc = HaltCoordinator()
        asyncio.get_event_loop().run_until_complete(
            hc.halt(HaltReason.MANUAL, "Test")
        )
        with pytest.raises(SystemHaltedError):
            hc.check()

    def test_check_passes_when_not_halted(self) -> None:
        hc = HaltCoordinator()
        hc.check()  # Should not raise

    def test_halt_callbacks(self) -> None:
        hc = HaltCoordinator()
        callback_called = []

        async def on_halt(event: HaltEvent) -> None:
            callback_called.append(event)

        hc.on_halt(on_halt)
        asyncio.get_event_loop().run_until_complete(
            hc.halt(HaltReason.MANUAL, "Test")
        )
        assert len(callback_called) == 1

    def test_halt_reasons(self) -> None:
        """All halt reasons should be usable."""
        reasons = [
            HaltReason.MANUAL,
            HaltReason.INVARIANT_VIOLATION,
            HaltReason.RECONCILIATION_DRIFT,
            HaltReason.WEBSOCKET_GAP,
            HaltReason.EXCHANGE_ERROR,
            HaltReason.RISK_LIMIT,
            HaltReason.SERVICE_FAILURE,
            HaltReason.CONFIG_ERROR,
        ]
        for reason in reasons:
            hc = HaltCoordinator()
            asyncio.get_event_loop().run_until_complete(
                hc.halt(reason, f"Test {reason.value}")
            )
            assert hc.is_halted is True


class TestRestartManager:
    def test_should_restart_within_limit(self) -> None:
        rm = RestartManager(RestartPolicy(max_restarts=3))
        record = ServiceRecord(name="test", state=ServiceState.FAILED)
        record.restart_count = 0
        assert rm.should_restart(record) is True

    def test_should_not_restart_over_limit(self) -> None:
        rm = RestartManager(RestartPolicy(max_restarts=3))
        record = ServiceRecord(name="test", state=ServiceState.FAILED)
        record.restart_count = 3
        assert rm.should_restart(record) is False

    def test_exponential_backoff(self) -> None:
        policy = RestartPolicy(base_delay_seconds=1.0, backoff_factor=2.0, max_delay_seconds=60.0)
        rm = RestartManager(policy)
        assert rm.get_restart_delay(ServiceRecord(name="test")) == 1.0
        record = ServiceRecord(name="test")
        record.restart_count = 1
        assert rm.get_restart_delay(record) == 2.0
        record.restart_count = 2
        assert rm.get_restart_delay(record) == 4.0

    def test_max_delay_cap(self) -> None:
        policy = RestartPolicy(base_delay_seconds=1.0, backoff_factor=10.0, max_delay_seconds=5.0)
        rm = RestartManager(policy)
        record = ServiceRecord(name="test")
        record.restart_count = 5
        assert rm.get_restart_delay(record) == 5.0


class TestSupervisor:
    def test_register_service(self) -> None:
        sup = Supervisor()
        svc = MockService("test")
        sup.register("test", svc)
        assert "test" in sup._services

    def test_register_duplicate_raises(self) -> None:
        sup = Supervisor()
        sup.register("test", MockService("test"))
        with pytest.raises(ValueError):
            sup.register("test", MockService("test2"))

    def test_dependency_ordering(self) -> None:
        sup = Supervisor()
        sup.register("a", MockService("a"))
        sup.register("b", MockService("b"), dependencies=["a"])
        sup.register("c", MockService("c"), dependencies=["b"])
        order = sup._topological_sort()
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_start_stop_services(self) -> None:
        sup = Supervisor()
        svc_a = MockService("a")
        svc_b = MockService("b")
        sup.register("a", svc_a)
        sup.register("b", svc_b, dependencies=["a"])

        asyncio.get_event_loop().run_until_complete(sup.start())
        assert svc_a.started is True
        assert svc_b.started is True

        asyncio.get_event_loop().run_until_complete(sup.stop())
        assert svc_a.stopped is True
        assert svc_b.stopped is True

    def test_critical_service_failure_triggers_halt(self) -> None:
        sup = Supervisor()
        svc = MockService("execution_engine", fail_health=True)
        sup.register("execution_engine", svc)

        asyncio.get_event_loop().run_until_complete(sup.start())
        # Simulate health check failure
        asyncio.get_event_loop().run_until_complete(
            sup._handle_service_failure(
                sup._services["execution_engine"], "test failure"
            )
        )
        assert sup.halt_coordinator.is_halted is True
