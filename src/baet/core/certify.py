"""Certification replay mode for BAET.

Guarantees that replaying the same event stream produces exactly
the same state, every time.

Usage:
    certifier = Certifier(event_store, snapshot_manager, interval=100)
    certifier.run_replay(date="2026-05-18")

    # Or for certification:
    certifier = Certifier(event_store, snapshot_manager, interval=100)
    report = certifier.certify(date="2026-05-18")
    assert report.passed

The certifier:
1. Replays events from the journal
2. Computes state_hash every N events
3. Compares against stored checkpoints
4. Reports any divergence
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from baet.core.events import Event, EventStore
from baet.core.reducer import reduce_many
from baet.core.snapshot import SnapshotManager
from baet.core.state import PortfolioState

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """State hash at a specific sequence number."""
    sequence: int
    state_hash: str
    event_count: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CertifyReport:
    """Result of a certification run."""
    passed: bool
    date: str
    total_events: int
    checkpoints_verified: int
    checkpoints_failed: int
    divergences: list[dict[str, Any]]
    duration_seconds: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "date": self.date,
            "total_events": self.total_events,
            "checkpoints_verified": self.checkpoints_verified,
            "checkpoints_failed": self.checkpoints_failed,
            "divergences": len(self.divergences),
            "duration_seconds": self.duration_seconds,
        }


class Certifier:
    """
    Certifies that event replay is deterministic.

    Runs the full event stream through the reducer and verifies
    that state hashes match at regular intervals.
    """

    def __init__(
        self,
        event_store: EventStore,
        snapshot_manager: SnapshotManager | None = None,
        checkpoint_interval: int = 100,
        cert_dir: Path | None = None,
    ) -> None:
        self.event_store = event_store
        self.snapshot_manager = snapshot_manager
        self.checkpoint_interval = checkpoint_interval
        self.cert_dir = cert_dir
        if self.cert_dir:
            self.cert_dir.mkdir(parents=True, exist_ok=True)

    def run_replay(
        self,
        date: str | None = None,
        *,
        save_checkpoints: bool = True,
    ) -> tuple[PortfolioState, list[Checkpoint]]:
        """
        Replay all events and compute checkpoints.

        Args:
            date: Date to replay (None = today).
            save_checkpoints: Whether to save checkpoints to disk.

        Returns:
            (final_state, checkpoints).
        """
        events = self.event_store.replay(date)
        if not events:
            logger.info(f"No events to replay for {date}")
            return PortfolioState(), []

        checkpoints: list[Checkpoint] = []
        state = PortfolioState()

        for i, event in enumerate(events):
            state = self._reduce_single(state, event)

            if (i + 1) % self.checkpoint_interval == 0:
                checkpoint = Checkpoint(
                    sequence=event.sequence,
                    state_hash=state.state_hash(),
                    event_count=i + 1,
                )
                checkpoints.append(checkpoint)

        # Final checkpoint
        if events and (len(events) % self.checkpoint_interval != 0):
            checkpoint = Checkpoint(
                sequence=events[-1].sequence,
                state_hash=state.state_hash(),
                event_count=len(events),
            )
            checkpoints.append(checkpoint)

        if save_checkpoints and self.cert_dir:
            self._save_checkpoints(date or "today", checkpoints)

        logger.info(
            f"Replay complete: {len(events)} events, {len(checkpoints)} checkpoints"
        )
        return state, checkpoints

    def certify(
        self,
        date: str | None = None,
    ) -> CertifyReport:
        """
        Certify that replay produces the same results as stored checkpoints.

        If no stored checkpoints exist, creates them (first run).
        On subsequent runs, verifies against stored checkpoints.
        """
        import time

        start = time.monotonic()
        date_str = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Load stored checkpoints
        stored = self._load_checkpoints(date_str)

        # Run replay
        state, checkpoints = self.run_replay(date, save_checkpoints=(stored is None))

        if stored is None:
            # First run — store checkpoints
            logger.info("First certification run — storing checkpoints")
            return CertifyReport(
                passed=True,
                date=date_str,
                total_events=len(checkpoints) * self.checkpoint_interval,
                checkpoints_verified=len(checkpoints),
                checkpoints_failed=0,
                divergences=[],
                duration_seconds=time.monotonic() - start,
            )

        # Verify against stored
        divergences: list[dict[str, Any]] = []
        verified = 0

        stored_map = {cp.sequence: cp for cp in stored}
        for cp in checkpoints:
            if cp.sequence in stored_map:
                if cp.state_hash == stored_map[cp.sequence].state_hash:
                    verified += 1
                else:
                    divergences.append({
                        "sequence": cp.sequence,
                        "stored_hash": stored_map[cp.sequence].state_hash,
                        "computed_hash": cp.state_hash,
                    })

        failed = len(divergences)
        passed = failed == 0

        if not passed:
            logger.error(f"CERTIFICATION FAILED: {failed} divergences")
            for d in divergences:
                logger.error(f"  Seq {d['sequence']}: stored={d['stored_hash'][:12]} computed={d['computed_hash'][:12]}")
        else:
            logger.info(f"Certification passed: {verified} checkpoints verified")

        return CertifyReport(
            passed=passed,
            date=date_str,
            total_events=sum(cp.event_count for cp in checkpoints),
            checkpoints_verified=verified,
            checkpoints_failed=failed,
            divergences=divergences,
            duration_seconds=time.monotonic() - start,
        )

    def verify_determinism(
        self,
        date: str | None = None,
        iterations: int = 3,
    ) -> bool:
        """
        Run replay N times and verify all produce the same final state hash.

        This catches non-determinism from:
        - Floating point ordering
        - Dict iteration order
        - Hidden state
        """
        hashes: list[str] = []
        for i in range(iterations):
            state, _ = self.run_replay(date, save_checkpoints=False)
            hashes.append(state.state_hash())

        unique_hashes = set(hashes)
        if len(unique_hashes) == 1:
            logger.info(f"Determinism verified: {iterations} iterations, all hash={hashes[0][:12]}")
            return True
        else:
            logger.error(f"DETERMINISM FAILURE: {len(unique_hashes)} different hashes across {iterations} iterations")
            for h in hashes:
                logger.error(f"  {h[:12]}")
            return False

    def _reduce_single(self, state: PortfolioState, event: Event) -> PortfolioState:
        """Apply a single event to state using the pure reducer."""
        from baet.core.reducer import reduce_state
        return reduce_state(state, event)

    def _save_checkpoints(self, date: str, checkpoints: list[Checkpoint]) -> None:
        if not self.cert_dir:
            return
        path = self.cert_dir / f"checkpoints_{date}.json"
        with path.open("w") as f:
            json.dump([
                {
                    "sequence": cp.sequence,
                    "state_hash": cp.state_hash,
                    "event_count": cp.event_count,
                    "timestamp": cp.timestamp.isoformat(),
                }
                for cp in checkpoints
            ], f, indent=2)

    def _load_checkpoints(self, date: str) -> list[Checkpoint] | None:
        if not self.cert_dir:
            return None
        path = self.cert_dir / f"checkpoints_{date}.json"
        if not path.exists():
            return None
        with path.open("r") as f:
            data = json.load(f)
        return [
            Checkpoint(
                sequence=cp["sequence"],
                state_hash=cp["state_hash"],
                event_count=cp["event_count"],
                timestamp=datetime.fromisoformat(cp["timestamp"]),
            )
            for cp in data
        ]
