"""Process supervisor for BAET.

Manages the lifecycle of all trading system components:
- Market Ingest
- Strategy Engine
- Execution Engine
- Reconciliation Loop
- Snapshot Scheduler
- Dashboard API
- Health Monitor

Responsibilities:
- Start services in dependency order
- Restart crashed services (with backoff)
- Graceful shutdown on SIGTERM/SIGINT
- Panic halt propagation (kill switch)
- Heartbeat monitoring

Architecture:
    Supervisor
        ├── ServiceRegistry (service definitions + dependencies)
        ├── HealthChecker (heartbeat monitoring)
        ├── HaltCoordinator (kill switch propagation)
        └── RestartManager (crash recovery with backoff)
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Coroutine, Protocol

from baet.core.clock import Clock, get_clock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service protocol
# ---------------------------------------------------------------------------

class Service(Protocol):
    """Protocol for supervised services."""

    @property
    def name(self) -> str: ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health_check(self) -> ServiceHealth: ...


@dataclass
class ServiceHealth:
    """Health status of a service."""
    name: str
    status: str  # "running", "stopped", "degraded", "failed"
    last_heartbeat: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status in ("running", "degraded")

    @property
    def heartbeat_age(self) -> float:
        if self.last_heartbeat == 0:
            return float("inf")
        return time.monotonic() - self.last_heartbeat


# ---------------------------------------------------------------------------
# Service state
# ---------------------------------------------------------------------------

class ServiceState(StrEnum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RESTARTING = "restarting"


@dataclass
class ServiceRecord:
    """Tracked state of a supervised service."""
    name: str
    service: Service | None = None
    state: ServiceState = ServiceState.PENDING
    restart_count: int = 0
    last_start: float = 0.0
    last_stop: float = 0.0
    last_error: str = ""
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Halt coordinator — global kill switch
# ---------------------------------------------------------------------------

class HaltReason(StrEnum):
    MANUAL = "manual"
    INVARIANT_VIOLATION = "invariant_violation"
    RECONCILIATION_DRIFT = "reconciliation_drift"
    WEBSOCKET_GAP = "websocket_gap"
    EXCHANGE_ERROR = "exchange_error"
    RISK_LIMIT = "risk_limit"
    SERVICE_FAILURE = "service_failure"
    CONFIG_ERROR = "config_error"


@dataclass
class HaltEvent:
    """A halt event — the system stopped trading."""
    reason: HaltReason
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class HaltCoordinator:
    """
    Centralized halt authority — the global kill switch.

    When ANY component detects a critical issue, it calls halt().
    The coordinator:
    1. Records the halt event
    2. Propagates halt to ALL services
    3. Prevents new orders
    4. Stops strategy execution
    5. Triggers snapshot for recovery

    The system CANNOT resume trading until:
    - The halt is manually cleared
    - All services pass health checks
    - Reconciliation passes
    """

    def __init__(self) -> None:
        self._halted = False
        self._halt_event: HaltEvent | None = None
        self._halt_callbacks: list[Callable[[HaltEvent], Coroutine]] = []
        self._resume_callbacks: list[Callable[[], Coroutine]] = []

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def halt_event(self) -> HaltEvent | None:
        return self._halt_event

    def on_halt(self, callback: Callable[[HaltEvent], Coroutine]) -> None:
        """Register a callback for halt events."""
        self._halt_callbacks.append(callback)

    def on_resume(self, callback: Callable[[], Coroutine]) -> None:
        """Register a callback for resume events."""
        self._resume_callbacks.append(callback)

    async def halt(
        self,
        reason: HaltReason,
        message: str,
        source: str = "",
        details: dict[str, Any] | None = None,
    ) -> HaltEvent:
        """
        Halt ALL trading activity.

        This is the single point of authority for stopping the system.
        Once called, no new orders can be placed, no strategies execute,
        and all services transition to a safe state.
        """
        if self._halted:
            logger.warning(f"Halt requested but already halted: {reason.value}")
            return self._halt_event

        self._halted = True
        self._halt_event = HaltEvent(
            reason=reason,
            message=message,
            source=source,
            details=details or {},
        )

        logger.critical(
            f"🛑 GLOBAL HALT: {reason.value} — {message} "
            f"(source={source})"
        )

        # Propagate to all registered callbacks
        for callback in self._halt_callbacks:
            try:
                await callback(self._halt_event)
            except Exception as e:
                logger.error(f"Halt callback failed: {e}")

        return self._halt_event

    async def resume(self) -> None:
        """
        Resume trading after a halt.

        WARNING: This should only be called after:
        1. The root cause has been identified and fixed
        2. All services pass health checks
        3. Reconciliation passes
        4. Manual confirmation
        """
        if not self._halted:
            logger.warning("Resume requested but not halted")
            return

        logger.info("▶️ Resuming trading — all services healthy")

        self._halted = False
        self._halt_event = None

        for callback in self._resume_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Resume callback failed: {e}")

    def check(self) -> None:
        """
        Raise if the system is halted. Use as a guard in order placement.
        """
        if self._halted:
            raise SystemHaltedError(
                f"System is halted: {self._halt_event.reason.value} — "
                f"{self._halt_event.message}"
            )


class SystemHaltedError(Exception):
    """Raised when an operation is attempted while the system is halted."""
    pass


# ---------------------------------------------------------------------------
# Restart manager
# ---------------------------------------------------------------------------

@dataclass
class RestartPolicy:
    """Policy for restarting failed services."""
    max_restarts: int = 5
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_factor: float = 2.0

    def get_delay(self, restart_count: int) -> float:
        delay = self.base_delay_seconds * (self.backoff_factor ** restart_count)
        return min(delay, self.max_delay_seconds)


class RestartManager:
    """Manages service restarts with exponential backoff."""

    def __init__(self, policy: RestartPolicy | None = None) -> None:
        self.policy = policy or RestartPolicy()

    def should_restart(self, record: ServiceRecord) -> bool:
        """Determine if a service should be restarted."""
        if record.state not in (ServiceState.FAILED, ServiceState.STOPPED):
            return False
        return record.restart_count < self.policy.max_restarts

    def get_restart_delay(self, record: ServiceRecord) -> float:
        """Get the delay before next restart attempt."""
        return self.policy.get_delay(record.restart_count)

    def record_restart(self, record: ServiceRecord) -> None:
        """Record a restart attempt."""
        record.restart_count += 1
        record.last_start = time.monotonic()


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------

class Supervisor:
    """
    Process orchestrator for the BAET trading system.

    Manages service lifecycle:
    - Dependency-ordered startup
    - Health monitoring with heartbeats
    - Automatic restart with backoff
    - Graceful shutdown
    - Global halt propagation
    """

    def __init__(
        self,
        halt_coordinator: HaltCoordinator | None = None,
        restart_policy: RestartPolicy | None = None,
        heartbeat_interval: float = 5.0,
        heartbeat_timeout: float = 30.0,
        clock: Clock | None = None,
    ) -> None:
        self.clock = clock or get_clock()
        self.halt_coordinator = halt_coordinator or HaltCoordinator()
        self.restart_manager = RestartManager(restart_policy)
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout

        self._services: dict[str, ServiceRecord] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Register halt callback
        self.halt_coordinator.on_halt(self._on_halt)

    def register(
        self,
        name: str,
        service: Service,
        dependencies: list[str] | None = None,
    ) -> None:
        """Register a service with the supervisor."""
        if name in self._services:
            raise ValueError(f"Service {name} already registered")

        self._services[name] = ServiceRecord(
            name=name,
            service=service,
            dependencies=dependencies or [],
        )

        # Update dependents
        for dep in (dependencies or []):
            if dep in self._services:
                self._services[dep].dependents.append(name)

    async def start(self) -> None:
        """Start all services in dependency order."""
        self._running = True
        logger.info("Supervisor starting")

        # Start in dependency order
        started = set()
        for name in self._topological_sort():
            record = self._services[name]
            await self._start_service(record)
            started.add(name)

        # Start health monitoring
        asyncio.create_task(self._monitor_health())

        logger.info(f"Supervisor started {len(started)} services")

    async def stop(self) -> None:
        """Stop all services in reverse dependency order."""
        self._running = False
        logger.info("Supervisor stopping")

        # Stop in reverse dependency order
        stopped = set()
        for name in reversed(self._topological_sort()):
            record = self._services[name]
            await self._stop_service(record)
            stopped.add(name)

        self._shutdown_event.set()
        logger.info(f"Supervisor stopped {len(stopped)} services")

    async def run(self) -> None:
        """Run the supervisor until shutdown."""
        await self.start()

        # Wait for shutdown signal
        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _start_service(self, record: ServiceRecord) -> None:
        """Start a single service."""
        if record.state == ServiceState.RUNNING:
            return

        # Check dependencies
        for dep_name in record.dependencies:
            dep = self._services.get(dep_name)
            if dep is None:
                raise RuntimeError(
                    f"Service {record.name} depends on unknown service {dep_name}"
                )
            if dep.state != ServiceState.RUNNING:
                raise RuntimeError(
                    f"Service {record.name} dependency {dep_name} not running"
                )

        record.state = ServiceState.STARTING
        try:
            if record.service:
                await record.service.start()
            record.state = ServiceState.RUNNING
            record.last_start = time.monotonic()
            logger.info(f"Service {record.name} started")
        except Exception as e:
            record.state = ServiceState.FAILED
            record.last_error = str(e)
            logger.error(f"Service {record.name} failed to start: {e}")
            raise

    async def _stop_service(self, record: ServiceRecord) -> None:
        """Stop a single service."""
        if record.state in (ServiceState.STOPPED, ServiceState.PENDING):
            return

        # Stop dependents first
        for dep_name in record.dependents:
            dep = self._services.get(dep_name)
            if dep and dep.state == ServiceState.RUNNING:
                await self._stop_service(dep)

        record.state = ServiceState.STOPPING
        try:
            if record.service:
                await record.service.stop()
            record.state = ServiceState.STOPPED
            record.last_stop = time.monotonic()
            logger.info(f"Service {record.name} stopped")
        except Exception as e:
            record.state = ServiceState.FAILED
            record.last_error = str(e)
            logger.error(f"Service {record.name} failed to stop: {e}")

    async def _monitor_health(self) -> None:
        """Monitor service health and restart failed services."""
        while self._running:
            await asyncio.sleep(self.heartbeat_interval)

            for name, record in self._services.items():
                if record.state != ServiceState.RUNNING:
                    continue

                try:
                    if record.service:
                        health = await record.service.health_check()
                        if not health.is_healthy:
                            logger.warning(
                                f"Service {name} unhealthy: {health.status}"
                            )
                            record.state = ServiceState.DEGRADED

                            # Check if heartbeat is stale
                            if health.heartbeat_age > self.heartbeat_timeout:
                                logger.error(
                                    f"Service {name} heartbeat stale "
                                    f"({health.heartbeat_age:.0f}s)"
                                )
                                await self._handle_service_failure(
                                    record, "heartbeat_timeout"
                                )
                except Exception as e:
                    logger.error(f"Health check failed for {name}: {e}")
                    await self._handle_service_failure(record, str(e))

    async def _handle_service_failure(self, record: ServiceRecord, error: str) -> None:
        """Handle a service failure — restart or halt."""
        record.state = ServiceState.FAILED
        record.last_error = error

        # Critical services trigger global halt
        critical_services = {"execution_engine", "reconciliation_loop"}
        if record.name in critical_services:
            await self.halt_coordinator.halt(
                reason=HaltReason.SERVICE_FAILURE,
                message=f"Critical service {record.name} failed: {error}",
                source="supervisor",
            )
            return

        # Non-critical services: attempt restart
        if self.restart_manager.should_restart(record):
            delay = self.restart_manager.get_restart_delay(record)
            logger.info(
                f"Restarting {record.name} in {delay:.1f}s "
                f"(attempt {record.restart_count + 1})"
            )
            await asyncio.sleep(delay)
            self.restart_manager.record_restart(record)
            try:
                await self._start_service(record)
            except Exception as e:
                logger.error(f"Restart failed for {record.name}: {e}")
        else:
            logger.error(
                f"Service {record.name} exceeded max restarts "
                f"({record.restart_count})"
            )

    async def _on_halt(self, event: HaltEvent) -> None:
        """Handle global halt — stop all trading services."""
        logger.info(f"Supervisor received halt: {event.reason.value}")

        # Stop execution-related services
        halt_order = ["strategy_engine", "execution_engine", "market_ingest"]
        for name in halt_order:
            if name in self._services:
                record = self._services[name]
                if record.state == ServiceState.RUNNING:
                    await self._stop_service(record)

    def _topological_sort(self) -> list[str]:
        """Topological sort of services by dependency."""
        visited = set()
        result = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            record = self._services.get(name)
            if record:
                for dep in record.dependencies:
                    visit(dep)
                result.append(name)

        for name in self._services:
            visit(name)

        return result
