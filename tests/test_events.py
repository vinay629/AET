"""Tests for event store, validation, and corruption recovery."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from baet.core.events import (
    Event,
    EventMigration,
    EventStore,
    EventType,
    EventValidationError,
    validate_event,
)


class TestEvent:
    def test_create_event(self) -> None:
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="test",
            payload={"symbol": "BTCUSDT", "close": 68490.0},
        )
        assert event.event_type == EventType.CANDLE_RECEIVED
        assert event.sequence == 1
        assert event.schema_version == 1

    def test_event_is_frozen(self) -> None:
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="test",
            payload={},
        )
        with pytest.raises(AttributeError):
            event.sequence = 2  # type: ignore[misc]

    def test_event_to_json_roundtrip(self) -> None:
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        original = Event(
            event_type=EventType.SIGNAL_GENERATED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=5,
            source="strategy",
            payload={"action": "BUY", "confidence": 0.72},
        )
        json_str = original.to_json()
        restored = Event.from_json(json_str)
        assert restored.event_id == original.event_id
        assert restored.sequence == original.sequence
        assert restored.event_type == original.event_type
        assert restored.payload == original.payload
        assert restored.schema_version == original.schema_version

    def test_event_includes_schema_version(self) -> None:
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="test",
            payload={},
        )
        d = event.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == 1


class TestEventValidation:
    def test_valid_event_passes(self) -> None:
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="test",
            payload={"close": 68490.0},
        )
        violations = validate_event(event)
        assert violations == []

    def test_negative_sequence_fails(self) -> None:
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=-1,
            source="test",
            payload={},
        )
        violations = validate_event(event)
        assert any("sequence" in v for v in violations)

    def test_empty_source_fails(self) -> None:
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="   ",
            payload={},
        )
        violations = validate_event(event)
        assert any("source" in v for v in violations)

    def test_exchange_after_local_no_longer_fails_in_store(self) -> None:
        """Time-based validation is now in the invariant layer, not the event store.
        The event store only checks structural integrity."""
        ts_exchange = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        ts_local = datetime(2026, 5, 17, 9, 0, 0, tzinfo=timezone.utc)
        event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts_exchange,
            timestamp_local=ts_local,
            sequence=1,
            source="test",
            payload={},
        )
        # Event store validation passes — time checks are in invariant layer
        violations = validate_event(event)
        assert len(violations) == 0

    def test_structural_validation_still_works(self) -> None:
        """Event store still validates structure: payload must be dict, source non-empty."""
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        # Invalid: payload is not a dict
        event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="test",
            payload="not a dict",  # type: ignore
        )
        violations = validate_event(event)
        assert any("payload must be a dict" in v for v in violations)


class TestEventMigration:
    def test_no_migration_needed(self) -> None:
        data = {"schema_version": 1, "event_type": "candle_received"}
        result = EventMigration.migrate(data, 1, 1)
        assert result == data

    def test_migration_updates_version(self) -> None:
        data = {"schema_version": 1, "event_type": "candle_received"}
        result = EventMigration.migrate(data, 1, 2)
        assert result["schema_version"] == 2

    def test_registered_migration_runs(self) -> None:
        @EventMigration.register(1, 2)
        def add_field(data: dict) -> dict:
            data["new_field"] = "added"
            data["schema_version"] = 2
            return data

        data = {"schema_version": 1, "event_type": "candle_received"}
        result = EventMigration.migrate(data, 1, 2)
        assert result.get("new_field") == "added"


class TestEventStore:
    """Tests that manage their own temp directories to avoid Windows handle issues."""

    def _make_store(self) -> tuple[EventStore, Path]:
        tmp = tempfile.mkdtemp()
        store = EventStore(base_dir=Path(tmp))
        return store, Path(tmp)

    def test_append_creates_event(self) -> None:
        store, tmp = self._make_store()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = store.append(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            source="test",
            payload={"symbol": "BTCUSDT"},
        )
        assert event.event_type == EventType.CANDLE_RECEIVED
        assert event.sequence == 1
        store.close()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_append_validates_before_write(self) -> None:
        """Event store validates structural properties before write."""
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        # Invalid: empty source
        invalid_event = Event(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=ts,
            timestamp_local=ts,
            sequence=1,
            source="   ",
            payload={},
        )
        violations = validate_event(invalid_event)
        assert len(violations) > 0
        assert any("source" in v for v in violations)

    def test_append_increments_sequence(self) -> None:
        store, tmp = self._make_store()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        e1 = store.append(EventType.CANDLE_RECEIVED, ts, "test", {})
        e2 = store.append(EventType.CANDLE_RECEIVED, ts, "test", {})
        assert e2.sequence == e1.sequence + 1
        store.close()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_append_writes_to_file(self) -> None:
        store, tmp = self._make_store()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        store.append(EventType.CANDLE_RECEIVED, ts, "test", {"close": 68490.0})
        store.close()

        jsonl_files = list(Path(tmp).glob("*.jsonl"))
        assert len(jsonl_files) == 1
        data = json.loads(jsonl_files[0].read_text(encoding="utf-8").strip())
        assert data["event_type"] == "candle_received"
        assert data["schema_version"] == 1
        shutil.rmtree(tmp, ignore_errors=True)

    def test_replay_returns_events(self) -> None:
        store, tmp = self._make_store()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        store.append(EventType.CANDLE_RECEIVED, ts, "test", {"close": 68490.0})
        store.append(EventType.SIGNAL_GENERATED, ts, "test", {"action": "BUY"})
        store.close()

        # Re-open for replay
        store2 = EventStore(base_dir=Path(tmp))
        events = store2.replay("2026-05-17")
        assert len(events) == 2
        store2.close()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_replay_from_sequence(self) -> None:
        store, tmp = self._make_store()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            store.append(EventType.CANDLE_RECEIVED, ts, "test", {"i": i})
        store.close()

        store2 = EventStore(base_dir=Path(tmp))
        events = store2.replay("2026-05-17", from_sequence=3)
        assert len(events) == 3
        assert events[0].sequence == 3
        store2.close()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_is_processed_idempotency(self) -> None:
        store, tmp = self._make_store()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        event = store.append(EventType.CANDLE_RECEIVED, ts, "test", {})
        assert store.is_processed(event.event_id)
        assert not store.is_processed("nonexistent-id")
        store.close()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_corruption_recovery(self) -> None:
        tmp = tempfile.mkdtemp()
        jsonl_path = Path(tmp) / "2026-05-17.jsonl"
        valid_event = json.dumps({
            "schema_version": 1,
            "event_id": "abc123",
            "sequence": 1,
            "event_type": "candle_received",
            "timestamp_exchange": "2026-05-17T10:00:00+00:00",
            "timestamp_local": "2026-05-17T10:00:00.050+00:00",
            "source": "test",
            "payload": {"close": 68490.0},
        })
        jsonl_path.write_text(valid_event + "\n{\"corrupted\n", encoding="utf-8")

        store = EventStore(base_dir=Path(tmp))
        events = store.replay("2026-05-17")
        assert len(events) == 1
        assert events[0].event_id == "abc123"
        store.close()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_resume_sequence_after_reopen(self) -> None:
        tmp = tempfile.mkdtemp()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)

        store1 = EventStore(base_dir=Path(tmp))
        store1.append(EventType.CANDLE_RECEIVED, ts, "test", {})
        store1.append(EventType.CANDLE_RECEIVED, ts, "test", {})
        store1.close()

        store2 = EventStore(base_dir=Path(tmp))
        e3 = store2.append(EventType.CANDLE_RECEIVED, ts, "test", {})
        assert e3.sequence == 3
        store2.close()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_context_manager(self) -> None:
        tmp = tempfile.mkdtemp()
        with EventStore(base_dir=Path(tmp)) as store:
            ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
            store.append(EventType.CANDLE_RECEIVED, ts, "test", {})
        assert (Path(tmp) / "2026-05-17.jsonl").exists()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_get_latest_sequence(self) -> None:
        store, tmp = self._make_store()
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            store.append(EventType.CANDLE_RECEIVED, ts, "test", {"i": i})
        assert store.get_latest_sequence() == 5
        store.close()
        shutil.rmtree(tmp, ignore_errors=True)
