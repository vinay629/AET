"""Portfolio snapshotting for fast recovery.

Instead of replaying millions of events from day 1,
restore from the latest snapshot + replay remaining events.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from baet.core.events import Event, EventStore, EventType
from baet.core.state import PortfolioState

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_INTERVAL = 1000  # events between snapshots


@dataclass
class SnapshotMetadata:
    """Metadata for a portfolio snapshot."""
    sequence: int
    event_count: int
    timestamp: datetime
    state_hash: str
    portfolio_state: dict[str, Any]


class SnapshotManager:
    """Manages portfolio state snapshots for fast recovery."""

    def __init__(self, snapshot_dir: Path, interval: int = DEFAULT_SNAPSHOT_INTERVAL) -> None:
        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.interval = interval
        self._events_since_snapshot = 0
        self._last_snapshot_sequence = 0

    def _snapshot_path(self, sequence: int) -> Path:
        return self.snapshot_dir / f"portfolio_{sequence}.json"

    def _metadata_path(self) -> Path:
        return self.snapshot_dir / "latest.json"

    def should_snapshot(self, event_sequence: int) -> bool:
        """Check if it's time to create a snapshot."""
        return event_sequence - self._last_snapshot_sequence >= self.interval

    def save_snapshot(self, state: PortfolioState, event_sequence: int,
                      event_count: int, store: EventStore) -> Path:
        """Save a portfolio state snapshot and record the event."""
        state_dict = state.snapshot()
        state_hash = self._compute_hash(state_dict)

        metadata = SnapshotMetadata(
            sequence=event_sequence,
            event_count=event_count,
            timestamp=datetime.now(timezone.utc),
            state_hash=state_hash,
            portfolio_state=state_dict,
        )

        path = self._snapshot_path(event_sequence)
        with path.open("w", encoding="utf-8") as f:
            json.dump({
                "sequence": metadata.sequence,
                "event_count": metadata.event_count,
                "timestamp": metadata.timestamp.isoformat(),
                "state_hash": metadata.state_hash,
                "portfolio_state": metadata.portfolio_state,
            }, f, indent=2, default=str)

        # Update latest pointer
        with self._metadata_path().open("w", encoding="utf-8") as f:
            json.dump({
                "latest_sequence": event_sequence,
                "latest_path": str(path),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)

        self._last_snapshot_sequence = event_sequence
        self._events_since_snapshot = 0

        # Record snapshot event
        store.append(
            event_type=EventType.SNAPSHOT_CREATED,
            timestamp_exchange=datetime.now(timezone.utc),
            source="snapshot_manager",
            payload={
                "sequence": event_sequence,
                "state_hash": state_hash,
                "path": str(path),
            },
        )

        logger.info(f"Snapshot saved at sequence {event_sequence}, hash={state_hash[:12]}")
        return path

    def load_latest_snapshot(self) -> tuple[dict[str, Any], int] | None:
        """Load the latest snapshot. Returns (state_dict, sequence) or None."""
        meta_path = self._metadata_path()
        if not meta_path.exists():
            return None

        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)

        snapshot_path = Path(meta["latest_path"])
        if not snapshot_path.exists():
            return None

        with snapshot_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        state_hash = data.get("state_hash", "")
        computed_hash = self._compute_hash(data["portfolio_state"])
        if state_hash != computed_hash:
            logger.error(f"Snapshot hash mismatch: stored={state_hash}, computed={computed_hash}")
            return None

        return data["portfolio_state"], data["sequence"]

    def restore_state(self, store: EventStore, date: str | None = None) -> tuple[PortfolioState, int]:
        """
        Restore portfolio state using snapshot + remaining events.
        Returns (state, last_sequence).
        """
        snapshot_data = self.load_latest_snapshot()

        if snapshot_data is None:
            # No snapshot — replay everything
            logger.info("No snapshot found, replaying all events")
            events = store.replay(date)
            state = PortfolioState.from_events(events)
            last_seq = events[-1].sequence if events else 0
            return state, last_seq

        state_dict, snapshot_sequence = snapshot_data
        logger.info(f"Restored from snapshot at sequence {snapshot_sequence}")

        # Rebuild state from snapshot
        state = PortfolioState(
            cash=Decimal(state_dict.get("cash", "10000.0")),
            positions={
                sym: {k: Decimal(v) for k, v in pos.items()}
                for sym, pos in state_dict.get("positions", {}).items()
            },
        )

        # Replay events after snapshot
        remaining_events = store.replay(date, from_sequence=snapshot_sequence + 1)
        for event in remaining_events:
            try:
                state.apply(event)
            except Exception:
                pass  # Skip events that don't apply to portfolio state

        last_seq = remaining_events[-1].sequence if remaining_events else snapshot_sequence
        logger.info(f"Replayed {len(remaining_events)} events after snapshot, now at sequence {last_seq}")

        return state, last_seq

    def verify_snapshot_integrity(self, state: PortfolioState) -> bool:
        """Verify that current state matches the latest snapshot."""
        meta_path = self._metadata_path()
        if not meta_path.exists():
            return True  # No snapshot to compare

        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)

        snapshot_path = Path(meta["latest_path"])
        if not snapshot_path.exists():
            return True

        with snapshot_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        stored_hash = data.get("state_hash", "")
        current_hash = self._compute_hash(state.snapshot())

        if current_hash != stored_hash:
            logger.error(f"State mismatch: current={current_hash[:12]}, snapshot={stored_hash[:12]}")
            return False
        return True

    @staticmethod
    def _compute_hash(state_dict: dict[str, Any]) -> str:
        """Compute a deterministic hash of portfolio state (excludes timestamp)."""
        import hashlib
        # Exclude timestamp since it changes on every call
        hashable = {k: v for k, v in state_dict.items() if k != "timestamp"}
        normalized = json.dumps(hashable, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def cleanup_old_snapshots(self, keep_last: int = 5) -> int:
        """Remove old snapshots, keeping only the most recent N. Returns count removed."""
        snapshots = sorted(self.snapshot_dir.glob("portfolio_*.json"))
        if len(snapshots) <= keep_last:
            return 0

        removed = 0
        for old_snapshot in snapshots[:-keep_last]:
            old_snapshot.unlink()
            removed += 1

        if removed:
            logger.info(f"Cleaned up {removed} old snapshots, keeping {keep_last}")
        return removed
