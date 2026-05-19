"""Audit view — read-only event explorer and hash chain verification.

Derived from event journal only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from baet.dashboard.views.base import MaterializedView
from baet.core.events import EventType


class AuditView(MaterializedView):
    """Read-only audit and event explorer projection."""

    def __init__(self, event_store, cache_ttl: float = 0.5) -> None:
        super().__init__(event_store, cache_ttl)

    def _compute(self, **params: Any) -> dict[str, Any]:
        # Search parameters
        event_id = params.get("event_id")
        order_id = params.get("order_id")
        symbol = params.get("symbol")
        event_type = params.get("event_type")
        date = params.get("date")
        limit = params.get("limit", 100)
        offset = params.get("offset", 0)

        events = self.event_store.replay(date)

        # Filter
        filtered = []
        for event in events:
            if event_id and event.event_id != event_id:
                continue
            if order_id:
                p = event.payload
                if p.get("client_order_id") != order_id and p.get("order_id") != order_id:
                    continue
            if symbol and event.payload.get("symbol") != symbol:
                continue
            if event_type and event.event_type.value != event_type:
                continue
            filtered.append(event)

        # Paginate
        total = len(filtered)
        paginated = filtered[offset:offset + limit]

        # Build event details
        event_details = []
        for event in paginated:
            event_details.append({
                "event_id": event.event_id,
                "sequence": event.sequence,
                "type": event.event_type.value,
                "source": event.source,
                "timestamp_exchange": event.timestamp_exchange.isoformat(),
                "timestamp_local": event.timestamp_local.isoformat(),
                "payload": event.payload,
                "schema_version": event.schema_version,
            })

        # Hash chain verification
        hash_chain = self._verify_hash_chain(events)

        # State diffs (before/after for each event)
        diffs = self._compute_state_diffs(paginated)

        return {
            "events": event_details,
            "total": total,
            "offset": offset,
            "limit": limit,
            "hash_chain": hash_chain,
            "state_diffs": diffs,
        }

    def _verify_hash_chain(self, events: list) -> dict[str, Any]:
        """Verify event chain integrity via sequence numbers."""
        if not events:
            return {"valid": True, "gaps": [], "duplicates": []}

        gaps = []
        duplicates = []
        seen_sequences = set()

        for i, event in enumerate(events):
            if event.sequence in seen_sequences:
                duplicates.append(event.sequence)
            seen_sequences.add(event.sequence)

            if i > 0:
                prev_seq = events[i - 1].sequence
                if event.sequence != prev_seq + 1:
                    gaps.append({
                        "from": prev_seq,
                        "to": event.sequence,
                        "missing": event.sequence - prev_seq - 1,
                    })

        return {
            "valid": len(gaps) == 0 and len(duplicates) == 0,
            "gaps": gaps,
            "duplicates": duplicates,
            "total_events": len(events),
            "first_sequence": events[0].sequence if events else 0,
            "last_sequence": events[-1].sequence if events else 0,
        }

    def _compute_state_diffs(self, events: list) -> list[dict]:
        """Compute state before/after for each event."""
        diffs = []
        for event in events:
            p = event.payload
            diff = {
                "event_id": event.event_id,
                "sequence": event.sequence,
                "type": event.event_type.value,
                "changes": {},
            }

            if event.event_type == EventType.ORDER_FILLED:
                diff["changes"] = {
                    "cash_delta": str(
                        Decimal(str(p.get("price", 0))) * Decimal(str(p.get("units", 0)))
                        * (-1 if p.get("side") == "BUY" else 1)
                    ),
                    "position_changed": p.get("symbol"),
                    "fee": p.get("fee", "0"),
                }
            elif event.event_type == EventType.PORTFOLIO_UPDATED:
                diff["changes"] = {
                    "cash": p.get("cash"),
                    "positions": p.get("positions"),
                }

            diffs.append(diff)

        return diffs
