"""Replay view — read-only projection for replay and certification.

Derived from event journal + certifier.
"""

from __future__ import annotations

from typing import Any

from baet.dashboard.views.base import MaterializedView
from baet.core.certify import Certifier


class ReplayView(MaterializedView):
    """Read-only replay and certification projection."""

    def __init__(self, event_store, certifier: Certifier | None = None, cache_ttl: float = 5.0) -> None:
        super().__init__(event_store, cache_ttl)
        self.certifier = certifier

    def _compute(self, **params: Any) -> dict[str, Any]:
        date = params.get("date")
        events = self.event_store.replay(date)

        # Event timeline summary
        timeline = self._build_timeline(events)

        # Checkpoints
        checkpoints = []
        if self.certifier:
            _, cps = self.certifier.run_replay(date, save_checkpoints=False)
            checkpoints = [
                {
                    "sequence": cp.sequence,
                    "state_hash": cp.state_hash[:16],
                    "event_count": cp.event_count,
                }
                for cp in cps
            ]

        # Certification status
        cert_status = "not_run"
        if self.certifier and checkpoints:
            report = self.certifier.certify(date)
            cert_status = "passed" if report.passed else "failed"

        return {
            "date": date or "today",
            "total_events": len(events),
            "timeline": timeline,
            "checkpoints": checkpoints,
            "certification_status": cert_status,
            "available_dates": self._list_available_dates(),
        }

    def _build_timeline(self, events: list) -> list[dict]:
        """Build event timeline summary."""
        timeline = []
        for event in events[-100:]:  # Last 100 events
            timeline.append({
                "sequence": event.sequence,
                "type": event.event_type.value,
                "source": event.source,
                "timestamp": event.timestamp_exchange.isoformat(),
                "summary": self._summarize_event(event),
            })
        return timeline

    @staticmethod
    def _summarize_event(event) -> str:
        """Create human-readable event summary."""
        p = event.payload
        if event.event_type.value == "order_filled":
            return f"{p.get('side')} {p.get('units')} {p.get('symbol')} @ {p.get('price')}"
        if event.event_type.value == "candle_received":
            return f"Candle {p.get('symbol')} {p.get('timeframe')} O={p.get('open')} C={p.get('close')}"
        if event.event_type.value == "signal_generated":
            return f"Signal {p.get('action')} {p.get('symbol')} conf={p.get('confidence')}"
        if event.event_type.value == "error":
            return f"Error: {p.get('type', 'unknown')}"
        return event.event_type.value

    def _list_available_dates(self) -> list[str]:
        """List dates with event data."""
        import json
        dates = []
        for f in sorted(self.event_store.base_dir.glob("*.jsonl")):
            date_str = f.stem  # YYYY-MM-DD
            dates.append(date_str)
        return dates
