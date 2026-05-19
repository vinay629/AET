"""Market data view — read-only projection of market data.

Derived from event journal (candles stored as events).
Does NOT query the exchange directly.
"""

from __future__ import annotations

from typing import Any

from baet.dashboard.views.base import MaterializedView
from baet.core.events import EventType


class MarketView(MaterializedView):
    """Read-only market data projection from event journal."""

    def __init__(self, event_store, cache_ttl: float = 1.0) -> None:
        super().__init__(event_store, cache_ttl)

    def _compute(self, **params: Any) -> dict[str, Any]:
        symbol = params.get("symbol", "BTCUSDT")
        timeframe = params.get("timeframe", "1h")
        limit = params.get("limit", 100)
        date = params.get("date")

        events = self.event_store.replay(date)

        # Filter candle events for this symbol/timeframe
        candles = []
        for event in events:
            if event.event_type != EventType.CANDLE_RECEIVED:
                continue
            p = event.payload
            if p.get("symbol") != symbol:
                continue
            if p.get("timeframe") != timeframe:
                continue
            candles.append({
                "timestamp": p.get("open_time", ""),
                "open": p.get("open", 0),
                "high": p.get("high", 0),
                "low": p.get("low", 0),
                "close": p.get("close", 0),
                "volume": p.get("volume", 0),
                "quote_volume": p.get("quote_volume", 0),
                "trade_count": p.get("trade_count", 0),
                "is_closed": p.get("is_closed", True),
            })

        # Apply limit (most recent)
        candles = candles[-limit:]

        # Feed health metrics
        feed_health = self._compute_feed_health(events, symbol, timeframe)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles,
            "candle_count": len(candles),
            "feed_health": feed_health,
        }

    def _compute_feed_health(self, events: list, symbol: str, timeframe: str) -> dict:
        """Compute market feed health metrics."""
        candle_events = [
            e for e in events
            if e.event_type == EventType.CANDLE_RECEIVED
            and e.payload.get("symbol") == symbol
            and e.payload.get("timeframe") == timeframe
        ]

        if not candle_events:
            return {
                "status": "no_data",
                "last_candle_age_seconds": None,
                "gap_count": 0,
            }

        # Check for gaps (missing sequence numbers)
        gap_count = 0
        for i in range(1, len(candle_events)):
            seq_diff = candle_events[i].sequence - candle_events[i - 1].sequence
            if seq_diff > 1:
                gap_count += seq_count - 1

        # Last candle age
        import time
        last_ts = candle_events[-1].timestamp_exchange
        age_seconds = (time.time() - last_ts.timestamp()) if last_ts else None

        status = "healthy"
        if age_seconds and age_seconds > 300:  # 5 minutes
            status = "stale"
        if gap_count > 0:
            status = "degraded"

        return {
            "status": status,
            "last_candle_age_seconds": age_seconds,
            "gap_count": gap_count,
            "total_candles": len(candle_events),
        }
