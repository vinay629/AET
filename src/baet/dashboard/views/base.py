"""Base class for materialized views.

All views follow the same pattern:
1. Read events from the event journal
2. Reconstruct state via the pure reducer
3. Project state into a read-only JSON-serializable dict

Views NEVER:
- Mutate PortfolioState
- Call the exchange directly
- Write to the event journal
- Hold mutable global state
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from baet.core.events import EventStore
from baet.core.reducer import reduce_many
from baet.core.state import PortfolioState


@dataclass
class ViewCache:
    """Simple TTL cache for view results."""
    data: dict[str, Any] = field(default_factory=dict)
    computed_at: float = 0.0
    ttl_seconds: float = 1.0  # Default 1s TTL for near-real-time

    @property
    def is_stale(self) -> bool:
        return (time.monotonic() - self.computed_at) > self.ttl_seconds


class MaterializedView:
    """Base class for all materialized views."""

    def __init__(
        self,
        event_store: EventStore,
        cache_ttl: float = 1.0,
    ) -> None:
        self.event_store = event_store
        self._cache = ViewCache(ttl_seconds=cache_ttl)

    def get(self, **params: Any) -> dict[str, Any]:
        """
        Get the view data, using cache if fresh.

        Subclasses implement `_compute()` for the actual projection.
        """
        if self._cache.is_stale:
            self._cache.data = self._compute(**params)
            self._cache.computed_at = time.monotonic()
        return self._cache.data

    def refresh(self, **params: Any) -> dict[str, Any]:
        """Force recomputation, bypassing cache."""
        self._cache.data = self._compute(**params)
        self._cache.computed_at = time.monotonic()
        return self._cache.data

    def _compute(self, **params: Any) -> dict[str, Any]:
        """Override in subclasses. Return JSON-serializable dict."""
        raise NotImplementedError

    def _reconstruct_state(self, date: str | None = None) -> PortfolioState:
        """Reconstruct portfolio state from the event journal."""
        events = self.event_store.replay(date)
        return reduce_many(PortfolioState(), events)

    def _reconstruct_state_from_events(self, events: list) -> PortfolioState:
        """Reconstruct state from a pre-filtered event list."""
        return reduce_many(PortfolioState(), events)
