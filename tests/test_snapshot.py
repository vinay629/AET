"""Tests for portfolio snapshotting."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from baet.core.events import EventStore, EventType
from baet.core.snapshot import SnapshotManager
from baet.core.state import PortfolioState


class TestSnapshotManager:
    """Tests that manage their own temp directories to avoid Windows handle issues."""

    def _make_dirs(self) -> tuple[Path, Path]:
        tmp = tempfile.mkdtemp()
        return Path(tmp) / "events", Path(tmp) / "snapshots", Path(tmp)

    def test_should_snapshot(self) -> None:
        _, snap_dir, tmp = self._make_dirs()
        manager = SnapshotManager(snapshot_dir=snap_dir, interval=100)
        assert not manager.should_snapshot(50)
        assert manager.should_snapshot(100)
        shutil.rmtree(tmp, ignore_errors=True)

    def test_save_and_load_snapshot(self) -> None:
        event_dir, snap_dir, tmp = self._make_dirs()
        store = EventStore(base_dir=event_dir)
        manager = SnapshotManager(snapshot_dir=snap_dir, interval=100)

        state = PortfolioState(cash=Decimal("9320.32"))
        state.positions["BTCUSDT"] = {
            "units": Decimal("0.01"),
            "avg_price": Decimal("68000"),
        }

        path = manager.save_snapshot(state, event_sequence=100, event_count=100, store=store)
        assert path.exists()
        store.close()

        loaded = manager.load_latest_snapshot()
        assert loaded is not None
        state_dict, seq = loaded
        assert seq == 100
        assert state_dict["cash"] == "9320.32"
        shutil.rmtree(tmp, ignore_errors=True)

    def test_no_snapshot_returns_none(self) -> None:
        _, snap_dir, tmp = self._make_dirs()
        manager = SnapshotManager(snapshot_dir=snap_dir)
        assert manager.load_latest_snapshot() is None
        shutil.rmtree(tmp, ignore_errors=True)

    def test_restore_state_from_snapshot(self) -> None:
        event_dir, snap_dir, tmp = self._make_dirs()
        store = EventStore(base_dir=event_dir)
        manager = SnapshotManager(snapshot_dir=snap_dir, interval=100)

        # Create some events first
        ts = datetime(2026, 5, 17, 10, 0, 0, tzinfo=timezone.utc)
        store.append(EventType.CANDLE_RECEIVED, ts, "test", {"close": 68000})
        store.append(EventType.CANDLE_RECEIVED, ts, "test", {"close": 68100})

        # Save snapshot at sequence 2
        state = PortfolioState(cash=Decimal("9000"))
        state.positions["BTCUSDT"] = {
            "units": Decimal("0.01"),
            "avg_price": Decimal("68000"),
        }
        manager.save_snapshot(state, event_sequence=2, event_count=2, store=store)

        # Add more events after snapshot
        store.append(
            EventType.ORDER_FILLED,
            ts,
            "test",
            {
                "symbol": "ETHUSDT",
                "side": "BUY",
                "price": 3000.0,
                "units": 0.1,
                "fee": 0.3,
                "timestamp": ts.isoformat(),
            },
        )
        store.close()

        # Restore should include post-snapshot events
        restored_state, last_seq = manager.restore_state(store, "2026-05-17")
        assert "BTCUSDT" in restored_state.positions
        assert "ETHUSDT" in restored_state.positions
        assert last_seq > 2
        shutil.rmtree(tmp, ignore_errors=True)

    def test_verify_integrity(self) -> None:
        event_dir, snap_dir, tmp = self._make_dirs()
        store = EventStore(base_dir=event_dir)
        manager = SnapshotManager(snapshot_dir=snap_dir, interval=100)

        state = PortfolioState(cash=Decimal("5000"))
        manager.save_snapshot(state, event_sequence=100, event_count=100, store=store)
        store.close()

        # Same state should match
        same_state = PortfolioState(cash=Decimal("5000"))
        assert manager.verify_snapshot_integrity(same_state)

        # Modified state should fail verification
        modified_state = PortfolioState(cash=Decimal("9999"))
        assert not manager.verify_snapshot_integrity(modified_state)
        shutil.rmtree(tmp, ignore_errors=True)

    def test_cleanup_old_snapshots(self) -> None:
        event_dir, snap_dir, tmp = self._make_dirs()
        store = EventStore(base_dir=event_dir)
        manager = SnapshotManager(snapshot_dir=snap_dir, interval=100)

        state = PortfolioState()
        for i in range(1, 8):
            manager.save_snapshot(state, event_sequence=i * 100, event_count=i * 100, store=store)
        store.close()

        removed = manager.cleanup_old_snapshots(keep_last=3)
        assert removed == 4  # 7 - 3 = 4 removed
        shutil.rmtree(tmp, ignore_errors=True)
