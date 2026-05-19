"""Core primitives for BAET."""

from baet.core.events import (
    Event,
    EventMigration,
    EventStore,
    EventType,
    EventValidationError,
    validate_event,
)
from baet.core.health import HealthCheck, HealthMonitor, HealthStatus, MetricsCollector, SystemHealth
from baet.core.orders import (
    FillEvent,
    Order,
    OrderLifecycleError,
    OrderSide,
    OrderStatus,
    OrderTracker,
    OrderType,
)
from baet.core.reconcile import (
    DriftReport,
    DriftSeverity,
    DriftType,
    ReconciliationEngine,
    ReconciliationReport,
)
from baet.core.snapshot import SnapshotManager
from baet.core.state import PortfolioState, Position, TradeRecord

__all__ = [
    # Events
    "Event",
    "EventMigration",
    "EventStore",
    "EventType",
    "EventValidationError",
    "validate_event",
    # State
    "PortfolioState",
    "Position",
    "TradeRecord",
    # Orders
    "FillEvent",
    "Order",
    "OrderLifecycleError",
    "OrderSide",
    "OrderStatus",
    "OrderTracker",
    "OrderType",
    # Reconciliation
    "DriftReport",
    "DriftSeverity",
    "DriftType",
    "ReconciliationEngine",
    "ReconciliationReport",
    # Snapshot
    "SnapshotManager",
    # Health
    "HealthCheck",
    "HealthMonitor",
    "HealthStatus",
    "MetricsCollector",
    "SystemHealth",
]
