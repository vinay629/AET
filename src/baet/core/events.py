"""Event primitives for BAET.

Every important thing that happens in the system is an immutable event.
Events are the single source of truth for replay, debugging, and learning.

Schema versioning: all events carry schema_version for forward compatibility.
Atomic writes: fsync after every append, corruption recovery on startup.
Idempotency: processed_event_ids prevents duplicate processing.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from baet.core.clock import Clock, get_clock

# Current schema version — bump when event schema changes
CURRENT_SCHEMA_VERSION = 1

# Required fields every event must have
REQUIRED_EVENT_FIELDS = {
    "event_id", "sequence", "event_type",
    "timestamp_exchange", "source", "payload",
}


class EventType(StrEnum):
    # Market data
    CANDLE_RECEIVED = "candle_received"

    # Signal generation
    SIGNAL_GENERATED = "signal_generated"

    # Risk
    RISK_DECISION = "risk_decision"

    # Execution
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_PARTIAL_FILL = "order_partial_fill"
    ORDER_EXPIRED = "order_expired"

    # Portfolio
    PORTFOLIO_UPDATED = "portfolio_updated"
    EQUITY_SNAPSHOT = "equity_snapshot"

    # System
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SNAPSHOT_CREATED = "snapshot_created"
    ERROR = "error"


class EventValidationError(Exception):
    """Raised when an event fails validation before append."""
    pass


class EventCorruptionError(Exception):
    """Raised when journal corruption is detected and cannot be recovered."""
    pass


@dataclass(frozen=True)
class Event:
    """Immutable event — the fundamental unit of truth in BAET."""

    event_type: EventType
    timestamp_exchange: datetime
    timestamp_local: datetime
    sequence: int
    source: str
    payload: dict[str, Any]
    schema_version: int = CURRENT_SCHEMA_VERSION
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "timestamp_exchange": self.timestamp_exchange.isoformat(),
            "timestamp_local": self.timestamp_local.isoformat(),
            "latency_ms": round(
                (self.timestamp_local - self.timestamp_exchange).total_seconds() * 1000, 2
            ),
            "source": self.source,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        schema_version = data.get("schema_version", 1)
        if schema_version < CURRENT_SCHEMA_VERSION:
            data = EventMigration.migrate(data, schema_version, CURRENT_SCHEMA_VERSION)

        return cls(
            event_id=data["event_id"],
            sequence=data["sequence"],
            event_type=EventType(data["event_type"]),
            timestamp_exchange=datetime.fromisoformat(data["timestamp_exchange"]),
            timestamp_local=datetime.fromisoformat(data["timestamp_local"]),
            source=data["source"],
            payload=data["payload"],
            schema_version=data.get("schema_version", CURRENT_SCHEMA_VERSION),
        )

    @classmethod
    def from_json(cls, line: str) -> Event:
        return cls.from_dict(json.loads(line))


class EventMigration:
    """Schema migration handler for forward compatibility.

    Even if unused now, this ensures old journals remain readable
    when the schema evolves.
    """

    _migrations: dict[tuple[int, int], callable] = {}

    @classmethod
    def register(cls, from_ver: int, to_ver: int):
        """Decorator to register a migration function."""
        def decorator(fn):
            cls._migrations[(from_ver, to_ver)] = fn
            return fn
        return decorator

    @classmethod
    def migrate(cls, data: dict[str, Any], from_ver: int, to_ver: int) -> dict[str, Any]:
        """Migrate event data from one schema version to another."""
        if from_ver == to_ver:
            return data
        key = (from_ver, to_ver)
        if key in cls._migrations:
            return cls._migrations[key](data)
        data["schema_version"] = to_ver
        return data


def validate_event(event: Event) -> list[str]:
    """Validate an event before append. Returns list of violations."""
    violations: list[str] = []

    if not isinstance(event.payload, dict):
        violations.append("payload must be a dict")

    # Time-based validation is done in the invariant layer, not here.
    # The event store only checks structural integrity.

    if event.sequence <= 0:
        violations.append(f"sequence must be positive, got {event.sequence}")

    try:
        uuid.UUID(event.event_id)
    except ValueError:
        violations.append(f"invalid event_id: {event.event_id}")

    if not event.source.strip():
        violations.append("source must not be empty")

    return violations


class EventStore:
    """Append-only event journal with atomic writes and corruption recovery.

    One JSONL file per day. Global sequence across all files.
    Atomic append: flush + fsync after every write.
    Corruption recovery: detect and truncate malformed trailing lines on startup.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sequence = 0
        self._current_file: Path | None = None
        self._current_handle = None
        self._processed_ids: set[str] = set()

    def _file_for(self, dt: datetime) -> Path:
        return self.base_dir / f"{dt.strftime('%Y-%m-%d')}.jsonl"

    def _recover_corruption(self, path: Path) -> int:
        """Scan file for corruption. Truncate malformed trailing lines. Returns last valid sequence."""
        if not path.exists():
            return 0

        last_valid_seq = 0
        last_valid_pos = 0
        corrupted = False

        with path.open("r+b") as f:
            pos = 0
            while True:
                line = f.readline()
                if not line:
                    break
                line_stripped = line.strip()
                if not line_stripped:
                    pos = f.tell()
                    continue
                try:
                    data = json.loads(line_stripped.decode("utf-8"))
                    if not REQUIRED_EVENT_FIELDS.issubset(data.keys()):
                        corrupted = True
                        break
                    datetime.fromisoformat(data["timestamp_exchange"])
                    datetime.fromisoformat(data["timestamp_local"])
                    EventType(data["event_type"])
                    last_valid_seq = data.get("sequence", last_valid_seq)
                    last_valid_pos = f.tell()
                except (json.JSONDecodeError, KeyError, ValueError, UnicodeDecodeError):
                    corrupted = True
                    break

        if corrupted and last_valid_pos > 0:
            with path.open("r+", encoding="utf-8") as f:
                f.truncate(last_valid_pos)
            with path.open("a", encoding="utf-8") as f:
                f.write("\n")
        elif corrupted:
            # File is entirely corrupted — truncate to empty
            with path.open("w", encoding="utf-8") as f:
                pass

        return last_valid_seq

    def _ensure_handle(self, dt: datetime) -> None:
        path = self._file_for(dt)
        if path != self._current_file:
            if self._current_handle:
                self._current_handle.close()
            path.parent.mkdir(parents=True, exist_ok=True)
            recovered_seq = self._recover_corruption(path)
            self._sequence = max(self._sequence, recovered_seq)
            self._current_handle = path.open("a", encoding="utf-8")
            self._current_file = path

    def append(self, event_type: EventType, timestamp_exchange: datetime,
               source: str, payload: dict[str, Any],
               clock: Clock | None = None) -> Event:
        """Create, validate, and atomically persist an event. Returns the persisted event.

        Args:
            event_type: Type of event.
            timestamp_exchange: Exchange-reported timestamp.
            source: Component that produced this event.
            payload: Event data.
            clock: Optional clock for local timestamp. Defaults to global clock.
        """
        self._ensure_handle(timestamp_exchange)
        self._sequence += 1
        clk = clock or get_clock()
        event = Event(
            event_type=event_type,
            timestamp_exchange=timestamp_exchange,
            timestamp_local=clk.now(),
            sequence=self._sequence,
            source=source,
            payload=payload,
        )

        violations = validate_event(event)
        if violations:
            self._sequence -= 1
            raise EventValidationError(
                f"Event validation failed: {'; '.join(violations)}"
            )

        self._current_handle.write(event.to_json() + "\n")
        self._current_handle.flush()
        os.fsync(self._current_handle.fileno())

        self._processed_ids.add(event.event_id)
        return event

    def build_event(self, event_type: EventType, timestamp_exchange: datetime,
                    source: str, payload: dict[str, Any],
                    clock: Clock | None = None) -> Event:
        """Create an Event object without persisting it.

        Useful for testing and for building events that may be
        validated before commit.
        """
        clk = clock or get_clock()
        self._sequence += 1
        return Event(
            event_type=event_type,
            timestamp_exchange=timestamp_exchange,
            timestamp_local=clk.now(),
            sequence=self._sequence,
            source=source,
            payload=payload,
        )

    def is_processed(self, event_id: str) -> bool:
        """Check if an event has already been processed (idempotency)."""
        return event_id in self._processed_ids

    def replay(self, date: str | None = None, from_sequence: int = 0) -> list[Event]:
        """Replay events for a given date, optionally from a sequence."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.base_dir / f"{date}.jsonl"
        if not path.exists():
            return []
        events = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = Event.from_json(line)
                    if event.sequence >= from_sequence:
                        events.append(event)
                        self._processed_ids.add(event.event_id)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        return events

    def replay_range(self, from_date: str, to_date: str) -> list[Event]:
        """Replay events across a date range (inclusive)."""
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        all_events: list[Event] = []
        current = from_dt
        while current <= to_dt:
            all_events.extend(self.replay(current.strftime("%Y-%m-%d")))
            current += timedelta(days=1)
        all_events.sort(key=lambda e: e.sequence)
        return all_events

    def get_latest_sequence(self) -> int:
        """Get the highest sequence number across all journal files."""
        max_seq = 0
        for jsonl_file in sorted(self.base_dir.glob("*.jsonl")):
            seq = self._recover_corruption(jsonl_file)
            max_seq = max(max_seq, seq)
        return max_seq

    def close(self) -> None:
        if self._current_handle:
            self._current_handle.close()
            self._current_handle = None
            self._current_file = None

    def __enter__(self) -> EventStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
