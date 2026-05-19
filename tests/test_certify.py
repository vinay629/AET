"""Tests for certification replay mode."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from baet.core.certify import Certifier, Checkpoint
from baet.core.clock import Clock, set_clock, reset_clock
from baet.core.events import EventStore, EventType
from baet.core.snapshot import SnapshotManager
from baet.core.state import PortfolioState


TEST_TS = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def env(tmp_path):
    event_dir = tmp_path / "events"
    snap_dir = tmp_path / "snapshots"
    cert_dir = tmp_path / "cert"
    event_dir.mkdir()
    snap_dir.mkdir()
    cert_dir.mkdir()

    set_clock(Clock.fixed(TEST_TS))
    store = EventStore(event_dir)
    snap_mgr = SnapshotManager(snap_dir, interval=10)
    certifier = Certifier(
        event_store=store,
        snapshot_manager=snap_mgr,
        checkpoint_interval=2,
        cert_dir=cert_dir,
    )
    yield {"store": store, "snap_mgr": snap_mgr, "certifier": certifier, "cert_dir": cert_dir}
    store.close()
    reset_clock()


def _append_fill(store, symbol, side, price, units, fee, seq):
    store.append(
        EventType.ORDER_FILLED,
        TEST_TS,
        "test",
        {
            "symbol": symbol, "side": side,
            "price": str(price), "units": str(units), "fee": str(fee),
            "timestamp": TEST_TS.isoformat(),
        },
    )


class TestCertifier:
    def test_run_replay_no_events(self, env) -> None:
        state, checkpoints = env["certifier"].run_replay(save_checkpoints=False)
        assert isinstance(state, PortfolioState)
        assert len(checkpoints) == 0

    def test_run_replay_with_events(self, env) -> None:
        store = env["store"]
        _append_fill(store, "BTCUSDT", "BUY", 1000, 1, 1, 1)
        _append_fill(store, "ETHUSDT", "BUY", 3500, 0.1, 0.35, 2)
        _append_fill(store, "BTCUSDT", "SELL", 2000, 0.5, 1, 3)
        store.close()

        # Reopen for reading
        store2 = EventStore(store.base_dir)
        certifier = Certifier(
            event_store=store2,
            checkpoint_interval=2,
        )
        state, checkpoints = certifier.run_replay(save_checkpoints=False)

        assert state.cash < Decimal("10000")  # Bought BTC and ETH
        assert len(checkpoints) >= 1
        store2.close()

    def test_checkpoint_interval(self, env) -> None:
        store = env["store"]
        for i in range(5):
            _append_fill(store, "BTCUSDT", "BUY", 100, 0.01, 0.01, i + 1)
        store.close()

        store2 = EventStore(store.base_dir)
        certifier = Certifier(event_store=store2, checkpoint_interval=2)
        state, checkpoints = certifier.run_replay(save_checkpoints=False)

        # 5 events, interval=2 → checkpoints at event 2, 4, and final (5)
        assert len(checkpoints) >= 2
        store2.close()

    def test_certify_first_run_creates_checkpoints(self, env) -> None:
        store = env["store"]
        _append_fill(store, "BTCUSDT", "BUY", 1000, 1, 1, 1)
        store.close()

        store2 = EventStore(store.base_dir)
        certifier = Certifier(
            event_store=store2,
            checkpoint_interval=2,
            cert_dir=env["cert_dir"],
        )
        report = certifier.certify()

        assert report.passed is True
        assert report.checkpoints_verified > 0
        store2.close()

    def test_certify_second_run_verifies(self, env) -> None:
        store = env["store"]
        _append_fill(store, "BTCUSDT", "BUY", 1000, 1, 1, 1)
        store.close()

        store2 = EventStore(store.base_dir)
        certifier = Certifier(
            event_store=store2,
            checkpoint_interval=2,
            cert_dir=env["cert_dir"],
        )
        # First run creates checkpoints
        report1 = certifier.certify()
        assert report1.passed is True
        store2.close()

        # Second run verifies
        store3 = EventStore(store.base_dir)
        certifier2 = Certifier(
            event_store=store3,
            checkpoint_interval=2,
            cert_dir=env["cert_dir"],
        )
        report2 = certifier2.certify()
        assert report2.passed is True
        assert report2.checkpoints_failed == 0
        store3.close()

    def test_verify_determinism(self, env) -> None:
        store = env["store"]
        for i in range(5):
            _append_fill(store, "BTCUSDT", "BUY", 100 + i, 0.01, 0.01, i + 1)
        store.close()

        store2 = EventStore(store.base_dir)
        certifier = Certifier(event_store=store2, checkpoint_interval=2)
        is_deterministic = certifier.verify_determinism(iterations=3)
        assert is_deterministic is True
        store2.close()


class TestCheckpoint:
    def test_to_dict(self) -> None:
        cp = Checkpoint(sequence=10, state_hash="abc123", event_count=5)
        d = cp.__dict__
        assert d["sequence"] == 10
        assert d["state_hash"] == "abc123"
